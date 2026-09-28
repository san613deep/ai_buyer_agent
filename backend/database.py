"""
Mock database layer - loads and manages data from JSON files.
Simulates database operations for the purchasing agent.
"""

import json
import os
import copy
from datetime import datetime, timedelta, timezone
from typing import Optional

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "mock_data.json")


class MockDatabase:
    """In-memory database loaded from JSON mock data."""

    def __init__(self, data_path: str = None):
        path = data_path or DATA_PATH
        with open(path, "r") as f:
            self._data = json.load(f)

        # Mutable copies for runtime modifications
        self.products = copy.deepcopy(self._data["products"])
        self.suppliers = copy.deepcopy(self._data["suppliers"])
        self.inventory = copy.deepcopy(self._data["inventory"])
        self.demand_forecast = copy.deepcopy(self._data["demand_forecast"])
        self.open_purchase_orders = copy.deepcopy(self._data["open_purchase_orders"])
        self.budget = copy.deepcopy(self._data["budget"])
        self.storage = copy.deepcopy(self._data["storage"])
        self.created_purchase_orders: list[dict] = []
        self.po_counter = 3000  # Next PO number

    def reset(self):
        """Reset to original data (useful for tests)."""
        self.__init__()

    # ── Product queries ──────────────────────────────────────────────
    def get_product(self, sku: str) -> Optional[dict]:
        return self.products.get(sku)

    def list_products(self) -> list[dict]:
        return list(self.products.values())

    # ── Inventory queries ────────────────────────────────────────────
    def get_inventory(self, sku: str) -> Optional[dict]:
        return self.inventory.get(sku)

    # ── Demand queries ───────────────────────────────────────────────
    def get_demand_forecast(self, sku: str) -> Optional[dict]:
        return self.demand_forecast.get(sku)

    # ── Supplier queries ─────────────────────────────────────────────
    def get_supplier_for_product(self, sku: str) -> Optional[dict]:
        for sup in self.suppliers.values():
            if sku in sup["products"]:
                return sup
        return None

    def get_supplier(self, supplier_id: str) -> Optional[dict]:
        return self.suppliers.get(supplier_id)

    # ── Purchase order queries ───────────────────────────────────────
    def get_open_pos_for_sku(self, sku: str) -> list[dict]:
        return [po for po in self.open_purchase_orders if po["sku"] == sku and po["status"] in ("confirmed", "shipped")]

    def get_incoming_quantity(self, sku: str) -> int:
        return sum(po["quantity"] for po in self.get_open_pos_for_sku(sku))

    # ── Budget queries ───────────────────────────────────────────────
    def get_budget(self) -> dict:
        return self.budget

    # ── Storage queries ──────────────────────────────────────────────
    def get_storage(self) -> dict:
        return self.storage

    # ── Purchase order creation ──────────────────────────────────────
    def create_purchase_order(self, sku: str, quantity: int, supplier_id: str, unit_cost: float) -> dict:
        self.po_counter += 1
        supplier = self.get_supplier(supplier_id)
        lead_time = supplier["lead_time_days"] if supplier else 14

        po = {
            "po_id": f"PO-{self.po_counter}",
            "sku": sku,
            "supplier_id": supplier_id,
            "quantity": quantity,
            "unit_cost": unit_cost,
            "total_cost": round(quantity * unit_cost, 2),
            "status": "pending_approval",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expected_delivery": (datetime.now(timezone.utc) + timedelta(days=lead_time)).strftime("%Y-%m-%d"),
        }

        self.created_purchase_orders.append(po)
        self.open_purchase_orders.append(po)

        # Update budget
        self.budget["spent_this_month"] += po["total_cost"]
        self.budget["remaining"] = round(self.budget["total_monthly"] - self.budget["spent_this_month"], 2)

        # Update storage (reserved)
        product = self.get_product(sku)
        if product:
            volume_needed = quantity * product["volume_m3"]
            self.storage["used_m3"] = round(self.storage["used_m3"] + volume_needed, 4)
            self.storage["available_m3"] = round(self.storage["total_capacity_m3"] - self.storage["used_m3"], 4)

        return po

    def update_po_status(self, po_id: str, status: str) -> Optional[dict]:
        for po in self.open_purchase_orders:
            if po["po_id"] == po_id:
                po["status"] = status
                return po
        for po in self.created_purchase_orders:
            if po["po_id"] == po_id:
                po["status"] = status
                return po
        return None


# Singleton instance
db = MockDatabase()
