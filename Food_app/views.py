from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
import json
from .models import *
from django.contrib import messages
from .form import CustomUserForm
from django.contrib.auth import authenticate, login, logout


# Create your views here.

def home(request):
    # return HttpResponse('<h1>this is the home page</h1>')
    categories = Category.objects.all()
    items = Items.objects.filter(underrated_item=True)
    new_items = Items.objects.filter(new_added_item=True)
    return render(request, 'home.html', {
        'categories': categories,
        'items': items,
        'new_items': new_items,
    })

def login_page(request):
    if request.method == "POST":
        name = request.POST.get('username')
        pwd = request.POST.get('password')
        user = authenticate(request,username=name,password=pwd)
        if user is not None:
            login(request,user)
            messages.success(request,'Logged in successfully.')
        else:
            messages.error(request,'Invalid username or password.')
            return redirect('Login') 
    return render(request,'login.html')

def logout_page(request):
    if request.user.is_authenticated:
        logout(request)
        messages.success(request,'Logged out successfully!')
    return redirect('Login') 

def register(request):
    if request.method == "POST":
        form = CustomUserForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Registration successful! You can now log in.")
            return redirect('Login') 
        else:
            return render(request, 'register.html', {'form': form})
    else:
        form = CustomUserForm()  # Create a new instance of the form

    return render(request, 'register.html', {'form': form})


def category(request):
    categories = Category.objects.all()
    return render(request,'categories.html',{'categories':categories})

def categoryview(request, name):
    # Try to get the category by name
    try:
        category = Category.objects.get(food_names=name)
        
        # Filter items by the category instance
        items = Items.objects.filter(category=category)

        # If there are no items, show a warning message
        if not items:
            messages.warning(request, 'No items found for this category.')

        return render(request, 'item_view.html', {'items': items, 'category': category})

    except Category.DoesNotExist:
        # If the category does not exist, show an error message and redirect
        messages.error(request,"Oops! It seems we couldn't find that category. Please try a different one!")
        return redirect('Category')  # Replace 'homepage' with the URL name you want to redirect to

def productdetail(request, cname, pname):
    try:
        # Check if the category exists
        category = Category.objects.get(food_names=cname)

        # Check if the item exists in the given category
        item = Items.objects.get(name=pname, category=category)

        # If the item is found, render the product details page
        return render(request, 'product_detail.html', {'item': item})

    except Category.DoesNotExist:
        # Handle case where the category does not exist
        messages.error(request, "Oops! It seems we couldn't find that category. Please try a different one!")
        return redirect('Category')  # Replace 'homepage' with your desired redirection

    except Items.DoesNotExist:
        # Handle case where the product does not exist in the specified category
        messages.error(request, 'Oops! It looks like there are no food items in this category. How about exploring other delicious options?')
        return redirect('Category', name=cname)  # Redirect to the category page or another page

def add_to_cart(request):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.user.is_authenticated:
            data = json.load(request)
            product_qty = data['product_qty']
            product_id = data['product_id']
            product_status = Items.objects.get(id=product_id)
            if product_status:
                # in Django's ORM syntax, you can't use dot notation in filter conditions like product.id. Instead, you should use the double underscore __ notation to access the id field of the ForeignKey.
                # "why using double underscore" - use this when you want to filter on other fields of the related model, e.g., product__name or product__price.
                if Cart.objects.filter(user=request.user,product_id=product_id).exists(): 
                    cart_qty_update = Cart.objects.get(user=request.user, product_id=product_id)
                    cart_qty_update.product_qty = product_qty
                    cart_qty_update.save()
                    return JsonResponse({'status':'Product quantity updated in Cart'}, status = 200)
                else:
                    if product_status.quantity >= product_qty:
                        Cart.objects.create(user=request.user,product_id=product_id,product_qty=product_qty )
                        return JsonResponse({'status':'Product added to Cart'}, status = 200)
                    else:
                        return JsonResponse({'status':'Product stock not available'}, status = 200)
        else:
            return JsonResponse({'status':'Please Login to add items to your cart'}, status = 200)
    else:
        # Non-Ajax GET support for quick add
        if request.method == 'GET':
            if request.user.is_authenticated:
                product_id = request.GET.get('product_id')
                product_qty = int(request.GET.get('product_qty', 1))

                if not product_id:
                    messages.error(request, 'No product selected to add to cart.')
                    return redirect('Home')

                try:
                    product_status = Items.objects.get(id=product_id)
                except Items.DoesNotExist:
                    messages.error(request, 'Product not found.')
                    return redirect('Home')

                if Cart.objects.filter(user=request.user, product_id=product_id).exists():
                    cart_qty_update = Cart.objects.get(user=request.user, product_id=product_id)
                    cart_qty_update.product_qty = product_qty
                    cart_qty_update.save()
                    messages.success(request, 'Product quantity updated in cart.')
                else:
                    if product_status.quantity >= product_qty:
                        Cart.objects.create(user=request.user, product_id=product_id, product_qty=product_qty)
                        messages.success(request, 'Product added to cart.')
                    else:
                        messages.error(request, 'Product stock not available.')
                return redirect('Cart')
            else:
                messages.error(request, 'Please login to add items to your cart.')
                return redirect('Login')

        return JsonResponse({'status':'Invalid Access'}, status = 200)

