export function MetricsPanel({ metrics }: { metrics: Record<string, number> }) {
  const keys = [
    "recall_at_20",
    "rerank_at_5",
    "citation_support_rate",
    "evidence_sufficiency_rate",
    "need_review_rate",
    "latency_p95_ms"
  ];
  return (
    <div className="grid three">
      {keys.map((key) => (
        <div className="panel metric" key={key}>
          <span className="muted">{key.replaceAll("_", " ")}</span>
          <strong>{metrics[key] === undefined ? "-" : metrics[key].toFixed(2)}</strong>
        </div>
      ))}
    </div>
  );
}
