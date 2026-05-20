"use client";

import { useEffect, useState } from "react";
import { ReviewEditor } from "@/components/review-editor/ReviewEditor";
import { approveReviewItem, convertReviewItemToFaq, listReviewItems, updateReviewItem } from "@/lib/api-client";
import type { ReviewItem } from "@/lib/types";

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");

  async function refresh() {
    const nextItems = await listReviewItems().catch(() => []);
    setItems(nextItems);
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
        />
        {message ? <p className="status" style={{ marginTop: 14 }}>{message}</p> : null}
      </section>
    </>
  );
}
