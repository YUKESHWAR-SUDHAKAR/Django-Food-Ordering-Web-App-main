import json
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, ExpressionWrapper, F, FloatField, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .form import CustomUserForm
from .models import (
    Cart,
    Category,
    Coupon,
    Delivery,
    DeliveryZone,
    Favourite,
    Items,
    Notification,
    Order,
    OrderItem,
    Payment,
    UserProfile,
)
from .utils import (
    apply_item_filters,
    build_checkout_signature,
    build_invoice_pdf,
    calculate_cart_totals,
    clear_coupon_session,
    create_notification,
    ensure_invoice,
    estimate_delivery_time,
    get_coupon_from_session,
    get_recommended_items,
    track_activity,
)


def _cart_items_for(user):
    return Cart.objects.filter(user=user).select_related("product", "product__category")


def _active_zones():
    return DeliveryZone.objects.filter(is_active=True).order_by("pincode")


def _parse_optional_float(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _parse_scheduled_datetime(raw_value):
    if not raw_value:
        return None
    scheduled_for = datetime.fromisoformat(raw_value)
    if timezone.is_naive(scheduled_for):
        scheduled_for = timezone.make_aware(scheduled_for, timezone.get_current_timezone())
    return scheduled_for


def home(request):
    categories = Category.objects.all()
    menu_queryset = Items.objects.select_related("category").all()
    filtered_items, filter_state, applied_filters = apply_item_filters(menu_queryset, request.GET)
    category_spotlights = [
        {"category": category, "items": category.items.all()[:4]}
        for category in categories[:4]
    ]
    context = {
        "categories": categories,
        "items": filtered_items[:8],
        "new_items": Items.objects.select_related("category").filter(new_added_item=True)[:4],
        "recommended_items": get_recommended_items(request.user if request.user.is_authenticated else None, limit=4),
        "category_spotlights": category_spotlights,
        "filter_state": filter_state,
        "applied_filters": applied_filters,
    }
    return render(request, "home.html", context)


def login_page(request):
    if request.user.is_authenticated:
        return redirect("Home")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        if not username or not password:
            messages.error(request, "Username and password are required.")
            return render(request, "login.html")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "Logged in successfully.")
            return redirect("Home")

        messages.error(request, "Invalid username or password.")
    return render(request, "login.html")


def logout_page(request):
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, "Logged out successfully.")
    return redirect("Login")


def register(request):
    form = CustomUserForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Registration successful! You can now log in.")
            return redirect("Login")
        messages.error(request, "Please correct the highlighted fields.")
    return render(request, "register.html", {"form": form})


def category(request):
    categories = Category.objects.annotate(item_count=Count("items"))
    return render(request, "categories.html", {"categories": categories})


def categoryview(request, name):
    category_obj = get_object_or_404(Category, food_names__iexact=name)
    items, filter_state, applied_filters = apply_item_filters(
        Items.objects.select_related("category").filter(category=category_obj),
        request.GET,
    )
    return render(
        request,
        "item_view.html",
        {
            "category": category_obj,
            "items": items,
            "filter_state": filter_state,
            "applied_filters": applied_filters,
        },
    )


def productdetail(request, cname, pname):
    category_obj = get_object_or_404(Category, food_names__iexact=cname)
    item = get_object_or_404(Items.objects.select_related("category"), category=category_obj, name__iexact=pname)
    if request.user.is_authenticated:
        track_activity(request.user, item, "view")

    context = {
        "item": item,
        "similar_items": Items.objects.select_related("category").filter(category=item.category).exclude(id=item.id)[:4],
        "recommended_items": get_recommended_items(
            request.user if request.user.is_authenticated else None,
            exclude_item_id=item.id,
            limit=4,
        ),
        "delivery_zone_count": _active_zones().count(),
    }
    return render(request, "product_detail.html", context)


