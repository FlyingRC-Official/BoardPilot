export function MetricsPanel({ metrics }: { metrics: Record<string, number | Record<string, number>> }) {
  const keys = [
    "recall_at_20",
    "rerank_at_5",
    "citation_support_rate",
    "evidence_sufficiency_rate",
    "need_review_rate",
    "latency_p95_ms"
  ];
  const failureDistribution = metrics.failure_category_distribution;
  const failureRows =
    typeof failureDistribution === "object"
      ? Object.entries(failureDistribution).filter(([, value]) => typeof value === "number" && value > 0)
      : [];

  return (
    <>
      <div className="grid three">
        {keys.map((key) => (
          <div className="panel metric" key={key}>
            <span className="muted">{key.replaceAll("_", " ")}</span>
            <strong>{typeof metrics[key] !== "number" ? "-" : metrics[key].toFixed(2)}</strong>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 16 }}>
        <h3>Failure Categories</h3>
        {failureRows.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Category</th>
                <th>Count</th>
              </tr>
            </thead>
            <tbody>
              {failureRows.map(([category, count]) => (
                <tr key={category}>
                  <td>{category.replaceAll("_", " ")}</td>
                  <td>{count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty">No failure categories were recorded for this run.</div>
        )}
      </div>
    </>
  );
}
