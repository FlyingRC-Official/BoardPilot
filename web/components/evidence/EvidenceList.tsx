import type { Evidence } from "@/lib/types";

export function EvidenceList({ evidence }: { evidence: Evidence[] }) {
  if (!evidence.length) {
    return <div className="empty">No saved evidence yet.</div>;
  }

  return (
    <div className="evidence-list">
      {evidence.map((item) => (
        <article className="evidence-item" key={item.id}>
          <strong>E{item.rank}</strong>
          <span className="muted"> score {item.score.toFixed(2)}</span>
          <blockquote>{item.quote}</blockquote>
        </article>
      ))}
    </div>
  );
}

