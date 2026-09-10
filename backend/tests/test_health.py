from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_cities_includes_vancouver() -> None:
    response = client.get("/api/v1/cities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["cities"][0]["cityId"] == "vancouver"
    assert payload["cities"][0]["name"] == "Vancouver, BC"


def test_unknown_city_returns_stable_error_code() -> None:
    response = client.get("/api/v1/cities/seattle")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "CITY_NOT_AVAILABLE"
