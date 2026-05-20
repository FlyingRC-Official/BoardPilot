import type { ReviewItem } from "@/lib/types";

export function ReviewEditor({ items, onApprove }: { items: ReviewItem[]; onApprove: (id: string) => void }) {
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
              <button className="button secondary" onClick={() => onApprove(item.id)}>
                Approve
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

