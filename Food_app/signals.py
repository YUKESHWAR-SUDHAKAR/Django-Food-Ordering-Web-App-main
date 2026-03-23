from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

from .models import Delivery, Notification, Order, Payment, UserProfile


@receiver(post_save, sender=User)
def create_profile_for_user(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


def _attach_previous_value(instance, model, field_name):
    if not instance.pk:
        return
    previous = model.objects.filter(pk=instance.pk).values(field_name).first()
    if previous:
        setattr(instance, f"_previous_{field_name}", previous[field_name])


def _notify_status_change(user, title, message, link):
    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        link=link,
    )


@receiver(pre_save, sender=Order)
def capture_previous_order_status(sender, instance, **kwargs):
    _attach_previous_value(instance, sender, "status")


@receiver(post_save, sender=Order)
def notify_order_status_update(sender, instance, created, **kwargs):
    if created:
        return
    previous_status = getattr(instance, "_previous_status", None)
    if previous_status and previous_status != instance.status:
        _notify_status_change(
            instance.user,
            "Order status updated",
            f"Order #{instance.id} is now {instance.status}.",
            reverse("order_detail", args=[instance.id]),
        )


@receiver(pre_save, sender=Delivery)
def capture_previous_delivery_status(sender, instance, **kwargs):
    _attach_previous_value(instance, sender, "delivery_status")


@receiver(post_save, sender=Delivery)
def notify_delivery_status_update(sender, instance, created, **kwargs):
    if created:
        return
    previous_status = getattr(instance, "_previous_delivery_status", None)
    if previous_status and previous_status != instance.delivery_status:
        _notify_status_change(
            instance.order.user,
            "Delivery update",
            f"Delivery for order #{instance.order.id} is now {instance.delivery_status}.",
            reverse("delivery_tracking", args=[instance.order.id]),
        )


@receiver(pre_save, sender=Payment)
def capture_previous_payment_status(sender, instance, **kwargs):
    _attach_previous_value(instance, sender, "status")


@receiver(post_save, sender=Payment)
def notify_payment_status_update(sender, instance, created, **kwargs):
    if created:
        return
    previous_status = getattr(instance, "_previous_status", None)
    if previous_status and previous_status != instance.status:
        _notify_status_change(
            instance.order.user,
            "Payment update",
            f"Payment for order #{instance.order.id} is now {instance.status}.",
            reverse("payment", args=[instance.order.id]),
        )