def add_to_cart(request):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if not request.user.is_authenticated:
            return JsonResponse({"status": "Please login to add items to your cart."}, status=200)
        try:
            data = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"status": "Invalid request payload."}, status=400)

        product_id = data.get("product_id")
        product_qty = int(data.get("product_qty", 1) or 1)
    else:
        if request.method != "GET":
            return JsonResponse({"status": "Invalid access."}, status=400)
        if not request.user.is_authenticated:
            messages.error(request, "Please login to add items to your cart.")
            return redirect("Login")
        product_id = request.GET.get("product_id")
        product_qty = int(request.GET.get("product_qty", 1) or 1)

    if product_qty <= 0:
        response = {"status": "Quantity should be at least 1."}
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(response, status=200)
        messages.error(request, response["status"])
        return redirect("Home")

    product = get_object_or_404(Items, id=product_id)
    if product.quantity < product_qty:
        response = {"status": "Product stock not available for that quantity."}
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(response, status=200)
        messages.error(request, response["status"])
        return redirect("Product_detail", cname=product.category.food_names, pname=product.name)

    cart_item, created = Cart.objects.get_or_create(
        user=request.user,
        product=product,
        defaults={"product_qty": product_qty},
    )
    if not created:
        cart_item.product_qty = product_qty
        cart_item.save(update_fields=["product_qty"])

    response = {"status": "Product added to cart." if created else "Product quantity updated in cart."}
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(response, status=200)
    messages.success(request, response["status"])
    return redirect("Cart")


@login_required(login_url="Login")
def cart_page(request):
    cart_items = _cart_items_for(request.user)
    coupon = get_coupon_from_session(request)
    totals = calculate_cart_totals(cart_items, coupon)
    if coupon and not totals["coupon"]:
        clear_coupon_session(request)
        messages.warning(request, totals["coupon_error"])
    return render(
        request,
        "cart.html",
        {
            "cart_items": cart_items,
            "coupon": totals["coupon"],
            "subtotal_amount": totals["subtotal"],
            "discount_amount": totals["discount"],
            "total_amount": totals["final_total"],
        },
    )


@login_required(login_url="Login")
@require_POST
def apply_coupon(request):
    cart_items = _cart_items_for(request.user)
    if not cart_items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect("Cart")

    code = request.POST.get("coupon_code", "").strip().upper()
    if not code:
        messages.error(request, "Enter a coupon code.")
        return redirect("Cart")

    coupon = Coupon.objects.filter(code__iexact=code, active=True).first()
    if not coupon:
        messages.error(request, "Coupon not found.")
        return redirect("Cart")

    totals = calculate_cart_totals(cart_items, coupon)
    if totals["coupon"]:
        request.session["coupon_code"] = coupon.code
        messages.success(request, f"Coupon {coupon.code} applied successfully.")
    else:
        messages.error(request, totals["coupon_error"])
    return redirect("Cart")


@login_required(login_url="Login")
@require_POST
def remove_coupon(request):
    clear_coupon_session(request)
    messages.info(request, "Coupon removed from cart.")
    return redirect("Cart")


@login_required(login_url="Login")
def remove_cart(request, Cartid):
    cart_item = get_object_or_404(Cart, id=Cartid, user=request.user)
    cart_item.delete()
    messages.success(request, "Item removed from cart.")
    return redirect("Cart")


def add_to_fav(request):
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        return JsonResponse({"status": "Invalid access."}, status=400)
    if not request.user.is_authenticated:
        return JsonResponse({"status": "Please login to add items to your wishlist."}, status=200)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"status": "Invalid request payload."}, status=400)

    product = get_object_or_404(Items, id=data.get("product_id"))
    favourite, created = Favourite.objects.get_or_create(user=request.user, product=product)
    if created:
        return JsonResponse({"status": "Product added to wishlist."}, status=200)
    return JsonResponse({"status": "Product already in wishlist."}, status=200)


@login_required(login_url="Login")
def favourite_page(request):
    fav_items = Favourite.objects.filter(user=request.user).select_related("product", "product__category")
    return render(request, "favourite.html", {"fav_items": fav_items})


@login_required(login_url="Login")
def remove_fav(request, favid):
    fav_item = get_object_or_404(Favourite, id=favid, user=request.user)
    fav_item.delete()
    messages.success(request, "Item removed from wishlist.")
    return redirect("Favourite")


