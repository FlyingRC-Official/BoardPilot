"use client";

import { useEffect, useState } from "react";
import { EvidenceList } from "@/components/evidence/EvidenceList";
import { RetrievalTrace } from "@/components/retrieval-trace/RetrievalTrace";
import { AuditLogTable } from "@/components/review-editor/AuditLogTable";
import { ReviewEditor } from "@/components/review-editor/ReviewEditor";
import {
  approveReviewItem,
  convertReviewItemToEvalCase,
  convertReviewItemToFaq,
  getReviewItemDetail,
  listAuditLogs,
  listReviewItems,
  markReviewSourceUpdateNeeded,
  updateReviewItem
} from "@/lib/api-client";
import type { AuditLog, ReviewItem, ReviewItemDetail } from "@/lib/types";

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [failureCategories, setFailureCategories] = useState<Record<string, string>>({});
  const [detail, setDetail] = useState<ReviewItemDetail | null>(null);
  const [message, setMessage] = useState("");

  async function refresh() {
    const nextItems = await listReviewItems().catch(() => []);
    setItems(nextItems);
    setAuditLogs(await listAuditLogs().catch(() => []));
    setEdits((current) => ({
      ...current,
      ...Object.fromEntries(nextItems.map((item) => [item.id, current[item.id] || item.edited_answer_text || ""]))
    }));
    setNotes((current) => ({
      ...current,
      ...Object.fromEntries(nextItems.map((item) => [item.id, current[item.id] || item.reviewer_notes || ""]))
    }));
    setFailureCategories((current) => ({
      ...current,
      ...Object.fromEntries(nextItems.map((item) => [item.id, current[item.id] || item.failure_category || ""]))
    }));
  }

  async function saveDraft(id: string) {
    await updateReviewItem(id, {
      edited_answer_text: edits[id] || "",
      reviewer_notes: notes[id] || "",
      failure_category: failureCategories[id] || undefined
    });
  }

  useEffect(() => {
    refresh();
  }, []);

  async function approve(id: string) {
    await saveDraft(id);
    await approveReviewItem(id, failureCategories[id] || "human_policy_required");
    await refresh();
    setMessage("Review item approved with an audit-log decision.");
  }

  async function toFaq(id: string) {
    await saveDraft(id);
    await convertReviewItemToFaq(id);
    await refresh();
    setMessage("Review item converted to an ApprovedFAQ source and re-ingested.");
  }

  async function toEval(id: string) {
    await saveDraft(id);
    await convertReviewItemToEvalCase(id);
    await refresh();
    setMessage("Review item converted to an EvalCase with expected evidence.");
  }

  async function saveEdit(id: string) {
    await saveDraft(id);
    await refresh();
    setMessage("Reviewer fields saved.");
  }

  async function inspect(id: string) {
    setDetail(await getReviewItemDetail(id));
    setMessage("Review detail loaded.");
  }

  async function sourceUpdateNeeded(id: string) {
    await saveDraft(id);
    await markReviewSourceUpdateNeeded(id, failureCategories[id] || "stale_source");
    await refresh();
    setMessage("Review item marked as needing a source update.");
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
          notes={notes}
          failureCategories={failureCategories}
          onEdit={(id, value) => setEdits((current) => ({ ...current, [id]: value }))}
          onNotesChange={(id, value) => setNotes((current) => ({ ...current, [id]: value }))}
          onFailureChange={(id, value) => setFailureCategories((current) => ({ ...current, [id]: value }))}
          onSaveEdit={saveEdit}
          onApprove={approve}
          onToFaq={toFaq}
          onToEval={toEval}
          onInspect={inspect}
          onSourceUpdateNeeded={sourceUpdateNeeded}
        />
        {message ? <p className="status" style={{ marginTop: 14 }}>{message}</p> : null}
      </section>
      {detail ? (
        <section className="panel" style={{ marginTop: 16 }}>
          <h2>Review Detail</h2>
          <div className="grid two">
            <div>
              <h3>Question</h3>
              <p>{detail.question?.raw_text || "No linked question."}</p>
              <h3>Generated Answer</h3>
              <p>{detail.answer?.answer_text || "No linked answer."}</p>
            </div>
            <div>
              <h3>Evidence</h3>
              <EvidenceList evidence={detail.evidence} />
            </div>
          </div>
          <div style={{ marginTop: 16 }}>
            <h3>Retrieval Trace</h3>
            <RetrievalTrace candidates={detail.candidates} />
          </div>
        </section>
      ) : null}
      <section className="panel" style={{ marginTop: 16 }}>
        <h2>Audit Log</h2>
        <AuditLogTable logs={auditLogs} />
      </section>
    </>
  );
}
