"""
Purchasing Agent — orchestrates the decision workflow.
Uses the rules engine for calculations and optionally an LLM for explanations.
"""

import os
import json
from typing import Optional
from datetime import datetime, timezone

from backend.database import MockDatabase
from backend.rules_engine import (
    PurchaseContext,
    PurchaseDecision,
    evaluate_recommendation,
    validate_purchase_order,
)


def _build_context(db: MockDatabase, sku: str, recommended_qty: int) -> PurchaseContext:
    """Gather all relevant data and build a PurchaseContext."""
    product = db.get_product(sku)
    if not product:
        raise ValueError(f"Unknown product SKU: {sku}")

    inventory = db.get_inventory(sku)
    if not inventory:
        raise ValueError(f"No inventory data for SKU: {sku}")

    demand = db.get_demand_forecast(sku)
    if not demand:
        raise ValueError(f"No demand forecast for SKU: {sku}")

    supplier = db.get_supplier_for_product(sku)
    if not supplier:
        raise ValueError(f"No supplier found for SKU: {sku}")

    incoming_qty = db.get_incoming_quantity(sku)
    budget = db.get_budget()
    storage = db.get_storage()

    return PurchaseContext(
        sku=sku,
        recommended_qty=recommended_qty,
        current_inventory=inventory["on_hand"],
        reserved_inventory=inventory["reserved"],
        available_inventory=inventory["available"],
        incoming_qty=incoming_qty,
        demand_next_30=demand["next_30_days"],
        demand_next_60=demand["next_60_days"],
        safety_stock=demand["safety_stock"],
        daily_demand=demand["daily_avg"],
        supplier_moq=supplier["min_order_qty"],
        supplier_lead_time_days=supplier["lead_time_days"],
        supplier_reliability=supplier["reliability_score"],
        unit_cost=product["unit_cost"],
        budget_remaining=budget["remaining"],
        storage_available_m3=storage["available_m3"],
        product_volume_m3=product["volume_m3"],
    )


def _get_llm_explanation(decision: PurchaseDecision, ctx: PurchaseContext) -> str:
    """
    Optionally use OpenAI to generate a human-readable explanation.
    Falls back to a template-based explanation if no API key is available.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")

    if api_key and api_key != "your-openai-api-key-here":
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)

            prompt = f"""You are a purchasing analyst. Summarize this purchase decision in 2-3 clear sentences.

Decision: {decision.action}
Product: {ctx.sku}
Recommended qty: {decision.recommended_qty}
Adjusted qty: {decision.adjusted_qty}
Reasons: {'; '.join(decision.reasons)}
Constraints: {'; '.join(decision.constraints_hit) if decision.constraints_hit else 'None'}
Risk: {decision.risk_level}
Coverage days: {decision.details['coverage_days']}
Total cost: ${decision.details['total_cost']:.2f}

