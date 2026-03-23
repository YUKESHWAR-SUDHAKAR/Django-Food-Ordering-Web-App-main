from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Category(models.Model):
    food_names = models.CharField(max_length=200)
    image = models.CharField(max_length=3000, null=True, blank=True)
    image_upload = models.FileField(upload_to="category_images/", null=True, blank=True)
    description = models.TextField(max_length=1000)

    class Meta:
        ordering = ["food_names"]

    def __str__(self):
        return self.food_names

    @property
    def display_image(self):
        if self.image_upload:
            return self.image_upload.url
        if self.image:
            return self.image
        return "https://via.placeholder.com/320x220?text=Category"


class Items(models.Model):
    VEG_NON_VEG_CHOICES = [
        ("Veg", "Veg"),
        ("Non-Veg", "Non-Veg"),
        ("Snacks", "Snacks"),
    ]

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=400)
    item_description = models.TextField(max_length=1000)
    price = models.FloatField()
    offer_price = models.FloatField()
    item_image = models.CharField(max_length=3000, null=True, blank=True)
    image_upload = models.FileField(upload_to="food_images/", null=True, blank=True)
    quantity = models.IntegerField()
    underrated_item = models.BooleanField(default=False)
    new_added_item = models.BooleanField(default=False)
    veg_non_veg = models.CharField(max_length=10, choices=VEG_NON_VEG_CHOICES, default="Veg")
    rating = models.FloatField(default=4.0)

    class Meta:
        ordering = ["-new_added_item", "-rating", "name"]

    def __str__(self):
        return self.name

    @property
    def display_image(self):
        if self.image_upload:
            return self.image_upload.url
        if self.item_image:
            return self.item_image
        return "https://via.placeholder.com/320x220?text=Food+Image"

    @property
    def rating_percentage(self):
        return max(0, min((self.rating / 5) * 100, 100))


class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cart_items")
    product = models.ForeignKey(Items, on_delete=models.CASCADE, related_name="cart_entries")
    product_qty = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def total_price(self):
        return round(self.product_qty * self.product.offer_price, 2)


class Favourite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favourites")
    product = models.ForeignKey(Items, on_delete=models.CASCADE, related_name="favourited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} likes {self.product.name}"


class Coupon(models.Model):
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    DISCOUNT_TYPE_CHOICES = [
        (PERCENTAGE, "Percentage"),
        (FIXED, "Flat Amount"),
    ]

    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default=PERCENTAGE)
    discount_value = models.FloatField()
    expiry_date = models.DateField()
    minimum_order_amount = models.FloatField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["expiry_date", "code"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.upper().strip()
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return self.expiry_date < timezone.localdate()

    def is_valid_for_total(self, total_amount):
        if not self.active:
            return False, "This coupon is currently inactive."
        if self.is_expired:
            return False, "This coupon has expired."
        if total_amount < self.minimum_order_amount:
            return False, f"Coupon works only for orders above Rs. {self.minimum_order_amount:.2f}."
        return True, ""

    def calculate_discount(self, total_amount):
        if self.discount_type == self.PERCENTAGE:
            discount = total_amount * (self.discount_value / 100)
        else:
            discount = self.discount_value
        return round(min(discount, total_amount), 2)


class Order(models.Model):
    NOW = "Now"
    LATER = "Later"
    DELIVERY_SLOT_CHOICES = [
        (NOW, "Now"),
        (LATER, "Later"),
    ]
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Confirmed", "Confirmed"),
        ("Delivered", "Delivered"),
        ("Cancelled", "Cancelled"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    items = models.ManyToManyField(Items, through="OrderItem")
    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL)
    subtotal_amount = models.FloatField(default=0)
    discount_amount = models.FloatField(default=0)
    total_amount = models.FloatField()
    delivery_slot = models.CharField(max_length=10, choices=DELIVERY_SLOT_CHOICES, default=NOW)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order {self.id} by {self.user.username}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="order_items")
    item = models.ForeignKey(Items, on_delete=models.CASCADE, related_name="ordered_items")
    quantity = models.IntegerField()
    price = models.FloatField()

    @property
    def line_total(self):
        return round(self.quantity * self.price, 2)

    def __str__(self):
        return f"{self.quantity} x {self.item.name}"


class DeliveryZone(models.Model):
    area_name = models.CharField(max_length=120)
    pincode = models.CharField(max_length=10, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["pincode"]

    def __str__(self):
        return f"{self.area_name} ({self.pincode})"


class Delivery(models.Model):
    STATUS_CHOICES = [
        ("Preparing", "Preparing"),
        ("Out for Delivery", "Out for Delivery"),
        ("Delivered", "Delivered"),
        ("Cancelled", "Cancelled"),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="delivery")
    delivery_zone = models.ForeignKey(DeliveryZone, null=True, blank=True, on_delete=models.SET_NULL)
    address = models.TextField()
    pincode = models.CharField(max_length=10, blank=True)
    delivery_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Preparing")
    location_lat = models.FloatField(null=True, blank=True)
    location_lng = models.FloatField(null=True, blank=True)
    estimated_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Delivery for Order {self.order.id}"


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ("Cash on Delivery", "Cash on Delivery"),
        ("Credit Card", "Credit Card"),
        ("Debit Card", "Debit Card"),
        ("UPI", "UPI"),
        ("Net Banking", "Net Banking"),
    ]
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Completed", "Completed"),
        ("Failed", "Failed"),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="payment")
    method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    transaction_id = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"Payment for Order {self.order.id}"


class Invoice(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="invoice")
    invoice_number = models.CharField(max_length=40, unique=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return self.invoice_number

    def save(self, *args, **kwargs):
        if not self.invoice_number and self.order_id:
            self.invoice_number = f"INV-{timezone.localdate():%Y%m%d}-{self.order_id:04d}"
        super().save(*args, **kwargs)


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=150)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} for {self.user.username}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone_number = models.CharField(max_length=20, blank=True)
    default_address = models.TextField(blank=True)
    pincode = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return f"Profile for {self.user.username}"


class UserActivity(models.Model):
    VIEW = "view"
    ORDER = "order"
    ACTIVITY_TYPES = [
        (VIEW, "Viewed"),
        (ORDER, "Ordered"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="activities")
    item = models.ForeignKey(Items, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} {self.activity_type} {self.item.name}"
