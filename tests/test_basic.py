import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "name" in response.json()

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "components" in data

def test_liveness():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