Be concise and focus on the business rationale."""

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            pass  # Fall through to template

    # Fallback: template-based explanation
    return _template_explanation(decision, ctx)


def _template_explanation(decision: PurchaseDecision, ctx: PurchaseContext) -> str:
    """Generate a structured explanation without an LLM."""
    lines = []

    if decision.action == "ACCEPT":
        lines.append(f"The recommendation to purchase {decision.adjusted_qty} units of {ctx.sku} is accepted.")
        lines.append(f"Current supply ({ctx.available_inventory} on hand + {ctx.incoming_qty} incoming) "
                      f"is insufficient for 30-day demand ({ctx.demand_next_30}) plus safety stock ({ctx.safety_stock}).")
    elif decision.action == "MODIFY":
        lines.append(f"The recommendation has been modified from {decision.recommended_qty} to {decision.adjusted_qty} units.")
        lines.append(f"Calculated need is based on 30-day demand ({ctx.demand_next_30}) + safety stock ({ctx.safety_stock}) "
                      f"minus current supply ({ctx.available_inventory} + {ctx.incoming_qty} incoming).")
    elif decision.action == "REJECT":
        lines.append(f"The recommendation to purchase {decision.recommended_qty} units is rejected.")
        lines.append(f"Current supply ({ctx.available_inventory} + {ctx.incoming_qty} incoming = "
                      f"{ctx.available_inventory + ctx.incoming_qty}) already covers "
                      f"30-day demand ({ctx.demand_next_30}) + safety stock ({ctx.safety_stock}).")
    elif decision.action == "INVESTIGATE":
        lines.append(f"The purchase of {ctx.sku} requires further investigation.")
        lines.append("Constraints prevent the order from being placed as recommended.")

    if decision.constraints_hit:
        lines.append("Constraints: " + "; ".join(decision.constraints_hit) + ".")

    if decision.risk_level != "LOW":
        lines.append(f"Risk level: {decision.risk_level}.")

    return " ".join(lines)


def process_recommendation(
    db: MockDatabase,
    sku: str,
    recommended_qty: int,
    auto_approve: bool = False,
) -> dict:
    """
    Main agent workflow:
    1. Gather context (inventory, demand, POs, supplier, budget, storage)
    2. Evaluate using deterministic rules
    3. Create/modify PO if appropriate
    4. Validate the resulting PO
    5. Return full result with reasoning
    """
    # Step 1: Build context
    ctx = _build_context(db, sku, recommended_qty)

    # Step 2: Evaluate recommendation
    decision = evaluate_recommendation(ctx)

    # Step 3: Generate explanation
    explanation = _get_llm_explanation(decision, ctx)

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sku": sku,
        "product_name": db.get_product(sku)["name"],
        "recommended_qty": recommended_qty,
        "decision": {
            "action": decision.action,
            "adjusted_qty": decision.adjusted_qty,
            "reasons": decision.reasons,
            "constraints_hit": decision.constraints_hit,
            "risk_level": decision.risk_level,
            "requires_approval": decision.requires_approval,
        },
        "context": {
            "available_inventory": ctx.available_inventory,
            "incoming_qty": ctx.incoming_qty,
            "demand_next_30": ctx.demand_next_30,
            "safety_stock": ctx.safety_stock,
            "coverage_days": decision.details["coverage_days"],
            "supplier_moq": ctx.supplier_moq,
            "supplier_lead_time_days": ctx.supplier_lead_time_days,
            "budget_remaining": ctx.budget_remaining,
            "storage_available_m3": ctx.storage_available_m3,
        },
        "explanation": explanation,
        "purchase_order": None,
        "validation": None,
    }

    # Step 4: Create PO if action is ACCEPT or MODIFY
    if decision.action in ("ACCEPT", "MODIFY") and decision.adjusted_qty > 0:
        if decision.requires_approval and not auto_approve:
            result["decision"]["status"] = "pending_human_approval"
            result["explanation"] += " This purchase requires human approval before the PO can be created."
        else:
            supplier = db.get_supplier_for_product(sku)
            po = db.create_purchase_order(
                sku=sku,
                quantity=decision.adjusted_qty,
                supplier_id=supplier["id"],
                unit_cost=ctx.unit_cost,
            )
            result["purchase_order"] = po

            # Step 5: Validate the PO
            # Re-build context with ORIGINAL budget/storage for validation
            validation = validate_purchase_order(po, ctx)
            result["validation"] = validation

            if not validation["valid"]:
                # Feedback loop: PO failed validation
                result["decision"]["status"] = "validation_failed"
                result["explanation"] += f" ⚠️ Post-creation validation FAILED: {'; '.join(validation['issues'])}. The PO has been flagged for review."
                db.update_po_status(po["po_id"], "validation_failed")
            else:
                result["decision"]["status"] = "executed"
                db.update_po_status(po["po_id"], "confirmed")
    else:
        result["decision"]["status"] = "no_action"

    return result


def approve_purchase(db: MockDatabase, sku: str, recommended_qty: int) -> dict:
    """Process a recommendation with auto-approval (human approved)."""
    return process_recommendation(db, sku, recommended_qty, auto_approve=True)
