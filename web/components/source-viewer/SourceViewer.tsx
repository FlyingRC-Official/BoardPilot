import type { Source } from "@/lib/types";

export function SourceViewer({ sources }: { sources: Source[] }) {
  if (!sources.length) {
    return <div className="empty">No sources have been created in this API session.</div>;
  }

  return (
    <table className="table">
      <thead>
        <tr>
          <th>Title</th>
          <th>Type</th>
          <th>Trust</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {sources.map((source) => (
          <tr key={source.id}>
            <td>{source.title}</td>
            <td>{source.source_type}</td>
            <td>{source.trust_level}</td>
            <td>{source.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

