from django.core.management.base import BaseCommand

from Food_app.models import Category, Items


DEMO_MENU = [
    {
        "food_names": "South Indian Specials",
        "image": "/static/Images/img1.jpeg",
        "description": "Comforting breakfast classics, dosa varieties, and hearty tiffin favorites.",
        "items": [
            {
                "name": "Masala Dosa",
                "item_description": "Crispy golden dosa filled with spiced potato masala and served with chutney flavors.",
                "price": 120,
                "offer_price": 95,
                "quantity": 40,
                "item_image": "/static/Images/img1.jpeg",
                "veg_non_veg": "Veg",
                "underrated_item": True,
                "new_added_item": True,
            },
            {
                "name": "Mini Idli Sambar",
                "item_description": "Soft mini idlis soaked in hot sambar for a cozy and filling meal.",
                "price": 110,
                "offer_price": 89,
                "quantity": 35,
                "item_image": "/static/Images/img2.jpg",
                "veg_non_veg": "Veg",
                "underrated_item": True,
                "new_added_item": False,
            },
        ],
    },
    {
        "food_names": "Street Food Hits",
        "image": "/static/Images/img3.jpeg",
        "description": "Crowd-favorite chaat, sandwiches, and snack-time cravings made fresh to order.",
        "items": [
            {
                "name": "Paneer Kathi Roll",
                "item_description": "Loaded roll with smoky paneer, onions, mint chutney, and soft flaky wrap.",
                "price": 150,
                "offer_price": 125,
                "quantity": 30,
                "item_image": "/static/Images/img3.jpeg",
                "veg_non_veg": "Veg",
                "underrated_item": False,
                "new_added_item": True,
            },
            {
                "name": "Crispy Veg Burger",
                "item_description": "Crunchy veggie patty burger stacked with lettuce, tomato, and house sauce.",
                "price": 140,
                "offer_price": 109,
                "quantity": 28,
                "item_image": "/static/Images/img4.jpg",
                "veg_non_veg": "Snacks",
                "underrated_item": True,
                "new_added_item": False,
            },
        ],
    },
    {
        "food_names": "Chef's Chicken Corner",
        "image": "/static/Images/img5.jpeg",
        "description": "Popular non-veg picks featuring grilled, fried, and saucy chicken favorites.",
        "items": [
            {
                "name": "Chicken Fried Rice",
                "item_description": "Wok-tossed basmati rice with juicy chicken, vegetables, and savory seasoning.",
                "price": 220,
                "offer_price": 185,
                "quantity": 26,
                "item_image": "/static/Images/img5.jpeg",
                "veg_non_veg": "Non-Veg",
                "underrated_item": True,
                "new_added_item": True,
            },
            {
                "name": "Pepper Chicken Bowl",
                "item_description": "Spicy pepper chicken served with seasoned rice for a bold lunch combo.",
                "price": 240,
                "offer_price": 199,
                "quantity": 24,
                "item_image": "/static/Images/img6.jpg",
                "veg_non_veg": "Non-Veg",
                "underrated_item": False,
                "new_added_item": True,
            },
        ],
    },
    {
        "food_names": "Bakery and Beverages",
        "image": "/static/Images/img7.jpg",
        "description": "Quick bites, sweets, and cool drinks for easy add-ons and evening cravings.",
        "items": [
            {
                "name": "Cold Coffee Float",
                "item_description": "Chilled coffee topped with creamy foam for a refreshing afternoon treat.",
                "price": 130,
                "offer_price": 99,
                "quantity": 25,
                "item_image": "/static/Images/img7.jpg",
                "veg_non_veg": "Snacks",
                "underrated_item": False,
                "new_added_item": True,
            },
            {
                "name": "Chocolate Muffin",
                "item_description": "Moist bakery-style chocolate muffin with rich cocoa flavor in every bite.",
                "price": 90,
                "offer_price": 69,
                "quantity": 32,
                "item_image": "/static/Images/img8.jpg",
                "veg_non_veg": "Snacks",
                "underrated_item": True,
                "new_added_item": False,
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Seed demo categories and food items for local development."

    def handle(self, *args, **options):
        category_count = 0
        item_count = 0

        for category_data in DEMO_MENU:
            items_data = category_data.pop("items")
            category, created = Category.objects.get_or_create(
                food_names=category_data["food_names"],
                defaults=category_data,
            )
            if not created:
                for field, value in category_data.items():
                    setattr(category, field, value)
                category.save()
            category_count += 1

            for item_data in items_data:
                _, item_created = Items.objects.update_or_create(
                    category=category,
                    name=item_data["name"],
                    defaults=item_data,
                )
                if item_created:
                    item_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo menu ready: {category_count} categories available and {Items.objects.count()} total items."
            )
        )
