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
