# Interview Guide — AI Purchasing Agent

## Quick Summary (30 seconds)
> "I built an AI purchasing agent that evaluates buy recommendations using deterministic business rules, 
> not LLM math. The LLM only generates human-readable explanations. The system gathers context 
> (inventory, demand, POs, budget, storage), calculates the optimal quantity, applies constraints,
> creates a PO, and validates the result in a feedback loop."

---

## Architecture Questions

### "Why separate the rules engine from the LLM?"
- **LLMs are unreliable at math.** A $50K budget miscalculation is unacceptable.
- The rules engine is **deterministic, testable, and auditable**.
- The LLM adds value in **explanation generation** — making decisions human-readable.
- This mirrors how real purchasing systems work: ERP does the math, humans interpret results.

### "How does the agent workflow work?"
1. **Gather context**: Query inventory, demand, open POs, supplier info, budget, storage
2. **Calculate need**: `need = demand_30 + safety_stock - available - incoming`
3. **Apply constraints**: MOQ → Budget → Storage (in order)
4. **Decide**: ACCEPT / MODIFY / REJECT / INVESTIGATE
5. **Execute**: Create PO if appropriate
6. **Validate**: Post-action checks (budget, MOQ, storage, reasonableness)
7. **Feedback loop**: If validation fails → flag PO, don't confirm

### "Why these specific constraints?"
- **MOQ**: Real suppliers have minimum order quantities
- **Budget**: Prevents overspending within monthly budget
- **Storage**: Warehouses have physical limits
- Applied in sequence so each can limit the previous

### "What is the feedback loop?"
After creating a PO, the system runs `validate_purchase_order()` which checks:
1. Quantity ≥ supplier MOQ
2. Total cost ≤ remaining budget
3. Volume ≤ available storage
4. Quantity is reasonable (not >3x calculated need)
5. Cost accuracy matches expected

If validation fails → PO status becomes `validation_failed` → requires manual review.
This catches edge cases where constraints interact unexpectedly.

---

## Decision Logic

### When does it ACCEPT?
- Recommended qty exactly matches calculated need after constraints

### When does it MODIFY?
- Qty needs adjustment (too high, or raised for MOQ)

### When does it REJECT?
- No purchase needed — current supply covers 30-day demand + safety stock

### When does it INVESTIGATE?
- Purchase is needed but constraints make it impossible
- e.g., budget only allows 50 units but MOQ is 100

---

## Human-in-the-Loop

### When does approval trigger?
HIGH risk if any of:
- Total cost > 50% of remaining budget
- Supplier reliability < 90%
- Order qty > 2× calculated need

### How does the approval flow work?
1. Agent returns decision with `requires_approval: true`
2. UI shows approval banner with Approve/Reject buttons
3. Approve calls `/api/approve` which re-runs with `auto_approve=True`
4. Reject simply cancels — no PO created

---

## Testing Strategy

### What the tests cover:
| Test | Scenario | What it proves |
|------|----------|----------------|
| ACCEPT | Qty matches need | Agent creates PO, validates OK |
| MODIFY | Qty too high | Agent reduces to calculated need |
| REJECT | Supply covers demand | Agent says "don't buy" |
| Constraints | Budget/storage/MOQ limits | Rules correctly constrain |
| Validation Failure | PO exceeds budget | Feedback loop catches errors |
| Human Approval | High-risk purchase | Approval gate works |

### Running tests:
```bash
pytest tests/ -v
```

---

## Design Decisions to Defend

1. **No LangChain/LangGraph**: Unnecessary complexity for a single-agent system. The orchestration is a simple function call chain.

2. **Mock database in JSON**: Perfect for a demo. Easy to inspect, easy to reset, easy to understand. Production would use PostgreSQL.

3. **React via CDN (no build step)**: Reduces project complexity. For a demo/MVP, this eliminates npm setup entirely.

4. **Python dataclasses for PurchaseContext**: Makes the data contract explicit. Every field the rules engine needs is clearly defined.

5. **No authentication**: Out of scope per instructions. Would add JWT tokens in production.

---

## If Asked "How Would You Extend This?"

- **Scenario 2 (Partial Fulfillment)**: Add a `handle_partial_supply()` function that checks alternative suppliers and splits orders
- **Scenario 3 (Demand Change)**: Add a demand monitoring loop that compares forecast vs actuals and triggers re-evaluation
- **Scenario 4 (Constraint Blocking)**: Already partially handled — INVESTIGATE decision with constraint analysis
- **Multi-supplier support**: Extend supplier queries to return ranked alternatives
- **Audit trail**: Log all decisions with timestamps for compliance
- **Real database**: SQLAlchemy + PostgreSQL with migration scripts

---

## Common Interview Traps

**Q: "Why not let GPT decide the quantity?"**
A: "GPT might say 800 when the math says 600. In purchasing, a 200-unit overorder at $12.50/unit is a $2,500 mistake. The rules engine guarantees correctness."

**Q: "This is just if/else statements, where's the AI?"**  
A: "The AI adds value in context interpretation and explanation generation. The rules ensure correctness. This is the same pattern used in production AI systems — AI proposes, rules validate."

**Q: "What happens if the rules engine has a bug?"**  
A: "That's what the validation feedback loop is for. Even if the calculation is wrong, the post-action validation catches MOQ violations, budget overruns, and storage issues. Defense in depth."
