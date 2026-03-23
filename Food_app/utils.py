import hashlib
import json
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from .models import Coupon, Invoice, Items, Notification, Order, UserActivity


def create_notification(user, title, message, link=""):
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        link=link,
    )


def get_coupon_from_session(request):
    coupon_code = request.session.get("coupon_code")
    if not coupon_code:
        return None
    return Coupon.objects.filter(code__iexact=coupon_code, active=True).first()


def clear_coupon_session(request):
    request.session.pop("coupon_code", None)
    request.session.modified = True


def calculate_cart_totals(cart_items, coupon=None):
    subtotal = round(sum(item.total_price for item in cart_items), 2)
    applied_coupon = None
    discount = 0.0
    coupon_error = ""
    if coupon:
        is_valid, coupon_error = coupon.is_valid_for_total(subtotal)
        if is_valid:
            applied_coupon = coupon
            discount = coupon.calculate_discount(subtotal)
    final_total = round(max(subtotal - discount, 0), 2)
    return {
        "subtotal": subtotal,
        "discount": discount,
        "final_total": final_total,
        "coupon": applied_coupon,
        "coupon_error": coupon_error,
    }


def estimate_delivery_time(delivery_slot, scheduled_for=None):
    if delivery_slot == Order.LATER and scheduled_for:
        return scheduled_for
    return timezone.now() + timedelta(minutes=45)


def build_checkout_signature(cart_items, address, pincode, payment_method, delivery_slot, scheduled_for):
    payload = {
        "items": sorted(
            [{"id": item.product_id, "qty": item.product_qty} for item in cart_items],
            key=lambda entry: entry["id"],
        ),
        "address": address.strip().lower(),
        "pincode": pincode.strip(),
        "payment_method": payment_method,
        "delivery_slot": delivery_slot,
        "scheduled_for": scheduled_for.isoformat() if scheduled_for else "",
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def track_activity(user, item, activity_type):
    if not user.is_authenticated:
        return
    UserActivity.objects.create(user=user, item=item, activity_type=activity_type)


def get_recommended_items(user, exclude_item_id=None, limit=6):
    queryset = Items.objects.select_related("category")
    if exclude_item_id:
        queryset = queryset.exclude(id=exclude_item_id)

    if user and user.is_authenticated:
        category_ids = list(
            UserActivity.objects.filter(user=user)
            .values("item__category")
            .annotate(score=Count("id"))
            .order_by("-score", "-item__category")
            .values_list("item__category", flat=True)[:5]
        )
        if category_ids:
            recommended = list(
                queryset.filter(category_id__in=category_ids).order_by("-rating", "-new_added_item", "name")[:limit]
            )
            if recommended:
                return recommended

    return list(queryset.order_by("-rating", "-new_added_item", "name")[:limit])


def apply_item_filters(queryset, params):
    selected = {
        "veg": params.get("veg", "").strip(),
        "min_price": params.get("min_price", "").strip(),
        "max_price": params.get("max_price", "").strip(),
        "rating": params.get("rating", "").strip(),
        "sort": params.get("sort", "").strip() or "featured",
    }
    applied_filters = []

    if selected["veg"]:
        queryset = queryset.filter(veg_non_veg=selected["veg"])
        applied_filters.append(selected["veg"])

    if selected["min_price"]:
        try:
            min_price = float(selected["min_price"])
            queryset = queryset.filter(offer_price__gte=min_price)
            applied_filters.append(f"Min Rs. {min_price:.0f}")
        except ValueError:
            selected["min_price"] = ""

    if selected["max_price"]:
        try:
            max_price = float(selected["max_price"])
            queryset = queryset.filter(offer_price__lte=max_price)
            applied_filters.append(f"Max Rs. {max_price:.0f}")
        except ValueError:
            selected["max_price"] = ""

    if selected["rating"]:
        try:
            min_rating = float(selected["rating"])
            queryset = queryset.filter(rating__gte=min_rating)
            applied_filters.append(f"Rating {min_rating:.1f}+")
        except ValueError:
            selected["rating"] = ""

    sort_mapping = {
        "featured": ("-underrated_item", "-rating", "name"),
        "price_asc": ("offer_price", "name"),
        "price_desc": ("-offer_price", "name"),
        "rating": ("-rating", "name"),
        "latest": ("-id", "name"),
    }
    queryset = queryset.order_by(*sort_mapping.get(selected["sort"], sort_mapping["featured"]))
    sort_labels = {
        "featured": "Featured",
        "price_asc": "Price: Low to High",
        "price_desc": "Price: High to Low",
        "rating": "Top Rated",
        "latest": "Newest",
    }
    applied_filters.append(sort_labels.get(selected["sort"], "Featured"))

    return queryset, selected, applied_filters


def get_invoice_lines(invoice):
    order = invoice.order
    lines = [
        f"Invoice Number: {invoice.invoice_number}",
        f"Order ID: {order.id}",
        f"Customer: {order.user.username}",
        f"Created At: {timezone.localtime(order.created_at).strftime('%d %b %Y %I:%M %p')}",
        "",
        "Items:",
    ]
    for order_item in order.order_items.select_related("item").all():
        lines.append(
            f"- {order_item.item.name} | Qty {order_item.quantity} | Rs. {order_item.price:.2f} | Rs. {order_item.line_total:.2f}"
        )

    lines.extend(
        [
            "",
            f"Subtotal: Rs. {order.subtotal_amount:.2f}",
            f"Discount: Rs. {order.discount_amount:.2f}",
            f"Total: Rs. {order.total_amount:.2f}",
        ]
    )
    if hasattr(order, "delivery"):
        lines.extend(
            [
                "",
                f"Address: {order.delivery.address.replace(chr(10), ', ')}",
                f"Pincode: {order.delivery.pincode}",
            ]
        )
    return lines


def _escape_pdf_text(value):
    return (
        value.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .encode("ascii", "replace")
        .decode("ascii")
    )


def build_invoice_pdf(invoice):
    lines = get_invoice_lines(invoice)
    content = ["BT", "/F1 12 Tf", "50 780 Td", "16 TL"]
    first_line = True
    for line in lines:
        if not first_line:
            content.append("T*")
        content.append(f"({_escape_pdf_text(line)}) Tj")
        first_line = False
    content.append("ET")
    stream = "\n".join(content).encode("latin-1")

    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n",
        f"4 0 obj << /Length {len(stream)} >> stream\n".encode("latin-1") + stream + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        (
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF"
        ).encode("latin-1")
    )
    return bytes(pdf)


def ensure_invoice(order):
    invoice, _ = Invoice.objects.get_or_create(order=order)
    return invoice
