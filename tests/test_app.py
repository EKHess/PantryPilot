import pytest

from app import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})
    return app.test_client()


@pytest.mark.parametrize("path, heading", [
    ("/", "Good morning"),
    ("/inventory", "Inventory"),
    ("/grocery-lists", "Grocery lists"),
    ("/stores", "Stores"),
    ("/settings", "Settings"),
])
def test_pages_render(client, path, heading):
    response = client.get(path)
    assert response.status_code == 200
    assert heading.encode() in response.data


def test_unknown_page_is_not_found(client):
    assert client.get("/missing").status_code == 404


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

    out_item = client.post(
        "/items",
        data={"name": "Coffee", "store_id": "1", "quantity": "0"},
        follow_redirects=True,
    )
    assert b"Out" in out_item.data


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
    assert b'<option value="2" selected>Fresh Market</option>' in filtered.data


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
    assert b"Minimum item" in grocery_lists
    assert b"Above item" not in grocery_lists
    assert b"Quantity \xe2\x89\xa4 2" in grocery_lists


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
    assert b'<option value="2" selected>Fresh Market</option>' in filtered
    assert b'<a class="" href="/inventory">All</a>' in filtered

    invalid = client.get("/inventory?letter=invalid").data
    assert b'<a class="active" href="/inventory" aria-current="page">All</a>' in invalid
    assert b"<strong>Milk</strong>" in invalid