def cart_page(request):
    if request.user.is_authenticated:
        cart_items = Cart.objects.filter(user=request.user)
        total_amount = sum(item.product.offer_price * item.product_qty for item in cart_items)

        context = {
            'cart_items': cart_items,
            'total_amount': total_amount,
        }
        return render(request,'cart.html',{'cart_items':cart_items,'total_amount':total_amount})
    else:
        messages.error(request, 'please login to enter cart page')
        return redirect('Login')

def remove_cart(request,Cartid):
    cart_item = Cart.objects.get(id = Cartid)
    cart_item.delete()
    return redirect('Cart')

def add_to_fav(request):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.user.is_authenticated:
            data = json.load(request)
            product_id = data['product_id']
            product_status = Items.objects.get(id=product_id)
            if product_status:
                # in Django's ORM syntax, you can't use dot notation in filter conditions like product.id. Instead, you should use the double underscore __ notation to access the id field of the ForeignKey.
                # "why using double underscore" - use this when you want to filter on other fields of the related model, e.g., product__name or product__price.
                if Favourite.objects.filter(user=request.user,product_id=product_id).exists(): 
                    return JsonResponse({'status':'Product already in favourite list'}, status = 200)
                else:
                    Favourite.objects.create(user=request.user,product_id=product_id )
                    return JsonResponse({'status':'Product added to favourite list'}, status = 200)
        else:
            return JsonResponse({'status':'Please Login to add items to your cart'}, status = 200)
    else:
        return JsonResponse({'status':'Invalid Access'}, status = 200)

def favourite_page(request):
    if request.user.is_authenticated:
        fav_items = Favourite.objects.filter(user=request.user)
        return render(request,'favourite.html',{'fav_items':fav_items})
    else:
        messages.error(request, 'please login to enter Favourite page')
        return redirect('Login')

def remove_fav(request,favid):
    fav_item = Favourite.objects.get(id = favid)
    fav_item.delete()
    return redirect('Favourite')

# New views for ordering, delivery, and payment features

def checkout(request):
    if request.user.is_authenticated:
        cart_items = Cart.objects.filter(user=request.user)
        if not cart_items.exists():
            messages.warning(request, 'Your cart is empty. Please add items before checkout.')
            return redirect('Category')
        
        total_amount = sum(item.product.offer_price * item.product_qty for item in cart_items)
        
        if request.method == 'POST':
            address = request.POST.get('address', '')
            payment_method = request.POST.get('payment_method', '')
            
            if not address or not payment_method:
                messages.error(request, 'Please fill in all checkout details.')
                return render(request, 'checkout.html', {'cart_items': cart_items, 'total_amount': total_amount})
            
            # Create order
            order = Order.objects.create(
                user=request.user,
                total_amount=total_amount,
                status='Confirmed'
            )
            
            # Add items to order
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    item=item.product,
                    quantity=item.product_qty,
                    price=item.product.offer_price
                )
            
            # Create delivery record
            Delivery.objects.create(
                order=order,
                address=address,
                delivery_status='Preparing'
            )
            
            # Create payment record
            Payment.objects.create(
                order=order,
                method=payment_method,
                status='Pending'
            )
            
            # Clear cart
            cart_items.delete()
            
            messages.success(request, f'Order placed successfully! Order ID: {order.id}')
            return redirect('order_detail', order_id=order.id)
        
        return render(request, 'checkout.html', {'cart_items': cart_items, 'total_amount': total_amount, 'payment_methods': Payment.PAYMENT_METHOD_CHOICES})
    else:
        messages.error(request, 'Please login to checkout')
        return redirect('Login')

