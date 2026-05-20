"use client";

import { useEffect, useState } from "react";
import { ReviewEditor } from "@/components/review-editor/ReviewEditor";
import { approveReviewItem, listReviewItems } from "@/lib/api-client";
import type { ReviewItem } from "@/lib/types";

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [message, setMessage] = useState("");

  async function refresh() {
    setItems(await listReviewItems().catch(() => []));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function approve(id: string) {
    await approveReviewItem(id);
    await refresh();
    setMessage("Review item approved with an audit-log decision.");
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
        <ReviewEditor items={items} onApprove={approve} />
        {message ? <p className="status" style={{ marginTop: 14 }}>{message}</p> : null}
      </section>
    </>
  );
}

