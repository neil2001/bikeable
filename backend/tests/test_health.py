from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_cities_includes_fixture_when_no_real_graph(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.city_registry.city_graph_is_available",
        lambda _city_id: False,
    )
    response = client.get("/api/v1/cities")
    assert response.status_code == 200
    payload = response.json()
    city_ids = {city["cityId"] for city in payload["cities"]}
    assert "vancouver" in city_ids
    assert "fixture" in city_ids


def test_list_cities_hides_fixture_when_real_graph_exists(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.city_registry.city_graph_is_available",
        lambda city_id: city_id == "vancouver",
    )
    response = client.get("/api/v1/cities")
    assert response.status_code == 200
    city_ids = {city["cityId"] for city in response.json()["cities"]}
    assert "vancouver" in city_ids
    assert "fixture" not in city_ids


def test_unknown_city_returns_stable_error_code() -> None:
    response = client.get("/api/v1/cities/seattle")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "CITY_NOT_AVAILABLE"
