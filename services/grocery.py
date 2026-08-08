"""Static grocery data service used by the first UI prototype."""

ITEMS = [
    {"name": "Bananas", "store": "Fresh Market", "quantity": 1, "added": "Aug 1, 2026"},
    {"name": "Brown rice", "store": "Superstore", "quantity": 1, "added": "Jul 28, 2026"},
    {"name": "Dish soap", "store": "Walmart", "quantity": 0, "added": "Jul 19, 2026"},
    {"name": "Eggs", "store": "Costco", "quantity": 3, "added": "Jul 15, 2026"},
    {"name": "Milk", "store": "Costco", "quantity": 0, "added": "Jul 12, 2026"},
]

STORE_NEEDS = [
    {"name": "Costco", "count": 8, "percent": 37},
    {"name": "Fresh Market", "count": 6, "percent": 28},
    {"name": "Superstore", "count": 5, "percent": 23},
    {"name": "Walmart", "count": 3, "percent": 12},
]


def status_for(quantity: int) -> tuple[str, str]:
    if quantity == 0:
        return "Out", "out"
    if quantity <= 1:
        return "Low", "low"
    return "In stock", "stock"


def inventory_items() -> list[dict]:
    return [{**item, "status": status_for(item["quantity"])} for item in ITEMS]


def dashboard_data() -> dict:
    return {
        "stats": [("Inventory items", 86), ("Low stock", 14), ("Out of stock", 6), ("Stores", 4)],
        "items": inventory_items()[:4],
        "stores": STORE_NEEDS,
    }


def grocery_lists() -> list[dict]:
    return [
        {"name": "Costco", "count": 8, "items": [("Milk", 0), ("Eggs", 1), ("Greek yogurt", 1)]},
        {"name": "Fresh Market", "count": 6, "items": [("Bananas", 1), ("Spinach", 0), ("Tomatoes", 1)]},
    ]
