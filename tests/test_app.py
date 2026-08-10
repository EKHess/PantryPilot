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
