from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

EXPECTED_PATHS = {
    "/api/v1/health",
    "/api/v1/cities",
    "/api/v1/cities/{cityId}",
    "/api/v1/cities/{cityId}/bikeability",
    "/api/v1/roads/{roadId}",
    "/api/v1/routes/segment",
    "/api/v1/routes/manual",
    "/api/v1/routes/loop",
    "/api/v1/routes/{routeId}",
    "/api/v1/routes/{routeId}/gpx",
}


def test_openapi_lists_v1_routes() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = set(response.json()["paths"])
    missing = EXPECTED_PATHS - paths
    assert not missing, f"OpenAPI missing paths: {sorted(missing)}"
