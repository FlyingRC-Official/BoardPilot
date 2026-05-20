import type { AuditLog } from "@/lib/types";

export function AuditLogTable({ logs }: { logs: AuditLog[] }) {
  if (!logs.length) {
    return <div className="empty">No audit events recorded in this API session.</div>;
  }

  return (
    <table className="table">
      <thead>
        <tr>
          <th>Action</th>
          <th>Entity</th>
          <th>User</th>
          <th>Time</th>
        </tr>
      </thead>
      <tbody>
        {logs.slice(-12).reverse().map((log) => (
          <tr key={log.id}>
            <td>{log.action}</td>
            <td>
              {log.entity_type} <span className="muted">{log.entity_id.slice(0, 8)}</span>
            </td>
            <td>{log.user_id || "system"}</td>
            <td>{new Date(log.created_at).toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