@login_required(login_url="Login")
def checkout(request):
    cart_items = _cart_items_for(request.user)
    if not cart_items.exists():
        messages.warning(request, "Your cart is empty. Please add items before checkout.")
        return redirect("Category")

    coupon = get_coupon_from_session(request)
    totals = calculate_cart_totals(cart_items, coupon)
    if coupon and not totals["coupon"]:
        clear_coupon_session(request)
        messages.warning(request, totals["coupon_error"])

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    zones = _active_zones()

    if request.method == "POST":
        address = request.POST.get("address", "").strip()
        pincode = request.POST.get("pincode", "").strip()
        payment_method = request.POST.get("payment_method", "").strip()
        delivery_slot = request.POST.get("delivery_slot", Order.NOW)
        scheduled_for_raw = request.POST.get("scheduled_for", "").strip()
        location_lat = _parse_optional_float(request.POST.get("location_lat"))
        location_lng = _parse_optional_float(request.POST.get("location_lng"))

        if not address or not pincode or not payment_method:
            messages.error(request, "Please complete the delivery and payment details.")
            return redirect("Checkout")

        try:
            scheduled_for = _parse_scheduled_datetime(scheduled_for_raw) if delivery_slot == Order.LATER else None
        except ValueError:
            messages.error(request, "Please choose a valid delivery time.")
            return redirect("Checkout")

        if delivery_slot == Order.LATER:
            if not scheduled_for:
                messages.error(request, "Choose a delivery date and time for later delivery.")
                return redirect("Checkout")
            if scheduled_for <= timezone.now():
                messages.error(request, "Delivery time must be in the future.")
                return redirect("Checkout")

        zone = zones.filter(pincode=pincode).first()
        if zones.exists() and not zone:
            messages.error(request, "Delivery is not available for this pincode yet.")
            return redirect("Checkout")

        signature = build_checkout_signature(
            cart_items,
            address,
            pincode,
            payment_method,
            delivery_slot,
            scheduled_for,
        )
        last_signature = request.session.get("last_checkout_signature")
        last_order_id = request.session.get("last_order_id")
        last_checkout_at = request.session.get("last_checkout_at")
        if last_signature and last_signature == signature and last_order_id and last_checkout_at:
            elapsed = timezone.now().timestamp() - float(last_checkout_at)
            if elapsed < 300:
                existing_order = Order.objects.filter(id=last_order_id, user=request.user).first()
                if existing_order:
                    messages.warning(request, "We blocked a duplicate order and reopened your last checkout.")
                    return redirect("order_detail", order_id=existing_order.id)

        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                coupon=totals["coupon"],
                subtotal_amount=totals["subtotal"],
                discount_amount=totals["discount"],
                total_amount=totals["final_total"],
                delivery_slot=delivery_slot,
                scheduled_for=scheduled_for,
                status="Pending",
            )

            for cart_item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    item=cart_item.product,
                    quantity=cart_item.product_qty,
                    price=cart_item.product.offer_price,
                )
                track_activity(request.user, cart_item.product, "order")

            Delivery.objects.create(
                order=order,
                delivery_zone=zone,
                address=address,
                pincode=pincode,
                location_lat=location_lat,
                location_lng=location_lng,
                estimated_time=estimate_delivery_time(delivery_slot, scheduled_for),
                delivery_status="Preparing",
            )

            Payment.objects.create(order=order, method=payment_method, status="Pending")
            ensure_invoice(order)
            create_notification(
                request.user,
                "Order placed",
                f"Your order #{order.id} has been placed successfully.",
                reverse("order_detail", args=[order.id]),
            )

            profile.default_address = address
            profile.pincode = pincode
            profile.save(update_fields=["default_address", "pincode"])
            cart_items.delete()

        clear_coupon_session(request)
        request.session["last_checkout_signature"] = signature
        request.session["last_order_id"] = order.id
        request.session["last_checkout_at"] = timezone.now().timestamp()
        messages.success(request, f"Order placed successfully! Order ID: {order.id}")
        return redirect("order_detail", order_id=order.id)

    return render(
        request,
        "checkout.html",
        {
            "cart_items": cart_items,
            "coupon": totals["coupon"],
            "subtotal_amount": totals["subtotal"],
            "discount_amount": totals["discount"],
            "total_amount": totals["final_total"],
            "payment_methods": Payment.PAYMENT_METHOD_CHOICES,
            "profile": profile,
            "delivery_slots": Order.DELIVERY_SLOT_CHOICES,
            "zones": zones,
        },
    )


