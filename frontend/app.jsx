const { useState, useEffect } = React;

const API_BASE = "http://localhost:8000";

// ── Workflow Step Indicator ─────────────────────────────────────────
function WorkflowSteps({ currentStep }) {
  const steps = [
    "Select Product",
    "Enter Qty",
    "Agent Evaluates",
    "Create PO",
    "Validate PO",
    "Result",
  ];
  return (
    <div className="workflow-steps mb-3">
      {steps.map((s, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span className="workflow-arrow">›</span>}
          <span
            className={`workflow-step ${
              i === currentStep ? "active" : i < currentStep ? "done" : ""
            }`}
          >
            {i < currentStep ? "✓ " : ""}
            {s}
          </span>
        </React.Fragment>
      ))}
    </div>
  );
}

// ── Data Item Component ─────────────────────────────────────────────
function DataItem({ label, value, valueColor }) {
  return (
    <div className="data-item">
      <span className="label">{label}</span>
      <span className="value" style={valueColor ? { color: valueColor } : {}}>
        {value}
      </span>
    </div>
  );
}

// ── Main App ────────────────────────────────────────────────────────
function App() {
  const [products, setProducts] = useState([]);
  const [selectedSku, setSelectedSku] = useState("");
  const [productDetails, setProductDetails] = useState(null);
  const [recommendedQty, setRecommendedQty] = useState(800);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState(null);
  const [step, setStep] = useState(0);

  // Load products on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/products`)
      .then((r) => r.json())
      .then(setProducts)
      .catch((e) => setError("Cannot connect to backend. Is it running on port 8000?"));
  }, []);

  // Load product details when selected
  useEffect(() => {
    if (!selectedSku) {
      setProductDetails(null);
      return;
    }
    setStep(1);
    fetch(`${API_BASE}/api/products/${selectedSku}`)
      .then((r) => r.json())
      .then(setProductDetails)
      .catch(console.error);
  }, [selectedSku]);

  const evaluate = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setStep(2);

    try {
      const resp = await fetch(`${API_BASE}/api/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sku: selectedSku, recommended_qty: recommendedQty }),
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || "Evaluation failed");
      }

      const data = await resp.json();
      setResult(data);
      setStep(5);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const approveHighRisk = async () => {
    setApproving(true);
    setError(null);

    try {
      const resp = await fetch(`${API_BASE}/api/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sku: selectedSku,
          recommended_qty: recommendedQty,
        }),
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || "Approval failed");
      }

      const data = await resp.json();
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setApproving(false);
    }
  };

  const resetAll = async () => {
    await fetch(`${API_BASE}/api/reset`, { method: "POST" });
    setResult(null);
    setSelectedSku("");
    setProductDetails(null);
    setRecommendedQty(800);
    setStep(0);
    setError(null);
    // Reload products
    const resp = await fetch(`${API_BASE}/api/products`);
    setProducts(await resp.json());
  };

  return (
    <div>
      {/* Header */}
      <header className="app-header">
        <div className="container">
          <div className="d-flex justify-content-between align-items-center">
            <div>
              <h1>AI Purchasing Agent</h1>
              <p className="subtitle">
                Scenario 1 — Purchase Recommendation Review
              </p>
            </div>
            <button className="btn-outline-light-custom" onClick={resetAll}>
              ↺ Reset Data
            </button>
          </div>
        </div>
      </header>

      <div className="container py-4">
        <WorkflowSteps currentStep={step} />

        <div className="row g-4">
          {/* ── Left Column: Input ──────────────────────────────────── */}
          <div className="col-lg-5">
            {/* Product Selection */}
            <div className="card-dark mb-3">
              <h2>① Select Product</h2>
              {products.map((p) => (
                <div
                  key={p.sku}
                  className={`product-option ${
                    selectedSku === p.sku ? "selected" : ""
                  }`}
                  onClick={() => setSelectedSku(p.sku)}
                >
                  <div className="product-name">{p.name}</div>
                  <div className="product-sku">
                    {p.sku} · ${p.unit_cost}/unit · {p.category}
                  </div>
                </div>
              ))}
            </div>

            {/* Quantity Input */}
            {selectedSku && (
              <div className="card-dark mb-3">
                <h2>② System Recommends</h2>
                <label
                  className="form-label"
                  style={{ color: "var(--text-secondary)", fontSize: "0.82rem" }}
                >
                  Recommended purchase quantity
                </label>
                <input
                  type="number"
                  className="form-control-dark w-100 mb-3"
                  value={recommendedQty}
                  min={1}
                  onChange={(e) =>
                    setRecommendedQty(parseInt(e.target.value) || 0)
                  }
                />
                <button
                  className="btn-accent w-100"
                  onClick={evaluate}
                  disabled={loading || !recommendedQty}
                >
                  {loading ? (
                    <>
                      <span className="spinner-accent me-2"></span> Agent
                      Evaluating…
                    </>
                  ) : (
                    "▶ Evaluate Recommendation"
                  )}
                </button>
              </div>
            )}

            {/* Context Panel */}
            {productDetails && (
              <div className="card-dark">
                <h3>Current Data</h3>
                <div className="data-grid">
                  <DataItem
                    label="On Hand"
                    value={productDetails.inventory?.on_hand}
                  />
                  <DataItem
                    label="Available"
                    value={productDetails.inventory?.available}
                  />
                  <DataItem
                    label="30-Day Demand"
                    value={productDetails.demand_forecast?.next_30_days}
                  />
                  <DataItem
                    label="Safety Stock"
                    value={productDetails.demand_forecast?.safety_stock}
                  />
                  <DataItem
                    label="Supplier MOQ"
                    value={productDetails.supplier?.min_order_qty}
                  />
                  <DataItem
                    label="Lead Time"
                    value={`${productDetails.supplier?.lead_time_days}d`}
                  />
                  <DataItem
                    label="Budget Left"
                    value={`$${productDetails.budget?.remaining?.toLocaleString()}`}
                  />
                  <DataItem
                    label="Storage Avail."
                    value={`${productDetails.storage?.available_m3} m³`}
                  />
                </div>
                {productDetails.open_purchase_orders?.length > 0 && (
                  <div className="mt-3">
                    <small
                      style={{
                        color: "var(--text-secondary)",
                        textTransform: "uppercase",
                        fontSize: "0.7rem",
                        letterSpacing: "0.3px",
                      }}
                    >
                      Open Purchase Orders
                    </small>
                    <table className="po-table mt-1">
                      <thead>
                        <tr>
                          <th>PO</th>
                          <th>Qty</th>
                          <th>Status</th>
                          <th>ETA</th>
                        </tr>
                      </thead>
                      <tbody>
                        {productDetails.open_purchase_orders.map((po) => (
                          <tr key={po.po_id}>
                            <td>{po.po_id}</td>
                            <td>{po.quantity}</td>
                            <td>
                              <span
                                className={`po-status po-status-${po.status}`}
                              >
                                {po.status}
                              </span>
                            </td>
                            <td>{po.expected_delivery}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ── Right Column: Result ────────────────────────────────── */}
          <div className="col-lg-7">
            {error && (
              <div
                className="card-dark mb-3"
                style={{
                  borderColor: "var(--danger)",
                  background: "rgba(239, 68, 68, 0.06)",
                }}
              >
                <strong style={{ color: "var(--danger)" }}>Error:</strong>{" "}
                {error}
              </div>
            )}

            {result && (
              <>
                {/* Decision Header */}
                <div className="card-dark mb-3">
                  <div className="d-flex justify-content-between align-items-start mb-3">
                    <div>
                      <h2 className="mb-1">Agent Decision</h2>
                      <div className="d-flex align-items-center gap-2">
                        <span
                          className={`badge-decision badge-${result.decision.action}`}
                        >
                          {result.decision.action}
                        </span>
                        <span
                          className={`badge-risk badge-risk-${result.decision.risk_level}`}
                        >
                          {result.decision.risk_level} Risk
                        </span>
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--text-secondary)",
                        }}
                      >
                        Recommended → Adjusted
                      </div>
                      <div style={{ fontSize: "1.3rem", fontWeight: 700 }}>
                        <span style={{ color: "var(--text-secondary)" }}>
                          {result.recommended_qty}
                        </span>{" "}
                        →{" "}
                        <span style={{ color: "var(--accent-light)" }}>
                          {result.decision.adjusted_qty}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Explanation */}
                  <div className="explanation-box mb-3">
                    {result.explanation}
                  </div>

                  {/* Reasons */}
                  {result.decision.reasons.length > 0 && (
                    <div className="mb-2">
                      <small
                        style={{
                          color: "var(--text-secondary)",
                          textTransform: "uppercase",
                          fontSize: "0.7rem",
                        }}
                      >
                        Reasoning
                      </small>
                      <ul className="reason-list">
                        {result.decision.reasons.map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Constraints */}
                  {result.decision.constraints_hit.length > 0 && (
                    <div>
                      <small
                        style={{
                          color: "var(--warning)",
                          textTransform: "uppercase",
                          fontSize: "0.7rem",
                        }}
                      >
                        Constraints Applied
                      </small>
                      <ul className="reason-list">
                        {result.decision.constraints_hit.map((c, i) => (
                          <li key={i} style={{ color: "var(--warning)" }}>
                            {c}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Human Approval Required */}
                {result.decision.status === "pending_human_approval" && (
                  <div className="card-dark mb-3">
                    <div className="approval-banner">
                      <h3 style={{ color: "var(--warning)" }}>
                        ⚠️ Human Approval Required
                      </h3>
                      <p
                        style={{
                          fontSize: "0.85rem",
                          color: "var(--text-secondary)",
                          marginBottom: "1rem",
                        }}
                      >
                        This purchase has been flagged as HIGH RISK. A human
                        buyer must review and approve before the Purchase Order
                        can be created.
                      </p>
                      <div className="d-flex gap-2">
                        <button
                          className="btn-approve"
                          onClick={approveHighRisk}
                          disabled={approving}
                        >
                          {approving ? (
                            <>
                              <span className="spinner-accent me-2"></span>
                              Processing…
                            </>
                          ) : (
                            "✓ Approve & Create PO"
                          )}
                        </button>
                        <button
                          className="btn-outline-light-custom"
                          onClick={() => {
                            setResult({
                              ...result,
                              decision: {
                                ...result.decision,
                                status: "rejected_by_human",
                              },
                            });
                          }}
                        >
                          ✕ Reject
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Purchase Order */}
                {result.purchase_order && (
                  <div className="card-dark mb-3">
                    <h3>Purchase Order Created</h3>
                    <div className="data-grid">
                      <DataItem
                        label="PO ID"
                        value={result.purchase_order.po_id}
                      />
                      <DataItem
                        label="Quantity"
                        value={result.purchase_order.quantity}
                      />
                      <DataItem
                        label="Unit Cost"
                        value={`$${result.purchase_order.unit_cost}`}
                      />
                      <DataItem
                        label="Total Cost"
                        value={`$${result.purchase_order.total_cost?.toLocaleString()}`}
                      />
                      <DataItem
                        label="Status"
                        value={result.purchase_order.status}
                      />
                      <DataItem
                        label="Expected Delivery"
                        value={result.purchase_order.expected_delivery}
                      />
                    </div>
                  </div>
                )}

                {/* Validation Result */}
                {result.validation && (
                  <div className="card-dark mb-3">
                    <h3>Post-Action Validation</h3>
                    <div
                      className={
                        result.validation.valid
                          ? "validation-pass"
                          : "validation-fail"
                      }
                    >
                      <div
                        style={{
                          fontWeight: 700,
                          fontSize: "0.9rem",
                          marginBottom: "0.5rem",
                        }}
                      >
                        {result.validation.valid ? "✓ PASSED" : "✕ FAILED"}
                      </div>

                      {result.validation.issues?.length > 0 && (
                        <div className="mb-2">
                          <small style={{ fontWeight: 600 }}>Issues:</small>
                          <ul className="reason-list">
                            {result.validation.issues.map((iss, i) => (
                              <li
                                key={i}
                                style={{ color: "var(--danger)" }}
                              >
                                {iss}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {result.validation.warnings?.length > 0 && (
                        <div className="mb-2">
                          <small style={{ fontWeight: 600 }}>Warnings:</small>
                          <ul className="reason-list">
                            {result.validation.warnings.map((w, i) => (
                              <li
                                key={i}
                                style={{ color: "var(--warning)" }}
                              >
                                {w}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <div>
                        <small
                          style={{
                            color: "var(--text-secondary)",
                            fontSize: "0.75rem",
                          }}
                        >
                          Checks: {result.validation.checks_performed?.join(", ")}
                        </small>
                      </div>
                    </div>
                  </div>
                )}

                {/* Context Used */}
                {result.context && (
                  <div className="card-dark">
                    <h3>Context Gathered by Agent</h3>
                    <div className="data-grid">
                      <DataItem
                        label="Available Inventory"
                        value={result.context.available_inventory}
                      />
                      <DataItem
                        label="Incoming (Open POs)"
                        value={result.context.incoming_qty}
                      />
                      <DataItem
                        label="30-Day Demand"
                        value={result.context.demand_next_30}
                      />
                      <DataItem
                        label="Safety Stock"
                        value={result.context.safety_stock}
                      />
                      <DataItem
                        label="Coverage Days"
                        value={`${result.context.coverage_days} days`}
                        valueColor={
                          result.context.coverage_days < 14
                            ? "var(--danger)"
                            : result.context.coverage_days < 30
                            ? "var(--warning)"
                            : "var(--success)"
                        }
                      />
                      <DataItem
                        label="Supplier MOQ"
                        value={result.context.supplier_moq}
                      />
                      <DataItem
                        label="Lead Time"
                        value={`${result.context.supplier_lead_time_days} days`}
                      />
                      <DataItem
                        label="Budget Remaining"
                        value={`$${result.context.budget_remaining?.toLocaleString()}`}
                      />
                    </div>
                  </div>
                )}
              </>
            )}

            {!result && !error && (
              <div
                className="card-dark d-flex align-items-center justify-content-center"
                style={{ minHeight: "300px" }}
              >
                <div
                  style={{
                    textAlign: "center",
                    color: "var(--text-secondary)",
                  }}
                >
                  <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>
                    🤖
                  </div>
                  <p style={{ fontSize: "0.9rem" }}>
                    Select a product and enter a recommended quantity.
                    <br />
                    The agent will evaluate and take action.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