def order_detail(request, order_id):
    if request.user.is_authenticated:
        try:
            order = Order.objects.get(id=order_id, user=request.user)
            order_items = OrderItem.objects.filter(order=order)
            delivery = Delivery.objects.get(order=order)
            payment = Payment.objects.get(order=order)
            
            context = {
                'order': order,
                'order_items': order_items,
                'delivery': delivery,
                'payment': payment,
            }
            return render(request, 'order_detail.html', context)
        except Order.DoesNotExist:
            messages.error(request, 'Order not found.')
            return redirect('home')
    else:
        messages.error(request, 'Please login to view order details.')
        return redirect('Login')

def order_tracking(request):
    if request.user.is_authenticated:
        orders = Order.objects.filter(user=request.user).order_by('-created_at')
        context = {'orders': orders}
        return render(request, 'order_tracking.html', context)
    else:
        messages.error(request, 'Please login to track orders.')
        return redirect('Login')

def delivery_tracking(request, order_id):
    if request.user.is_authenticated:
        try:
            order = Order.objects.get(id=order_id, user=request.user)
            delivery = Delivery.objects.get(order=order)
            
            context = {
                'order': order,
                'delivery': delivery,
            }
            return render(request, 'delivery_tracking.html', context)
        except (Order.DoesNotExist, Delivery.DoesNotExist):
            messages.error(request, 'Delivery information not found.')
            return redirect('order_tracking')
    else:
        messages.error(request, 'Please login to track delivery.')
        return redirect('Login')

def payment_page(request, order_id):
    if request.user.is_authenticated:
        try:
            order = Order.objects.get(id=order_id, user=request.user)
            payment = Payment.objects.get(order=order)
            
            if request.method == 'POST':
                # Process payment based on method
                payment_method = payment.method
                
                if payment_method == 'Cash on Delivery':
                    payment.status = 'Completed'
                    payment.save()
                    messages.success(request, 'Payment will be collected at delivery.')
                else:
                    # For other payment methods, this would be handled by payment gateway
                    payment.status = 'Pending'
                    payment.save()
                    messages.info(request, f'Redirecting to {payment_method} payment gateway...')
                
                return redirect('order_detail', order_id=order.id)
            
            context = {
                'order': order,
                'payment': payment,
            }
            return render(request, 'payment.html', context)
        except (Order.DoesNotExist, Payment.DoesNotExist):
            messages.error(request, 'Order or payment information not found.')
            return redirect('order_tracking')
    else:
        messages.error(request, 'Please login to make payment.')
        return redirect('Login')


def cancel_order(request, order_id):
    if not request.user.is_authenticated:
        messages.error(request, 'Please login to cancel an order.')
        return redirect('Login')

    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        messages.error(request, 'Order not found.')
        return redirect('order_tracking')

    if order.status in ['Delivered', 'Cancelled']:
        messages.warning(request, 'This order cannot be cancelled.')
        return redirect('order_detail', order_id=order_id)

    order.status = 'Cancelled'
    order.save()

    delivery = Delivery.objects.filter(order=order).first()
    if delivery:
        delivery.delivery_status = 'Cancelled'
        delivery.save()

    payment = Payment.objects.filter(order=order).first()
    if payment:
        payment.status = 'Failed'
        payment.save()

    messages.success(request, f'Order #{order_id} has been cancelled successfully.')
    return redirect('order_tracking')


def search_items(request):
    query = request.GET.get('q', '').strip()

    if query:
        items = Items.objects.filter(
            Q(name__icontains=query) |
            Q(item_description__icontains=query) |
            Q(category__food_names__icontains=query)
        )
    else:
        items = Items.objects.none()

    context = {
        'query': query,
        'items': items,
    }

    return render(request, 'search_results.html', context)


def filter_by_veg_nonveg(request, category_type):
    """Filter items by Veg, Non-Veg, or Snacks"""
    if category_type in ['Veg', 'Non-Veg', 'Snacks']:
        items = Items.objects.filter(veg_non_veg=category_type)
        context = {
            'items': items,
            'category_type': category_type,
        }
        return render(request, 'food_list.html', context)
    else:
        messages.error(request, 'Invalid category type.')
        return redirect('home')