import type { ReviewItem } from "@/lib/types";

export function ReviewEditor({
  items,
  onApprove,
  onToFaq,
  onToEval,
  edits,
  onEdit,
  onSaveEdit
}: {
  items: ReviewItem[];
  onApprove: (id: string) => void;
  onToFaq: (id: string) => void;
  onToEval: (id: string) => void;
  edits: Record<string, string>;
  onEdit: (id: string, value: string) => void;
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
          <th>Failure</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id}>
            <td>{item.source_type}</td>
            <td>
              <span className="status warn">{item.status}</span>
            </td>
            <td>{item.failure_category || "unassigned"}</td>
            <td>
              <textarea
                className="textarea"
                style={{ minHeight: 72, marginBottom: 8 }}
                value={edits[item.id] || ""}
                onChange={(event) => onEdit(item.id, event.target.value)}
                placeholder="Reviewer-edited answer for FAQ conversion"
              />
              <button className="button secondary" onClick={() => onApprove(item.id)}>
                Approve
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
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
