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