@login_required(login_url="Login")
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("delivery", "payment", "invoice", "coupon"),
        id=order_id,
        user=request.user,
    )
    invoice = ensure_invoice(order)
    Notification.objects.filter(user=request.user, link=reverse("order_detail", args=[order.id])).update(is_read=True)
    return render(
        request,
        "order_detail.html",
        {
            "order": order,
            "order_items": order.order_items.select_related("item"),
            "delivery": order.delivery,
            "payment": order.payment,
            "invoice": invoice,
        },
    )


@login_required(login_url="Login")
def order_tracking(request):
    orders = Order.objects.filter(user=request.user).select_related("invoice", "delivery", "payment")
    return render(request, "order_tracking.html", {"orders": orders})


@login_required(login_url="Login")
def delivery_tracking(request, order_id):
    order = get_object_or_404(Order.objects.select_related("delivery"), id=order_id, user=request.user)
    Notification.objects.filter(user=request.user, link=reverse("delivery_tracking", args=[order.id])).update(is_read=True)
    return render(request, "delivery_tracking.html", {"order": order, "delivery": order.delivery})


@login_required(login_url="Login")
def payment_page(request, order_id):
    order = get_object_or_404(Order.objects.select_related("payment"), id=order_id, user=request.user)
    payment = order.payment

    if request.method == "POST" and order.status != "Cancelled":
        payment.status = "Completed"
        if payment.method != "Cash on Delivery":
            payment.transaction_id = f"TXN-{timezone.now():%Y%m%d%H%M%S}-{order.id}"
        payment.save()
        order.status = "Confirmed"
        order.save(update_fields=["status"])
        messages.success(request, "Payment processed successfully.")
        return redirect("order_detail", order_id=order.id)

    return render(request, "payment.html", {"order": order, "payment": payment})


@login_required(login_url="Login")
@require_POST
def cancel_order(request, order_id):
    order = get_object_or_404(Order.objects.select_related("delivery", "payment"), id=order_id, user=request.user)
    if order.status != "Pending":
        messages.warning(request, "Only pending orders can be cancelled.")
        return redirect("order_detail", order_id=order.id)

    order.status = "Cancelled"
    order.save(update_fields=["status"])
    order.delivery.delivery_status = "Cancelled"
    order.delivery.save(update_fields=["delivery_status"])
    if order.payment.status == "Pending":
        order.payment.status = "Failed"
        order.payment.save(update_fields=["status"])

    messages.success(request, f"Order #{order.id} has been cancelled.")
    return redirect("order_tracking")


def search_items(request):
    query = request.GET.get("q", "").strip()
    queryset = Items.objects.select_related("category")
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(item_description__icontains=query)
            | Q(category__food_names__icontains=query)
        )
    else:
        queryset = queryset.none()

    items, filter_state, applied_filters = apply_item_filters(queryset, request.GET)
    return render(
        request,
        "search_results.html",
        {
            "query": query,
            "items": items,
            "filter_state": filter_state,
            "applied_filters": applied_filters,
        },
    )


def filter_by_veg_nonveg(request, category_type):
    if category_type not in ["Veg", "Non-Veg", "Snacks"]:
        messages.error(request, "Invalid category type.")
        return redirect("Home")

    params = request.GET.copy()
    params["veg"] = category_type
    items, filter_state, applied_filters = apply_item_filters(Items.objects.select_related("category"), params)
    filter_state["veg"] = category_type
    return render(
        request,
        "food_list.html",
        {
            "items": items,
            "category_type": category_type,
            "filter_state": filter_state,
            "applied_filters": applied_filters,
        },
    )


@login_required(login_url="Login")
def invoice_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("delivery", "payment", "coupon", "invoice"),
        id=order_id,
        user=request.user,
    )
    invoice = ensure_invoice(order)
    return render(
        request,
        "invoice.html",
        {
            "order": order,
            "order_items": order.order_items.select_related("item"),
            "invoice": invoice,
            "delivery": order.delivery,
            "payment": order.payment,
        },
    )


