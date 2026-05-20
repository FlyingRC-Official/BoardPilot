import type { RetrievalCandidate } from "@/lib/types";

export function RetrievalTrace({ candidates }: { candidates: RetrievalCandidate[] }) {
  const reranked = candidates.filter((candidate) => candidate.stage === "reranked").slice(0, 8);
  if (!reranked.length) {
    return <div className="empty">Retrieval trace appears after a question runs.</div>;
  }

  return (
    <div className="trace-list">
      {reranked.map((candidate) => (
        <div className="trace-item" key={candidate.id}>
          <strong>#{candidate.rank}</strong>
          <span className="muted">{candidate.chunk_id.slice(0, 8)}</span>
          <span>{candidate.rerank_score.toFixed(2)}</span>
        </div>
      ))}
    </div>
  );
}

