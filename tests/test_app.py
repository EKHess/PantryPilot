import io
import sqlite3

import pytest

from app import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})
    return app.test_client()


@pytest.mark.parametrize("path, heading", [
    ("/", "Hello"),
    ("/inventory", "Inventory"),
    ("/grocery-lists", "Grocery lists"),
    ("/stores", "Stores"),
    ("/categories", "Categories"),
    ("/settings", "Settings"),
    ("/import", "Import"),
    ("/export", "Export"),
])
def test_pages_render(client, path, heading):
    response = client.get(path)
    assert response.status_code == 200
    assert heading.encode() in response.data


def test_unknown_page_is_not_found(client):
    assert client.get("/missing").status_code == 404


def test_export_downloads_current_database(client):
    client.post("/items", data={"name": "Export me", "store_id": "1", "quantity": "4"})

    response = client.get("/export/download")

    assert response.status_code == 200
    assert response.headers["Content-Disposition"] == 'attachment; filename=pantrypilot-backup.db'
    with sqlite3.connect(":memory:") as restored:
        restored.deserialize(response.data)
        assert restored.execute(
            "SELECT quantity FROM grocery_items WHERE name = 'Export me'"
        ).fetchone() == (4,)


def test_import_replaces_current_pantry(client, tmp_path):
    client.post(
        "/items",
        data={"name": "Current-only item", "store_id": "1", "quantity": "2"},
        follow_redirects=True,
    )
    source = tmp_path / "source.db"
    source_client = create_app({"TESTING": True, "DATABASE": str(source)}).test_client()
    source_client.post("/items", data={"name": "Restored item", "store_id": "1", "quantity": "7"})

    response = client.post(
        "/import",
        data={"database": (io.BytesIO(source.read_bytes()), "backup.db")},
        follow_redirects=True,
    )

    assert b"backup was imported successfully" in response.data
    assert b"Restored item" in response.data
    assert b"Current-only item" not in response.data


@pytest.mark.parametrize(
    "contents,filename,message",
    [
        (b"not sqlite", "backup.db", b"not a compatible PantryPilot database"),
        (b"not sqlite", "backup.txt", b"must have a .db extension"),
    ],
)
def test_import_rejects_invalid_files_without_changing_pantry(client, contents, filename, message):
    response = client.post(
        "/import",
        data={"database": (io.BytesIO(contents), filename)},
        follow_redirects=True,
    )

    assert message in response.data
    assert b"Milk" in client.get("/inventory").data


