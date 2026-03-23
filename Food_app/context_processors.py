from .models import Cart, Notification


def shared_state(request):
    if not request.user.is_authenticated:
        return {
            "cart_count": 0,
            "unread_notifications_count": 0,
            "recent_notifications": [],
        }

    recent_notifications = Notification.objects.filter(user=request.user).order_by("-created_at")[:5]
    unread_notifications_count = Notification.objects.filter(user=request.user, is_read=False).count()
    cart_count = Cart.objects.filter(user=request.user).count()
    return {
        "cart_count": cart_count,
        "unread_notifications_count": unread_notifications_count,
        "recent_notifications": recent_notifications,
    }
