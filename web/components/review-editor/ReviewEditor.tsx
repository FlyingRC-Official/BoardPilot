import type { ReviewItem } from "@/lib/types";

export const FAILURE_CATEGORIES = [
  "missing_source",
  "stale_source",
  "bad_parse",
  "bad_chunk",
  "bad_query_normalization",
  "bad_metadata_filter",
  "bad_keyword_recall",
  "bad_vector_recall",
  "bad_merge_dedup",
  "bad_rerank",
  "insufficient_evidence",
  "unsupported_claim",
  "generation_error",
  "product_alias_missing",
  "human_policy_required"
];

export function ReviewEditor({
  items,
  onApprove,
  onReject,
  onToFaq,
  onToEval,
  onInspect,
  onSourceUpdateNeeded,
  edits,
  notes,
  failureCategories,
  onEdit,
  onNotesChange,
  onFailureChange,
  onSaveEdit
}: {
  items: ReviewItem[];
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onToFaq: (id: string) => void;
  onToEval: (id: string) => void;
  onInspect: (id: string) => void;
  onSourceUpdateNeeded: (id: string) => void;
  edits: Record<string, string>;
  notes: Record<string, string>;
  failureCategories: Record<string, string>;
  onEdit: (id: string, value: string) => void;
  onNotesChange: (id: string, value: string) => void;
  onFailureChange: (id: string, value: string) => void;
  onSaveEdit: (id: string) => void;
}) {
  if (!items.length) {
    return <div className="empty">The review queue is empty.</div>;
  }

  return (
    <table className="table">
      <thead>
        <tr>
          <th>Type</th>
          <th>Status</th>
          <th>Review Fields</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id}>
            <td>{item.source_type}</td>
            <td>
              <span className="status warn">{item.status}</span>
            </td>
            <td>
              <select
                className="select"
                style={{ marginBottom: 8 }}
                value={failureCategories[item.id] || item.failure_category || ""}
                onChange={(event) => onFailureChange(item.id, event.target.value)}
              >
                <option value="">Unassigned</option>
                {FAILURE_CATEGORIES.map((category) => (
                  <option key={category} value={category}>{category}</option>
                ))}
              </select>
              <textarea
                className="textarea"
                style={{ minHeight: 72, marginBottom: 8 }}
                value={edits[item.id] || ""}
                onChange={(event) => onEdit(item.id, event.target.value)}
                placeholder="Reviewer-edited answer for FAQ or Eval conversion"
              />
              <textarea
                className="textarea"
                style={{ minHeight: 64, marginBottom: 8 }}
                value={notes[item.id] || ""}
                onChange={(event) => onNotesChange(item.id, event.target.value)}
                placeholder="Reviewer notes"
              />
              <button className="button secondary" onClick={() => onApprove(item.id)}>
                Approve
              </button>
              <button className="button secondary" style={{ marginLeft: 8 }} onClick={() => onReject(item.id)}>
                Reject
              </button>
              <button className="button secondary" style={{ marginLeft: 8 }} onClick={() => onSaveEdit(item.id)}>
                Save Edit
              </button>
              <button className="button secondary" style={{ marginLeft: 8 }} onClick={() => onToFaq(item.id)}>
                To FAQ
              </button>
              <button className="button secondary" style={{ marginLeft: 8 }} onClick={() => onToEval(item.id)}>
                To Eval
              </button>
              <button className="button secondary" style={{ marginLeft: 8 }} onClick={() => onInspect(item.id)}>
                Details
              </button>
              <button className="button secondary" style={{ marginLeft: 8 }} onClick={() => onSourceUpdateNeeded(item.id)}>
                Source Update
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