def test_add_store_persists_and_updates_store_choices(client):
    response = client.post(
        "/stores",
        data={"name": "  Corner   Shop  ", "color": "#AABBCC"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Corner Shop was added." in response.data
    assert b"#aabbcc" in response.data

    inventory = client.get("/inventory")
    assert b'<option value="5">Corner Shop</option>' in inventory.data


@pytest.mark.parametrize(
    "name,color,message",
    [
        ("", "#123456", "Enter a store name."),
        ("A" * 81, "#123456", "Store names must be 80 characters or fewer."),
        ("Valid name", "blue", "Choose a valid store color."),
    ],
)
def test_add_store_rejects_invalid_input(client, name, color, message):
    response = client.post(
        "/stores", data={"name": name, "color": color}, follow_redirects=True
    )

    assert message.encode() in response.data


def test_add_store_rejects_case_insensitive_duplicates(client):
    response = client.post(
        "/stores",
        data={"name": "  cOsTcO ", "color": "#123456"},
        follow_redirects=True,
    )

    assert b"A store with that name already exists." in response.data


def test_edit_store_updates_everywhere_store_is_used(client):
    response = client.post(
        "/stores/1/edit",
        data={"name": "Bulk Club", "color": "#112233"},
        follow_redirects=True,
    )

    assert b"Bulk Club was updated." in response.data
    assert b'data-color="#112233"' in response.data

    for path in ("/", "/inventory", "/grocery-lists"):
        page = client.get(path)
        assert b"Bulk Club" in page.data
        assert b"Costco" not in page.data


def test_edit_store_validates_duplicates_without_matching_itself(client):
    unchanged = client.post(
        "/stores/1/edit",
        data={"name": "costco", "color": "#123456"},
        follow_redirects=True,
    )
    duplicate = client.post(
        "/stores/1/edit",
        data={"name": "Walmart", "color": "#123456"},
        follow_redirects=True,
    )

    assert b"costco was updated." in unchanged.data
    assert b"A store with that name already exists." in duplicate.data


def test_delete_store_removes_it_everywhere_and_does_not_reseed(tmp_path):
    database_path = tmp_path / "delete-test.db"
    app = create_app({"TESTING": True, "DATABASE": str(database_path)})
    client = app.test_client()

    response = client.post("/stores/2/delete", follow_redirects=True)

    assert b"Fresh Market was deleted." in response.data
    for path in ("/", "/inventory", "/grocery-lists"):
        page = client.get(path)
        assert b"Fresh Market" not in page.data
    assert b"Unassigned" in client.get("/inventory").data

    restarted_client = create_app(
        {"TESTING": True, "DATABASE": str(database_path)}
    ).test_client()
    assert b"Fresh Market" not in restarted_client.get("/stores").data


@pytest.mark.parametrize("action", ["edit", "delete"])
def test_modifying_missing_store_is_not_found(client, action):
    data = {"name": "Missing", "color": "#123456"} if action == "edit" else None
    assert client.post(f"/stores/999/{action}", data=data).status_code == 404


def test_add_item_persists_and_uses_item_minimum_status(client):
    response = client.post(
        "/items",
        data={
            "name": "  Oat   milk ",
            "store_id": "2",
            "quantity": "2",
            "return_to": "dashboard",
        },
        follow_redirects=True,
    )

    assert b"Oat milk was added." in response.data
    assert b"Oat milk" in response.data
    assert b"Fresh Market" in response.data
    assert b"In Stock" in response.data
    assert b'data-quantity="2"' in response.data
    assert b">misc</span>" in response.data

    out_item = client.post(
        "/items",
        data={"name": "Coffee", "store_id": "1", "quantity": "0"},
        follow_redirects=True,
    )
    assert b"Out" in out_item.data


def test_add_item_json_response_supports_quick_entry(client):
    modal = client.get("/inventory").data
    assert b"data-add-item-form" in modal
    assert b"data-add-item-notification" in modal
    assert b"data-done-adding" in modal
    javascript = client.get("/static/js/app.js").data
    assert b"refreshInventory" in javascript
    assert b"BroadcastChannel('pantrypilot-inventory')" in javascript

    response = client.post(
        "/items",
        data={"name": "Yogurt", "store_id": "2", "quantity": "2"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 201
    assert response.json == {
        "ok": True,
        "message": "Yogurt was added to the pantry.",
    }
    assert b"Yogurt" in client.get("/inventory").data


def test_add_item_rejects_same_name_and_store_case_insensitively(client):
    duplicate = client.post(
        "/items",
        data={"name": "  mILk  ", "store_id": "1", "quantity": "4"},
        headers={"Accept": "application/json"},
    )

    assert duplicate.status_code == 400
    assert duplicate.json == {
        "ok": False,
        "message": "An item with this name and store already is in the pantry inventory.",
    }

    # The same item name remains valid when it belongs to a different store.
    other_store = client.post(
        "/items",
        data={"name": "Milk", "store_id": "2", "quantity": "1"},
        headers={"Accept": "application/json"},
    )
    assert other_store.status_code == 201


def test_categories_can_be_created_used_edited_and_deleted(client):
    created = client.post(
        "/categories",
        data={"name": "  Fresh   Food ", "color": "#AABBCC"},
        follow_redirects=True,
    )
    assert b"Fresh Food was added." in created.data
    assert b'data-color="#aabbcc"' in created.data

    item = client.post(
        "/items",
        data={"name": "Apples", "store_id": "1", "quantity": "3", "category_id": "2"},
        follow_redirects=True,
    )
    assert b">Fresh Food</span>" in item.data
    assert b'data-category-id="2"' in item.data

    edited = client.post(
        "/categories/2/edit",
        data={"name": "Produce", "color": "#112233"},
        follow_redirects=True,
    )
    assert b"Produce was updated." in edited.data
    assert b">Produce</span>" in client.get("/inventory").data

    deleted = client.post("/categories/2/delete", follow_redirects=True)
    assert b"Produce was deleted." in deleted.data
    inventory = client.get("/inventory").data
    apples_row = inventory.split(b"<strong>Apples</strong>", 1)[1].split(b"</tr>", 1)[0]
    assert b">misc</span>" in apples_row


def test_item_rejects_unknown_category_and_misc_is_protected(client):
    invalid = client.post(
        "/items",
        data={"name": "Bread", "store_id": "1", "quantity": "1", "category_id": "999"},
        follow_redirects=True,
    )
    assert b"Choose a valid category." in invalid.data

    renamed = client.post(
        "/categories/1/edit",
        data={"name": "Other", "color": "#64748b"},
        follow_redirects=True,
    )
    assert b"The misc category cannot be renamed." in renamed.data
    deleted = client.post("/categories/1/delete", follow_redirects=True)
    assert b"The misc category cannot be deleted." in deleted.data


@pytest.mark.parametrize(
    "name,store_id,quantity,message",
    [
        ("", "1", "1", "Enter an item name."),
        ("A" * 121, "1", "1", "Item names must be 120 characters or fewer."),
        ("Bread", "999", "1", "Choose a valid store."),
        ("Bread", "1", "1.5", "Quantity must be a whole number."),
        ("Bread", "1", "-1", "Quantity cannot be negative."),
    ],
)
def test_add_item_rejects_invalid_input(
    client, name, store_id, quantity, message
):
    response = client.post(
        "/items",
        data={"name": name, "store_id": store_id, "quantity": quantity},
        follow_redirects=True,
    )
    assert message.encode() in response.data


def test_item_edit_quantity_controls_and_delete(client):
    edited = client.post(
        "/items/1/edit",
        data={
            "name": "Plantains",
            "store_id": "3",
            "quantity": "4",
            "return_to": "inventory",
        },
        follow_redirects=True,
    )
    assert b"Plantains was updated." in edited.data
    assert b'data-quantity="4"' in edited.data
    assert b'data-store-id="3"' in edited.data

    decreased = client.post(
        "/items/1/quantity",
        data={"change": "-1", "return_to": "inventory"},
        follow_redirects=True,
    )
    assert b'data-quantity="3"' in decreased.data

    for _ in range(4):
        decreased = client.post(
            "/items/1/quantity",
            data={"change": "-1", "return_to": "inventory"},
            follow_redirects=True,
        )
    assert b'data-quantity="0"' in decreased.data
    assert b"Out" in decreased.data

    increased = client.post(
        "/items/1/quantity", data={"change": "1"}, follow_redirects=True
    )
    assert b'data-quantity="1"' in increased.data
    assert b"In Stock" in increased.data

    deleted = client.post("/items/1/delete", follow_redirects=True)
    assert b"Plantains was deleted." in deleted.data
    assert b'data-name="Plantains"' not in deleted.data


def test_quantity_json_response_supports_updates_without_navigation(client):
    page = client.get("/inventory")
    assert b"data-quantity-form" in page.data
    assert b'aria-live="polite"' in page.data

    response = client.post(
        "/items/1/quantity",
        data={"change": "1"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    assert response.json == {
        "ok": True,
        "quantity": 2,
        "status": {"label": "In Stock", "className": "stock"},
    }

    javascript = client.get("/static/js/app.js").data
    assert b"event.preventDefault()" in javascript
    assert b"[data-quantity-form]" in javascript


def test_items_default_active_and_can_be_made_inactive(client):
    created = client.post(
        "/items",
        data={"name": "Default active", "store_id": "1", "quantity": "0"},
        follow_redirects=True,
    )
    assert b'data-name="Default active"' in created.data
    assert b'data-is-active="1"' in created.data

    inactive = client.post(
        "/items/5/edit",
        data={
            "name": "Milk",
            "store_id": "1",
            "quantity": "0",
            "category_id": "1",
            "is_active": "0",
            "return_to": "inventory",
        },
        follow_redirects=True,
    )
    milk_row = inactive.data.split(b'<strong>Milk</strong>', 1)[0].rsplit(b"<tr", 1)[1]
    assert b'class="inactive-item"' in milk_row
    assert b'data-is-active="0"' in inactive.data

    dashboard = client.get("/").data
    assert b'class="inactive-item"' in dashboard
    assert b"Milk" in dashboard

    grocery_page = client.get("/grocery-lists?include_low=1").data
    grocery_pdf = client.get("/grocery-lists/download?include_low=1").data
    assert b"Milk" not in grocery_page
    assert b"Milk" not in grocery_pdf

    reactivated = client.post(
        "/items/5/edit",
        data={
            "name": "Milk",
            "store_id": "1",
            "quantity": "0",
            "category_id": "1",
            "is_active": ["0", "1"],
            "return_to": "inventory",
        },
        follow_redirects=True,
    )
    assert b'data-is-active="1"' in reactivated.data
    assert b"Milk" in client.get("/grocery-lists").data


def test_dashboard_search_filter_and_autocomplete(client):
    page = client.get("/")
    assert b'<datalist id="inventory-names">' in page.data
    assert b'<option value="Bananas">' in page.data

    searched = client.get("/?search=milk")
    assert b"<strong>Milk</strong>" in searched.data
    assert b"<strong>Eggs</strong>" not in searched.data

    filtered = client.get("/?store=2")
    assert b"<strong>Bananas</strong>" in filtered.data
    assert b"<strong>Milk</strong>" not in filtered.data
    assert b'<input type="hidden" name="store" value="2">' in filtered.data


def test_inventory_and_dashboard_search_forms_hide_redundant_controls(client):
    inventory_form = client.get('/inventory').data.split(b'<form class="filters inventory-filters"', 1)[1].split(b'</form>', 1)[0]
    dashboard_form = client.get('/').data.split(b'<form class="filters dashboard-lookup"', 1)[1].split(b'</form>', 1)[0]

    assert b'All stores' not in inventory_form
    assert b'>Search</button>' not in inventory_form
    assert b'link-button' not in inventory_form
    assert b'All stores' not in dashboard_form
    assert b'>Search</button>' not in dashboard_form
    assert b'link-button' not in dashboard_form


def test_search_sections_render_updated_headings(client):
    assert b'<h2 class="inventory-search-heading">Search Your Pantry</h2>' in client.get('/inventory').data
    assert b'<h2>Quick Pantry Lookup</h2>' in client.get('/').data


@pytest.mark.parametrize(
    ("path", "return_to", "return_query", "expected_query"),
    [
        ("/", "dashboard", "search=milk&store=1", "search=milk&store=1"),
        (
            "/inventory",
            "inventory",
            "search=milk&store=1&letter=M",
            "search=milk&store=1&letter=M",
        ),
    ],
)
def test_item_updates_preserve_inventory_filters(
    client, path, return_to, return_query, expected_query
):
    page = client.get(f"{path}?{return_query}")
    assert f'name="return_query" value="{return_query.replace("&", "&amp;")}"'.encode() in page.data

    response = client.post(
        "/items/2/quantity",
        data={
            "change": "1",
            "return_to": return_to,
            "return_query": return_query,
        },
    )

    assert response.headers["Location"] == f"{path}?{expected_query}"


def test_item_redirect_preserves_additional_inventory_filters(client):
    response = client.post(
        "/items/2/quantity",
        data={
            "change": "1",
            "return_to": "dashboard",
            "return_query": "search=milk&category=2&sort=quantity",
        },
    )

    assert response.headers["Location"] == "/?search=milk&category=2&sort=quantity"


@pytest.mark.parametrize("action", ["edit", "quantity", "delete"])
def test_modifying_missing_item_is_not_found(client, action):
    if action == "edit":
        data = {"name": "Missing", "store_id": "1", "quantity": "1"}
    elif action == "quantity":
        data = {"change": "1"}
    else:
        data = None
    assert client.post(f"/items/999/{action}", data=data).status_code == 404


def test_quantity_endpoint_rejects_invalid_change(client):
    assert client.post("/items/1/quantity", data={"change": "3"}).status_code == 400


def test_item_minimum_updates_inventory_statuses_and_lists(client):
    response = client.post(
        "/settings", data={"item_minimum": "2"}, follow_redirects=True
    )
    assert b"Item Minimum was updated to 2." in response.data
    assert b'value="2"' in response.data

    client.post(
        "/items",
        data={"name": "Zero item", "store_id": "1", "quantity": "0"},
    )
    client.post(
        "/items",
        data={"name": "Minimum item", "store_id": "1", "quantity": "2"},
    )
    client.post(
        "/items",
        data={"name": "Above item", "store_id": "1", "quantity": "3"},
    )

    inventory = client.get("/inventory").data
    zero_row = inventory.split(b"<strong>Zero item</strong>", 1)[1].split(b"</tr>", 1)[0]
    minimum_row = inventory.split(b"<strong>Minimum item</strong>", 1)[1].split(
        b"</tr>", 1
    )[0]
    above_row = inventory.split(b"<strong>Above item</strong>", 1)[1].split(
        b"</tr>", 1
    )[0]
    assert b'<span class="badge out">Out</span>' in zero_row
    assert b'<span class="badge low">Low</span>' in minimum_row
    assert b'<span class="badge stock">In Stock</span>' in above_row

    dashboard = client.get("/").data
    assert b"Low stock" in dashboard
    grocery_lists = client.get("/grocery-lists").data
    assert b"Minimum item" not in grocery_lists
    grocery_lists = client.get("/grocery-lists?include_low=1").data
    assert b"Minimum item" in grocery_lists
    assert b"Above item" not in grocery_lists


def test_custom_item_minimum_overrides_default_and_can_be_cleared(client):
    client.post("/settings", data={"item_minimum": "2"})
    created = client.post(
        "/items",
        data={
            "name": "Custom minimum item",
            "store_id": "1",
            "quantity": "3",
            "item_minimum": "4",
        },
        follow_redirects=True,
    )

    custom_row = created.data.split(b"<strong>Custom minimum item</strong>", 1)[1].split(
        b"</tr>", 1
    )[0]
    assert b'<span class="badge low">Low</span>' in custom_row
    assert b'data-item-minimum="4"' in custom_row

    cleared = client.post(
        "/items/6/edit",
        data={
            "name": "Custom minimum item",
            "store_id": "1",
            "quantity": "3",
            "item_minimum": "",
        },
        follow_redirects=True,
    )
    default_row = cleared.data.split(b"<strong>Custom minimum item</strong>", 1)[
        1
    ].split(b"</tr>", 1)[0]
    assert b'<span class="badge stock">In Stock</span>' in default_row
    assert b'data-item-minimum=""' in default_row


def test_item_forms_offer_optional_custom_minimum(client):
    page = client.get("/inventory").data

    assert page.count(b'name="item_minimum"') == 2
    assert page.count(b'placeholder="Default: 1"') == 2
    assert b"Leave blank to use the default from Settings." in page


@pytest.mark.parametrize(
    "value,message",
    [
        ("1.5", "Item Minimum must be a whole number."),
        ("-1", "Item Minimum cannot be negative."),
    ],
)
def test_custom_item_minimum_rejects_invalid_values(client, value, message):
    response = client.post(
        "/items",
        data={
            "name": "Invalid minimum",
            "store_id": "1",
            "quantity": "3",
            "item_minimum": value,
        },
        follow_redirects=True,
    )

    assert message.encode() in response.data
    assert b"Invalid minimum" not in client.get("/inventory").data


def test_grocery_lists_default_to_out_items_and_toggle_low_items(client):
    default_page = client.get("/grocery-lists")
    assert b"List settings" in default_page.data
    assert b"Sort first by" in default_page.data
    assert b'<option value="store" selected>Store</option>' in default_page.data
    assert b'<option value="category" >Category</option>' in default_page.data
    assert b"Milk" in default_page.data
    assert b"Dish soap" in default_page.data
    assert b"Bananas" not in default_page.data
    assert b'name="include_low" value="1"  onchange' in default_page.data
    store_lists = default_page.data.split(b'<section class="lists-grid">', 1)[1]
    assert b'<input type="checkbox">' not in store_lists

    with_low = client.get("/grocery-lists?include_low=1")
    assert b"Milk" in with_low.data
    assert b"Bananas" in with_low.data
    assert b'name="include_low" value="1" checked' in with_low.data
    assert b"/grocery-lists/download?include_low=1" in with_low.data


def test_grocery_lists_and_pdfs_can_sort_category_then_store(client):
    client.post("/categories", data={"name": "Cleaning", "color": "#123456"})
    client.post(
        "/items/3/edit",
        data={"name": "Dish soap", "store_id": "4", "quantity": "0", "category_id": "2"},
    )

    page = client.get("/grocery-lists?sort_first=category").data
    assert b'<option value="category" selected>Category</option>' in page
    assert page.index(b"Cleaning ") < page.index(b"misc ")
    cleaning_section = page.split(b"Cleaning ", 1)[1].split(b"</section>", 1)[0]
    assert b"Walmart" in cleaning_section
    assert b"Dish soap" in cleaning_section
    assert b"sort_first=category" in page

    category_pdf = client.get("/grocery-lists/download?sort_first=category").data
    assert category_pdf.index(b"(CLEANING ") < category_pdf.index(b"(WALMART ")
    assert category_pdf.index(b"(WALMART ") < category_pdf.index(b"(Dish soap")
    assert category_pdf.index(b"(MISC ") < category_pdf.index(b"(COSTCO ")

    store_pdf = client.get("/grocery-lists/download?sort_first=store").data
    assert store_pdf.index(b"(COSTCO) Tj") < store_pdf.index(b"(MISC ")
    assert store_pdf.index(b"(WALMART) Tj") < store_pdf.index(b"(CLEANING ")


def test_store_and_all_grocery_list_pdf_downloads(client):
    store_pdf = client.get("/grocery-lists/stores/1/download")
    assert store_pdf.status_code == 200
    assert store_pdf.mimetype == "application/pdf"
    assert "attachment;" in store_pdf.headers["Content-Disposition"]
    assert "costco-grocery-list.pdf" in store_pdf.headers["Content-Disposition"]
    assert store_pdf.data.startswith(b"%PDF-1.4")
    assert b"Milk" in store_pdf.data
    assert b"Eggs" not in store_pdf.data
    # The checkbox surrounds the first line's glyph body instead of sitting
    # below its text baseline.
    assert b"0.55 w 34 558.2 10 10 re S" in store_pdf.data
    assert b"(Milk \\(Qty: 0\\)) Tj" in store_pdf.data
    assert b"[ ]" not in store_pdf.data
    assert b"(PantryPilot) Tj" in store_pdf.data
    assert b"(Shop smart. Save time. Waste less.) Tj" in store_pdf.data

    all_pdf = client.get("/grocery-lists/download?include_low=1")
    assert all_pdf.status_code == 200
    assert all_pdf.data.startswith(b"%PDF-1.4")
    assert b"COSTCO" in all_pdf.data
    assert b"FRESH MARKET" in all_pdf.data
    assert b"WALMART" in all_pdf.data
    assert b"Bananas" in all_pdf.data
    assert b"Brown rice" in all_pdf.data
    assert all_pdf.data.index(b"COSTCO") < all_pdf.data.index(b"FRESH MARKET")
    # The printable design is monochrome regardless of configured UI colors.
    assert b"0.145 0.388 0.922 rg" not in all_pdf.data
    assert b"0.086 0.639 0.290 rg" not in all_pdf.data


def test_store_pdf_for_missing_store_is_not_found(client):
    assert client.get("/grocery-lists/stores/999/download").status_code == 404


def test_long_pdf_lists_repeat_context_across_pages(client):
    for index in range(40):
        client.post(
            "/items",
            data={
                "name": f"Long pantry item number {index:02d}",
                "store_id": "1",
                "quantity": "0",
            },
        )

    pdf = client.get("/grocery-lists/stores/1/download").data
    assert b"/Count 2" in pdf or b"/Count 3" in pdf
    assert b"(Costco Grocery List \xb7 Continued)" in pdf
    assert b"/F2 9 Tf" in pdf and b"(MISC) Tj" in pdf
    assert b"/F1 7 Tf" in pdf and b"(\\(continued\\)) Tj" in pdf
    assert pdf.count(b"(Shop smart. Save time. Waste less.)") >= 2
    assert b"(Page 1 of 2)" in pdf or b"(Page 1 of 3)" in pdf


def test_pdf_wraps_long_store_headings_inside_their_columns(client):
    client.post(
        "/stores",
        data={"name": "A Very Long Neighborhood Grocery Marketplace", "color": "#123456"},
    )
    client.post(
        "/items",
        data={"name": "Paper towels", "store_id": "5", "quantity": "0"},
    )

    pdf = client.get("/grocery-lists/download").data

    assert b"(A VERY LONG NEIGHBORHOOD) Tj" in pdf
    assert b"(GROCERY MARKETPLACE) Tj" in pdf


def test_pdf_lists_flow_down_then_across_columns(client):
    for index in range(24):
        client.post(
            "/items",
            data={"name": f"Flow item {index:02d}", "store_id": "1", "quantity": "0"},
        )
    client.post(
        "/items",
        data={"name": "Second flow item", "store_id": "2", "quantity": "0"},
    )

    pdf = client.get("/grocery-lists/download").data

    first_column = b"1 0 0 1 32 610 Tm (COSTCO) Tj"
    second_column = b"1 0 0 1 220 610 Tm (COSTCO) Tj"
    next_list_same_column = b"1 0 0 1 220 418 Tm (FRESH MARKET) Tj"
    assert pdf.index(first_column) < pdf.index(second_column)
    assert pdf.index(second_column) < pdf.index(next_list_same_column)
    assert b"/F1 8 Tf" in pdf and b"(\\(continued\\)) Tj" in pdf


def test_pdf_font_size_setting_updates_all_exported_pdfs(client):
    settings = client.get("/settings")
    assert b"Font size for exported PDFs" in settings.data
    assert b'name="pdf_font_size"' in settings.data
    assert b'value="12"' in settings.data

    updated = client.post(
        "/settings", data={"pdf_font_size": "20"}, follow_redirects=True
    )
    assert b"PDF font size was updated to 20." in updated.data
    assert b'name="pdf_font_size"' in updated.data
    assert b'value="20"' in updated.data

    store_pdf = client.get("/grocery-lists/stores/1/download")
    all_pdf = client.get("/grocery-lists/download")
    assert b"/F1 20 Tf" in store_pdf.data
    assert b"/F1 20 Tf" in all_pdf.data


@pytest.mark.parametrize("value", ["", "7", "33", "12.5"])
def test_pdf_font_size_rejects_invalid_values(client, value):
    response = client.post(
        "/settings", data={"pdf_font_size": value}, follow_redirects=True
    )
    assert b"PDF font size" in response.data
    assert b'value="12"' in response.data


@pytest.mark.parametrize(
    "value,message",
    [
        ("", "Item Minimum must be a whole number."),
        ("1.5", "Item Minimum must be a whole number."),
        ("-1", "Item Minimum cannot be negative."),
    ],
)
def test_item_minimum_rejects_invalid_values(client, value, message):
    response = client.post(
        "/settings", data={"item_minimum": value}, follow_redirects=True
    )
    assert message.encode() in response.data
    assert b'value="1"' in response.data


def test_item_minimum_persists_across_restart(tmp_path):
    database_path = tmp_path / "settings.db"
    app = create_app({"TESTING": True, "DATABASE": str(database_path)})
    app.test_client().post("/settings", data={"item_minimum": "4"})

    restarted = create_app(
        {"TESTING": True, "DATABASE": str(database_path)}
    ).test_client()
    assert b'value="4"' in restarted.get("/settings").data
    assert b'<span class="badge low">Low</span>' in restarted.get("/inventory").data


def test_username_updates_dashboard_greeting_and_persists(tmp_path):
    database_path = tmp_path / "username.db"
    app = create_app({"TESTING": True, "DATABASE": str(database_path)})
    client = app.test_client()

    response = client.post(
        "/settings", data={"username": "  Ada   Lovelace  "}, follow_redirects=True
    )

    assert b"Username was updated to Ada Lovelace." in response.data
    assert b'value="Ada Lovelace"' in response.data
    assert b"Hello, Ada Lovelace" in client.get("/").data

    restarted = create_app(
        {"TESTING": True, "DATABASE": str(database_path)}
    ).test_client()
    assert b"Hello, Ada Lovelace" in restarted.get("/").data


@pytest.mark.parametrize(
    "value,message",
    [
        ("", "Enter a username."),
        ("A" * 81, "Username must be 80 characters or fewer."),
    ],
)
def test_username_rejects_invalid_values(client, value, message):
    response = client.post(
        "/settings", data={"username": value}, follow_redirects=True
    )

    assert message.encode() in response.data
    assert b"Hello," not in client.get("/").data


def test_inventory_letter_selectors_filter_by_item_name(client):
    all_items = client.get("/inventory").data
    assert b'<nav class="alphabet" aria-label="Filter inventory by first letter">' in all_items
    assert b'<a class="active" href="/inventory" aria-current="page">All</a>' in all_items
    assert b"<strong>Bananas</strong>" in all_items
    assert b"<strong>Milk</strong>" in all_items

    b_items = client.get("/inventory?letter=B").data
    assert b'<a class="active" href="/inventory?letter=B" aria-current="page">B</a>' in b_items
    assert b"<strong>Bananas</strong>" in b_items
    assert b"<strong>Brown rice</strong>" in b_items
    assert b"<strong>Milk</strong>" not in b_items
    assert b"Showing 2 inventory items" in b_items


def test_inventory_letter_filter_is_case_insensitive_and_combines_with_filters(client):
    filtered = client.get("/inventory?letter=b&store=2").data
    assert b"<strong>Bananas</strong>" in filtered
    assert b"<strong>Brown rice</strong>" not in filtered
    assert b'<input type="hidden" name="letter" value="B">' in filtered
    assert b'<input type="hidden" name="store" value="2">' in filtered
    assert b'<a class="" href="/inventory">All</a>' in filtered

    invalid = client.get("/inventory?letter=invalid").data
    assert b'<a class="active" href="/inventory" aria-current="page">All</a>' in invalid
    assert b"<strong>Milk</strong>" in invalid


def test_inventory_suggestions_require_two_characters(client):
    assert client.get('/api/inventory/suggestions?q=m').get_json() == {'suggestions': []}
    assert client.get('/api/inventory/suggestions?q=  ').get_json() == {'suggestions': []}


def test_inventory_suggestions_are_case_insensitive_and_include_details(client):
    suggestions = client.get('/api/inventory/suggestions?q=MIL').get_json()['suggestions']
    milk = next(item for item in suggestions if item['name'] == 'Milk')
    assert milk['store'] == 'Costco'
    assert milk['quantity'] == 0


def test_inventory_suggestions_rank_prefixes_before_substrings(client):
    client.post('/items', data={'name': 'Amilk substring', 'store_id': '1', 'quantity': '2'})
    client.post('/items', data={'name': 'Milk prefix', 'store_id': '1', 'quantity': '1'})
    names = [item['name'] for item in client.get('/api/inventory/suggestions?q=milk').get_json()['suggestions']]
    assert names.index('Milk') < names.index('Amilk substring')
    assert names.index('Milk prefix') < names.index('Amilk substring')


def test_inventory_suggestions_limit_results_and_exclude_inactive(client):
    for index in range(12):
        client.post('/items', data={'name': f'Test suggestion {index:02}', 'store_id': '1', 'quantity': str(index)})
    client.post('/items', data={'name': 'Test inactive', 'store_id': '2', 'quantity': '4', 'is_active': ['0']})
    suggestions = client.get('/api/inventory/suggestions?q=test').get_json()['suggestions']
    assert len(suggestions) == 10
    assert all(item['name'] != 'Test inactive' for item in suggestions)


def test_inventory_suggestions_treat_sql_wildcards_literally(client):
    client.post('/items', data={'name': '100% Juice', 'store_id': '1', 'quantity': '3'})
    client.post('/items', data={'name': 'Under_score', 'store_id': '1', 'quantity': '2'})
    percent = client.get('/api/inventory/suggestions?q=0%').get_json()['suggestions']
    underscore = client.get('/api/inventory/suggestions?q=r_').get_json()['suggestions']
    assert [item['name'] for item in percent] == ['100% Juice']
    assert [item['name'] for item in underscore] == ['Under_score']
    assert client.get('/api/inventory/suggestions?q=zz-no-match').get_json() == {'suggestions': []}
