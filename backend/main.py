"""
FastAPI application — REST API for the purchasing agent.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from backend.database import MockDatabase
from backend.agent import process_recommendation, approve_purchase

app = FastAPI(
    title="AI Purchasing Agent",
    description="Scenario 1: Purchase Recommendation Review",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared database instance
db = MockDatabase()


# ── Request/Response Models ──────────────────────────────────────────

class RecommendationRequest(BaseModel):
    sku: str = Field(..., description="Product SKU", examples=["SKU-001"])
    recommended_qty: int = Field(..., gt=0, description="Recommended purchase quantity", examples=[800])


class ApprovalRequest(BaseModel):
    sku: str
    recommended_qty: int = Field(..., gt=0)


# ── API Endpoints ────────────────────────────────────────────────────

@app.get("/api/products")
def list_products():
    """List all available products."""
    return db.list_products()


@app.get("/api/products/{sku}")
def get_product(sku: str):
    """Get product details and related data."""
    product = db.get_product(sku)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {sku} not found")

    inventory = db.get_inventory(sku)
    demand = db.get_demand_forecast(sku)
    supplier = db.get_supplier_for_product(sku)
    open_pos = db.get_open_pos_for_sku(sku)

    return {
        "product": product,
        "inventory": inventory,
        "demand_forecast": demand,
        "supplier": supplier,
        "open_purchase_orders": open_pos,
        "budget": db.get_budget(),
        "storage": db.get_storage(),
    }


@app.post("/api/evaluate")
def evaluate(req: RecommendationRequest):
    """
    Evaluate a purchase recommendation.
    Returns decision (ACCEPT/MODIFY/REJECT/INVESTIGATE) with reasoning.
    """
    try:
        result = process_recommendation(db, req.sku, req.recommended_qty)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.post("/api/approve")
def approve(req: ApprovalRequest):
    """
    Approve a high-risk purchase (human-in-the-loop).
    Processes the recommendation with auto_approve=True.
    """
    try:
        result = approve_purchase(db, req.sku, req.recommended_qty)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.get("/api/purchase-orders")
def list_purchase_orders():
    """List all purchase orders (open + created)."""
    return db.open_purchase_orders


@app.post("/api/reset")
def reset_data():
    """Reset mock data to initial state."""
    global db
    db = MockDatabase()
    return {"status": "reset", "message": "Database reset to initial state"}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ai-purchasing-agent"}
