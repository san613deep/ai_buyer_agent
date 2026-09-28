"""
Deterministic business rules engine for purchasing decisions.
All critical calculations happen here — NOT in the LLM.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PurchaseContext:
    """All data needed for a purchase decision."""
    sku: str
    recommended_qty: int
    current_inventory: int
    reserved_inventory: int
    available_inventory: int
    incoming_qty: int  # from open POs
    demand_next_30: int
    demand_next_60: int
    safety_stock: int
    daily_demand: float
    supplier_moq: int
    supplier_lead_time_days: int
    supplier_reliability: float
    unit_cost: float
    budget_remaining: float
    storage_available_m3: float
    product_volume_m3: float


@dataclass
class PurchaseDecision:
    """Result of rules engine evaluation."""
    action: str  # ACCEPT, MODIFY, REJECT, INVESTIGATE
    recommended_qty: int
    adjusted_qty: int
    reasons: list[str]
    constraints_hit: list[str]
    risk_level: str  # LOW, MEDIUM, HIGH
    requires_approval: bool
    details: dict


def calculate_required_quantity(ctx: PurchaseContext) -> int:
    """
    Calculate the actual quantity needed based on demand vs supply.
    
    Formula:
      need = demand_next_30 + safety_stock - available_inventory - incoming_qty
    """
    total_supply = ctx.available_inventory + ctx.incoming_qty
    need = ctx.demand_next_30 + ctx.safety_stock - total_supply
    return max(0, need)


def check_moq_constraint(qty: int, moq: int) -> tuple[int, Optional[str]]:
    """Ensure quantity meets supplier minimum order quantity."""
    if qty == 0:
        return 0, None
    if qty < moq:
        return moq, f"Quantity raised from {qty} to {moq} to meet supplier MOQ"
    return qty, None


def check_budget_constraint(qty: int, unit_cost: float, budget_remaining: float) -> tuple[int, Optional[str]]:
    """Ensure total cost fits within remaining budget."""
    total_cost = qty * unit_cost
    if total_cost > budget_remaining:
        max_affordable = int(budget_remaining // unit_cost)
        return max_affordable, f"Budget constraint: can only afford {max_affordable} units (${budget_remaining:.2f} remaining, ${unit_cost:.2f}/unit)"
    return qty, None


def check_storage_constraint(qty: int, volume_per_unit: float, storage_available_m3: float) -> tuple[int, Optional[str]]:
    """Ensure ordered quantity fits in available storage."""
    total_volume = qty * volume_per_unit
    if total_volume > storage_available_m3:
        max_storable = int(round(storage_available_m3 / volume_per_unit)) if volume_per_unit > 0 else qty
        return max_storable, f"Storage constraint: can only store {max_storable} units ({storage_available_m3:.2f} m³ available, {volume_per_unit:.4f} m³/unit)"
    return qty, None


def assess_risk(ctx: PurchaseContext, final_qty: int) -> tuple[str, bool]:
    """
    Determine risk level and whether human approval is needed.
    
    HIGH risk (needs approval):
      - Total cost > 50% of remaining budget
      - Supplier reliability < 0.90
      - Order qty > 2x the calculated need
    
    MEDIUM risk:
      - Total cost > 25% of remaining budget
      - Lead time > 21 days
    """
    total_cost = final_qty * ctx.unit_cost
    reasons_high = []
    reasons_medium = []

    if ctx.budget_remaining > 0 and total_cost > 0.5 * ctx.budget_remaining:
        reasons_high.append("Cost exceeds 50% of remaining budget")
    if ctx.supplier_reliability < 0.90:
        reasons_high.append(f"Supplier reliability is low ({ctx.supplier_reliability:.0%})")

    required = calculate_required_quantity(ctx)
    if required > 0 and final_qty > 2 * required:
        reasons_high.append(f"Order qty ({final_qty}) is >2x calculated need ({required})")

    if ctx.budget_remaining > 0 and total_cost > 0.25 * ctx.budget_remaining:
        reasons_medium.append("Cost exceeds 25% of remaining budget")
    if ctx.supplier_lead_time_days > 21:
        reasons_medium.append(f"Long lead time ({ctx.supplier_lead_time_days} days)")

    if reasons_high:
        return "HIGH", True
    elif reasons_medium:
        return "MEDIUM", False
    return "LOW", False


def evaluate_recommendation(ctx: PurchaseContext) -> PurchaseDecision:
    """
    Main rules engine: evaluate a purchase recommendation and return a decision.
    
    Decision logic:
    1. Calculate actual need
    2. Compare with recommendation
    3. Apply constraints (MOQ, budget, storage)
    4. Determine action: ACCEPT / MODIFY / REJECT / INVESTIGATE
    """
    reasons = []
    constraints_hit = []

    # Step 1: Calculate how much we actually need
    required_qty = calculate_required_quantity(ctx)

    # Step 2: Start with the calculated need
    adjusted_qty = required_qty

    # Step 3: Apply MOQ constraint
    adjusted_qty, moq_msg = check_moq_constraint(adjusted_qty, ctx.supplier_moq)
    if moq_msg:
        constraints_hit.append(moq_msg)

    # Step 4: Apply budget constraint
    adjusted_qty, budget_msg = check_budget_constraint(adjusted_qty, ctx.unit_cost, ctx.budget_remaining)
    if budget_msg:
        constraints_hit.append(budget_msg)

    # Step 5: Apply storage constraint
    adjusted_qty, storage_msg = check_storage_constraint(adjusted_qty, ctx.product_volume_m3, ctx.storage_available_m3)
    if storage_msg:
        constraints_hit.append(storage_msg)

    # Step 6: Re-check MOQ after budget/storage reduction
    if 0 < adjusted_qty < ctx.supplier_moq:
        constraints_hit.append(f"After constraints, qty {adjusted_qty} is below MOQ {ctx.supplier_moq}")

    # Step 7: Determine action
    total_supply = ctx.available_inventory + ctx.incoming_qty
    coverage_days = total_supply / ctx.daily_demand if ctx.daily_demand > 0 else 999

    details = {
        "required_qty": required_qty,
        "available_inventory": ctx.available_inventory,
        "incoming_qty": ctx.incoming_qty,
        "total_supply": total_supply,
        "demand_next_30": ctx.demand_next_30,
        "safety_stock": ctx.safety_stock,
        "coverage_days": round(coverage_days, 1),
        "total_cost": round(adjusted_qty * ctx.unit_cost, 2),
        "supplier_moq": ctx.supplier_moq,
        "supplier_lead_time_days": ctx.supplier_lead_time_days,
    }

    if required_qty == 0:
        # No need to order — current supply covers demand
        action = "REJECT"
        adjusted_qty = 0
        reasons.append(f"Current supply ({total_supply} units) covers 30-day demand ({ctx.demand_next_30}) plus safety stock ({ctx.safety_stock})")
        reasons.append(f"Inventory covers {coverage_days:.0f} days of demand")
    elif adjusted_qty == 0:
        # Need exists but constraints prevent ordering
        action = "INVESTIGATE"
        reasons.append("Purchase needed but constraints prevent ordering")
        reasons.append("Budget or storage limitations must be resolved")
    elif 0 < adjusted_qty < ctx.supplier_moq:
        # Can't meet MOQ after constraints
        action = "INVESTIGATE"
        reasons.append(f"Need {required_qty} units but constraints limit to {adjusted_qty}, which is below MOQ ({ctx.supplier_moq})")
    elif adjusted_qty == ctx.recommended_qty:
        action = "ACCEPT"
        reasons.append(f"Recommendation of {ctx.recommended_qty} units aligns with calculated need")
    else:
        action = "MODIFY"
        if adjusted_qty < ctx.recommended_qty:
            reasons.append(f"Reduced from {ctx.recommended_qty} to {adjusted_qty} units based on actual need and constraints")
        else:
            reasons.append(f"Adjusted from {ctx.recommended_qty} to {adjusted_qty} units (MOQ or need adjustment)")

    # Step 8: Assess risk
    risk_level, requires_approval = assess_risk(ctx, adjusted_qty)
    if requires_approval:
        reasons.append("⚠️ HIGH RISK: Requires human approval before execution")

    return PurchaseDecision(
        action=action,
        recommended_qty=ctx.recommended_qty,
        adjusted_qty=adjusted_qty,
        reasons=reasons,
        constraints_hit=constraints_hit,
        risk_level=risk_level,
        requires_approval=requires_approval,
        details=details,
    )


def validate_purchase_order(po: dict, ctx: PurchaseContext) -> dict:
    """
    Post-action validation: verify a created PO is acceptable.
    Returns validation result with pass/fail and issues found.
    """
    issues = []
    warnings = []

    qty = po["quantity"]
    total_cost = po.get("total_cost", qty * po.get("unit_cost", ctx.unit_cost))

    # Validate MOQ
    if qty < ctx.supplier_moq:
        issues.append(f"PO quantity ({qty}) is below supplier MOQ ({ctx.supplier_moq})")

    # Validate budget
    if total_cost > ctx.budget_remaining:
        issues.append(f"PO cost (${total_cost:.2f}) exceeds remaining budget (${ctx.budget_remaining:.2f})")

    # Validate storage
    volume_needed = qty * ctx.product_volume_m3
    if volume_needed > ctx.storage_available_m3:
        issues.append(f"PO requires {volume_needed:.2f} m³ but only {ctx.storage_available_m3:.2f} m³ available")

    # Validate reasonable quantity
    required = calculate_required_quantity(ctx)
    if required > 0 and qty > 3 * required:
        warnings.append(f"PO quantity ({qty}) is >3x calculated need ({required})")

    # Validate cost matches expected
    expected_cost = qty * ctx.unit_cost
    if abs(total_cost - expected_cost) > 0.01:
        issues.append(f"PO cost (${total_cost:.2f}) doesn't match expected (${expected_cost:.2f})")

    passed = len(issues) == 0

    return {
        "valid": passed,
        "po_id": po["po_id"],
        "issues": issues,
        "warnings": warnings,
        "checks_performed": [
            "moq_check",
            "budget_check",
            "storage_check",
            "quantity_reasonableness",
            "cost_accuracy",
        ],
    }
