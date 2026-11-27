"""HTTP-level tests for the FastAPI purchasing-agent endpoints."""
import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import main
from backend.database import MockDatabase


def setup_function():
    # Each test starts with an isolated in-memory dataset.
    main.db = MockDatabase()


def test_health_endpoint():
    response = TestClient(main.app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ai-purchasing-agent"}


def test_list_products_endpoint():
    response = TestClient(main.app).get("/api/products")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert response.json()


def test_unknown_product_returns_404():
    response = TestClient(main.app).get("/api/products/UNKNOWN-SKU")

    assert response.status_code == 404


def test_evaluate_endpoint_returns_a_decision():
    response = TestClient(main.app).post(
        "/api/evaluate",
        json={"sku": "SKU-001", "recommended_qty": 600},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["action"] in {"ACCEPT", "MODIFY", "REJECT", "INVESTIGATE"}
    assert "reasons" in body["decision"]


def test_evaluate_rejects_non_positive_quantity():
    response = TestClient(main.app).post(
        "/api/evaluate",
        json={"sku": "SKU-001", "recommended_qty": 0},
    )

    assert response.status_code == 422


def test_unknown_sku_evaluation_returns_400():
    response = TestClient(main.app).post(
        "/api/evaluate",
        json={"sku": "UNKNOWN-SKU", "recommended_qty": 10},
    )

    assert response.status_code == 400