@login_required(login_url="Login")
def download_invoice_pdf(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    invoice = ensure_invoice(order)
    pdf_content = build_invoice_pdf(invoice)
    response = HttpResponse(pdf_content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{invoice.invoice_number}.pdf"'
    return response


@login_required(login_url="Login")
def profile_page(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip().lower()

        if not email:
            messages.error(request, "Email is required.")
            return redirect("profile")
        if User.objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists():
            messages.error(request, "This email is already used by another account.")
            return redirect("profile")

        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.email = email
        request.user.save(update_fields=["first_name", "last_name", "email"])

        profile.phone_number = request.POST.get("phone_number", "").strip()
        profile.default_address = request.POST.get("default_address", "").strip()
        profile.pincode = request.POST.get("pincode", "").strip()
        profile.save()

        messages.success(request, "Profile updated successfully.")
        return redirect("profile")

    orders = Order.objects.filter(user=request.user).select_related("invoice", "payment", "delivery")
    return render(
        request,
        "profile.html",
        {
            "profile": profile,
            "orders": orders[:8],
            "invoices": [order.invoice for order in orders if hasattr(order, "invoice")],
            "recommended_items": get_recommended_items(request.user, limit=4),
        },
    )


@login_required(login_url="Login")
def notifications_page(request):
    notifications = Notification.objects.filter(user=request.user)
    return render(request, "notifications.html", {"notifications": notifications})


@login_required(login_url="Login")
@require_POST
def mark_all_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, "Notifications marked as read.")
    return redirect(request.POST.get("next") or "notifications")


@login_required(login_url="Login")
@require_GET
def notifications_json(request):
    notifications = Notification.objects.filter(user=request.user).order_by("-created_at")[:5]
    data = [
        {
            "title": notification.title,
            "message": notification.message,
            "link": notification.link,
            "is_read": notification.is_read,
            "created_at": timezone.localtime(notification.created_at).strftime("%d %b %I:%M %p"),
        }
        for notification in notifications
    ]
    return JsonResponse(
        {
            "count": Notification.objects.filter(user=request.user, is_read=False).count(),
            "notifications": data,
        }
    )


@require_GET
def delivery_availability(request):
    pincode = request.GET.get("pincode", "").strip()
    zones = _active_zones()
    if not pincode:
        return JsonResponse({"available": False, "message": "Enter a pincode to check delivery."})
    if not zones.exists():
        return JsonResponse({"available": True, "message": "Delivery zones are open for all pincodes right now."})

    zone = zones.filter(pincode=pincode).first()
    if zone:
        return JsonResponse({"available": True, "message": f"Delivery is available in {zone.area_name}."})
    return JsonResponse({"available": False, "message": "Sorry, delivery is not available for this pincode yet."})


@staff_member_required
def analytics_dashboard(request):
    valid_orders = Order.objects.exclude(status="Cancelled")
    revenue = valid_orders.aggregate(total=Sum("total_amount"))["total"] or 0
    line_total = ExpressionWrapper(F("quantity") * F("price"), output_field=FloatField())
    top_items = list(
        OrderItem.objects.exclude(order__status="Cancelled")
        .values("item__name")
        .annotate(total_qty=Sum("quantity"), revenue=Sum(line_total))
        .order_by("-total_qty", "-revenue")[:5]
    )

    last_seven_days = [timezone.localdate() - timedelta(days=offset) for offset in range(6, -1, -1)]
    sales_lookup = {
        row["day"]: row["total"]
        for row in valid_orders.annotate(day=TruncDate("created_at")).values("day").annotate(total=Sum("total_amount"))
    }
    daily_sales = [
        {"label": day.strftime("%d %b"), "value": round(float(sales_lookup.get(day, 0) or 0), 2)}
        for day in last_seven_days
    ]

    return render(
        request,
        "analytics_dashboard.html",
        {
            "total_orders": valid_orders.count(),
            "revenue": revenue,
            "top_items": top_items,
            "daily_sales": daily_sales,
        },
    )

