# AI Purchasing Agent — Purchase Recommendation Review

A FastAPI purchasing-decision service with a React interface. It evaluates proposed purchase quantities against inventory, incoming purchase orders, demand forecasts, supplier minimum-order quantities, budget and storage constraints.

**Important design choice:** purchase calculations and decisions are deterministic Python rules. Gemini is optional and is used only to produce a human-readable explanation; it is not the authority for quantities, constraints or approval decisions.

## Problem

A suggested purchase should not be executed without checking current supply, expected demand, supplier terms and operational constraints. This project turns a recommendation into an auditable decision: `ACCEPT`, `MODIFY`, `REJECT` or `INVESTIGATE`.

## Architecture

```text
React UI
   |
   v
FastAPI routes
   |
   v
Agent orchestrator
   ├── MockDatabase (JSON-backed, in-memory)
   ├── Deterministic rules engine
   │     ├── required-quantity calculation
   │     ├── supplier MOQ
   │     ├── remaining budget
   │     └── available storage
   ├── purchase-order creation
   ├── post-action validation
   └── optional Gemini explanation
```

## Decision flow

1. Load product, inventory, demand, supplier, open-PO, budget and storage context.
2. Calculate the required quantity from 30-day demand, safety stock, available inventory and incoming supply.
3. Apply MOQ, budget and storage constraints.
4. Determine the decision and risk level.
5. Create a purchase order only when the decision flow permits it.
6. Validate the created order and flag failures for investigation or approval.

The rules engine is the source of truth for business calculations. The LLM explanation is optional and can fall back to a deterministic text template.

## Technology

- Python 3.11+
- FastAPI and Pydantic
- React UI
- Deterministic Python rules engine
- JSON-backed mock data store
- Optional Google Gemini explanation
- Pytest and HTTPX
- Docker Compose

## Project structure

```text
backend/
  main.py             # FastAPI endpoints
  agent.py            # decision workflow orchestration
  database.py         # in-memory mock database
  rules_engine.py     # deterministic purchase constraints
frontend/
  index.html
  app.jsx
  styles.css
data/mock_data.json
tests/
  test_agent.py       # business-rule and workflow tests
  test_api.py         # HTTP endpoint tests
docs/
  architecture.png
  INTERVIEW_GUIDE.md
```

## Run locally

### 1. Clone and install

```bash
git clone https://github.com/san613deep/ai_buyer_agent.git
cd ai_buyer_agent
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Install backend dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Run tests

```bash
python -m pytest tests/ -q
```

The suite includes rules-engine scenarios and HTTP-level tests for health, product listing, invalid SKUs, request validation and recommendation evaluation. A passing local or GitHub Actions run is the evidence of test status; the README does not assume tests have passed in every environment.

### 3. Start the backend

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

- API root: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### 4. Start the frontend

In a second terminal:

```bash
python -m http.server 3000 --directory frontend
```

Open [http://localhost:3000](http://localhost:3000).

### 5. Docker Compose

```bash
docker compose up --build
```

Check the Compose file for service ports and local environment configuration before running.

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Service health |
| GET | `/api/products` | List products |
| GET | `/api/products/{sku}` | Product and purchasing context |
| POST | `/api/evaluate` | Evaluate a proposed purchase |
| POST | `/api/approve` | Human approval workflow |
| GET | `/api/purchase-orders` | List purchase orders |
| POST | `/api/reset` | Reset mock data |

Example evaluation request:

```json
{
  "sku": "SKU-001",
  "recommended_qty": 600
}
```

## Current limitations

- The database is a JSON-backed in-memory mock, not PostgreSQL. State changes are not durable across process restarts.
- The API does not currently implement user authentication or authorization.
- The optional Gemini integration requires a valid `GEMINI_API_KEY`; without it, the service uses a template explanation.
- The business rules are a demonstrator and should be reviewed with actual procurement policy before operational use.
- The service is a portfolio prototype, not a production procurement system.

## Future improvements

- Replace the mock store with PostgreSQL and transactional persistence.
- Add authentication, role-based authorization and audit history.
- Add idempotency keys for purchase-order creation.
- Add integration tests against a disposable database.
- Add structured logging, metrics and deployment health checks.
