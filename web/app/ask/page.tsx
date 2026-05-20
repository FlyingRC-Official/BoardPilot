"use client";

import { FormEvent, useEffect, useState } from "react";
import { EvidenceList } from "@/components/evidence/EvidenceList";
import { RetrievalTrace } from "@/components/retrieval-trace/RetrievalTrace";
import { askQuestion, listProducts } from "@/lib/api-client";
import type { AskResponse, Product } from "@/lib/types";

export default function AskPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [productId, setProductId] = useState("");
  const [question, setQuestion] = useState("Can I power servos from the USB connector?");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listProducts().then(setProducts).catch(() => setProducts([]));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await askQuestion({ question, product_id: productId || undefined });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ask request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Ask</h1>
          <p>Run hardware support questions through retrieval, rerank, saved evidence, citation generation, and review routing.</p>
        </div>
      </header>
      <section className="grid two">
        <div className="panel">
          <h2>Question</h2>
          <form className="form" onSubmit={submit}>
            <label className="field">
              <span>Product</span>
              <select className="select" value={productId} onChange={(event) => setProductId(event.target.value)}>
                <option value="">No hard product filter</option>
                {products.map((product) => (
                  <option value={product.id} key={product.id}>
                    {product.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Question text</span>
              <textarea className="textarea" value={question} onChange={(event) => setQuestion(event.target.value)} />
            </label>
            <div className="button-row">
              <button className="button" disabled={loading || !question.trim()}>
                {loading ? "Running..." : "Run Ask"}
              </button>
            </div>
            {error ? <p className="status danger">{error}</p> : null}
          </form>
        </div>
        <div className="panel">
          <h2>Candidate Answer</h2>
          {result ? (
            <div className="grid">
              <p>{result.answer.answer_text}</p>
              <p>
                <span className={result.answer.evidence_sufficiency === "sufficient" ? "status" : "status warn"}>
                  {result.answer.evidence_sufficiency}
                </span>{" "}
                <span className="muted">confidence {result.answer.confidence.toFixed(2)}</span>
              </p>
              {result.review_item ? <p className="status warn">Routed to review: {result.review_item.failure_category}</p> : null}
            </div>
          ) : (
            <div className="empty">Submit a question to generate a citation-backed candidate answer.</div>
          )}
        </div>
      </section>
      <section className="grid two" style={{ marginTop: 16 }}>
        <div className="panel">
          <h2>Evidence Pack</h2>
          <EvidenceList evidence={result?.evidence || []} />
        </div>
        <div className="panel">
          <h2>Retrieval Trace</h2>
          <RetrievalTrace candidates={result?.candidates || []} />
        </div>
      </section>
    </>
  );
}

