from django.contrib import admin

from .models import (
    Cart,
    Category,
    Coupon,
    Delivery,
    DeliveryZone,
    Favourite,
    Invoice,
    Items,
    Notification,
    Order,
    OrderItem,
    Payment,
    UserActivity,
    UserProfile,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("food_names", "description")
    search_fields = ("food_names",)


@admin.register(Items)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "veg_non_veg", "offer_price", "rating", "quantity")
    list_filter = ("category", "veg_non_veg", "new_added_item", "underrated_item")
    search_fields = ("name", "item_description")


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "discount_type", "discount_value", "expiry_date", "minimum_order_amount", "active")
    list_filter = ("discount_type", "active", "expiry_date")
    search_fields = ("code",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "subtotal_amount", "discount_amount", "total_amount", "created_at")
    list_filter = ("status", "delivery_slot", "created_at")
    search_fields = ("user__username", "id")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "item", "quantity", "price")


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ("order", "pincode", "delivery_zone", "delivery_status", "estimated_time")
    list_filter = ("delivery_status", "delivery_zone")
    search_fields = ("order__id", "pincode", "address")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "method", "status", "transaction_id")
    list_filter = ("method", "status")
    search_fields = ("transaction_id", "order__id")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "order", "generated_at")
    search_fields = ("invoice_number", "order__id", "order__user__username")


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ("area_name", "pincode", "is_active")
    list_filter = ("is_active",)
    search_fields = ("area_name", "pincode")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("user__username", "title", "message")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone_number", "pincode")
    search_fields = ("user__username", "user__email", "phone_number", "pincode")


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ("user", "item", "activity_type", "created_at")
    list_filter = ("activity_type", "created_at")
    search_fields = ("user__username", "item__name")


admin.site.register(Cart)
admin.site.register(Favourite)
