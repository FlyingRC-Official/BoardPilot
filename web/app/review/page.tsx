"use client";

import { useEffect, useState } from "react";
import { AuditLogTable } from "@/components/review-editor/AuditLogTable";
import { ReviewEditor } from "@/components/review-editor/ReviewEditor";
import {
  approveReviewItem,
  convertReviewItemToEvalCase,
  convertReviewItemToFaq,
  listAuditLogs,
  listReviewItems,
  updateReviewItem
} from "@/lib/api-client";
import type { AuditLog, ReviewItem } from "@/lib/types";

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");

  async function refresh() {
    const nextItems = await listReviewItems().catch(() => []);
    setItems(nextItems);
    setAuditLogs(await listAuditLogs().catch(() => []));
    setEdits((current) => ({
      ...current,
      ...Object.fromEntries(nextItems.map((item) => [item.id, current[item.id] || item.edited_answer_text || ""]))
    }));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function approve(id: string) {
    await approveReviewItem(id);
    await refresh();
    setMessage("Review item approved with an audit-log decision.");
  }

  async function toFaq(id: string) {
    if (edits[id]?.trim()) {
      await updateReviewItem(id, { edited_answer_text: edits[id].trim() });
    }
    await convertReviewItemToFaq(id);
    await refresh();
    setMessage("Review item converted to an ApprovedFAQ source and re-ingested.");
  }

  async function toEval(id: string) {
    if (edits[id]?.trim()) {
      await updateReviewItem(id, { edited_answer_text: edits[id].trim() });
    }
    await convertReviewItemToEvalCase(id);
    await refresh();
    setMessage("Review item converted to an EvalCase with expected evidence.");
  }

  async function saveEdit(id: string) {
    await updateReviewItem(id, { edited_answer_text: edits[id] || "" });
    await refresh();
    setMessage("Reviewer edit saved.");
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Review</h1>
          <p>Handle low-confidence answers, insufficient evidence, eval failures, and user feedback before they become FAQs or regression cases.</p>
        </div>
      </header>
      <section className="panel">
        <h2>Queue</h2>
        <ReviewEditor
          items={items}
          edits={edits}
          onEdit={(id, value) => setEdits((current) => ({ ...current, [id]: value }))}
          onSaveEdit={saveEdit}
          onApprove={approve}
          onToFaq={toFaq}
          onToEval={toEval}
        />
        {message ? <p className="status" style={{ marginTop: 14 }}>{message}</p> : null}
      </section>
      <section className="panel" style={{ marginTop: 16 }}>
        <h2>Audit Log</h2>
        <AuditLogTable logs={auditLogs} />
      </section>
    </>
  );
}
