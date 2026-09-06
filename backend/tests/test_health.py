from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint_returns_200():
    """Verify GET /api/health responds with HTTP 200 OK."""
    response = client.get("/api/health")
    assert response.status_code == 200

def test_health_response_structure():
    """Verify GET /api/health returns the expected JSON payload."""
    response = client.get("/api/health")
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "info2impact"

def test_root_endpoint():
    """Verify root GET / returns basic metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Info2Impact"
    assert data["health"] == "/api/health"
