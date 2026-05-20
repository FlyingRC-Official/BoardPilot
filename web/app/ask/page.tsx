"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { EvidenceList } from "@/components/evidence/EvidenceList";
import { RetrievalTrace } from "@/components/retrieval-trace/RetrievalTrace";
import {
  askQuestion,
  listProducts,
  listSources,
  listSourceVersionArtifacts,
  listSourceVersions,
  sendAnswerFeedback
} from "@/lib/api-client";
import type { AskResponse, Product, Source, SourceArtifact } from "@/lib/types";

type AttachmentDraft = {
  artifact_id: string;
  attachment_type: string;
  description?: string;
  label: string;
};

export default function AskPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [productId, setProductId] = useState("");
  const [question, setQuestion] = useState("Can I power servos from the USB connector?");
  const [metadataFilters, setMetadataFilters] = useState("{}");
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [availableArtifacts, setAvailableArtifacts] = useState<SourceArtifact[]>([]);
  const [selectedArtifactId, setSelectedArtifactId] = useState("");
  const [attachmentType, setAttachmentType] = useState("log");
  const [attachmentDescription, setAttachmentDescription] = useState("");
  const [attachments, setAttachments] = useState<AttachmentDraft[]>([]);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [feedbackNote, setFeedbackNote] = useState("");
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listProducts().then(setProducts).catch(() => setProducts([]));
    listSources().then(setSources).catch(() => setSources([]));
  }, []);

  const filteredSources = useMemo(
    () => (productId ? sources.filter((source) => source.product_id === productId) : sources),
    [productId, sources]
  );
  const selectedSource = sources.find((source) => source.id === selectedSourceId);

  useEffect(() => {
    if (!selectedSourceId && filteredSources[0]) {
      setSelectedSourceId(filteredSources[0].id);
      return;
    }
    if (selectedSourceId && filteredSources.length && !filteredSources.some((source) => source.id === selectedSourceId)) {
      setSelectedSourceId(filteredSources[0].id);
    }
    if (selectedSourceId && !filteredSources.length) {
      setSelectedSourceId("");
    }
  }, [filteredSources, selectedSourceId]);

  useEffect(() => {
    let cancelled = false;
    async function loadArtifacts() {
      if (!selectedSourceId) {
        setAvailableArtifacts([]);
        setSelectedArtifactId("");
        return;
      }
      const versions = await listSourceVersions(selectedSourceId).catch(() => []);
      const latestVersion = versions[versions.length - 1];
      const nextArtifacts = latestVersion ? await listSourceVersionArtifacts(latestVersion.id).catch(() => []) : [];
      if (!cancelled) {
        setAvailableArtifacts(nextArtifacts);
        setSelectedArtifactId(nextArtifacts[0]?.id || "");
      }
    }
    loadArtifacts();
    return () => {
      cancelled = true;
    };
  }, [selectedSourceId]);

  function addAttachment() {
    const artifact = availableArtifacts.find((candidate) => candidate.id === selectedArtifactId);
    if (!artifact) {
      setError("Select an artifact to attach");
      return;
    }
    if (attachments.some((attachment) => attachment.artifact_id === artifact.id)) {
      setError("Artifact is already attached");
      return;
    }
    setAttachments((current) => [
      ...current,
      {
        artifact_id: artifact.id,
        attachment_type: attachmentType,
        description: attachmentDescription.trim() || undefined,
        label: `${selectedSource?.title || "Source"} · ${artifact.artifact_type} · ${artifact.id.slice(0, 8)}`
      }
    ]);
    setAttachmentDescription("");
    setError("");
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      let parsedFilters: Record<string, unknown> = {};
      try {
        parsedFilters = metadataFilters.trim() ? JSON.parse(metadataFilters) : {};
      } catch {
        setError("Metadata filters JSON is invalid");
        setLoading(false);
        return;
      }
      const response = await askQuestion({
        question,
        product_id: productId || undefined,
        metadata_filters_json: parsedFilters,
        attachments: attachments.map(({ label: _label, ...attachment }) => attachment)
      });
      setResult(response);
      setFeedbackNote("");
      setFeedbackMessage("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ask request failed");
    } finally {
      setLoading(false);
    }
  }

  async function submitFeedback(feedbackType: string) {
    if (!result) {
      return;
    }
    const reviewItem = await sendAnswerFeedback(result.answer.id, {
      feedback_type: feedbackType,
      notes: feedbackNote || feedbackType.replaceAll("_", " ")
    });
    setFeedbackMessage(`Feedback saved to review queue: ${reviewItem.source_type}`);
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
            <label className="field">
              <span>Metadata filters JSON</span>
              <textarea
                className="textarea"
                style={{ minHeight: 84 }}
                value={metadataFilters}
                onChange={(event) => setMetadataFilters(event.target.value)}
              />
            </label>
            <div className="attachment-box">
              <h3>Attachments</h3>
              <div className="grid two compact-grid">
                <label className="field">
                  <span>Source</span>
                  <select
                    className="select"
                    value={selectedSourceId}
                    onChange={(event) => setSelectedSourceId(event.target.value)}
                  >
                    {filteredSources.length ? null : <option value="">No sources available</option>}
                    {filteredSources.map((source) => (
                      <option value={source.id} key={source.id}>
                        {source.title}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>Artifact</span>
                  <select
                    className="select"
                    value={selectedArtifactId}
                    onChange={(event) => setSelectedArtifactId(event.target.value)}
                    disabled={!availableArtifacts.length}
                  >
                    {availableArtifacts.length ? null : <option value="">No artifacts on latest version</option>}
                    {availableArtifacts.map((artifact) => (
                      <option value={artifact.id} key={artifact.id}>
                        {artifact.artifact_type} · {artifact.mime_type} · {artifact.id.slice(0, 8)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="grid two compact-grid">
                <label className="field">
                  <span>Type</span>
                  <select className="select" value={attachmentType} onChange={(event) => setAttachmentType(event.target.value)}>
                    <option value="log">Log</option>
                    <option value="image">Image</option>
                    <option value="ticket">Ticket</option>
                    <option value="manual">Manual</option>
                    <option value="other">Other</option>
                  </select>
                </label>
                <label className="field">
                  <span>Description</span>
                  <input
                    className="input"
                    value={attachmentDescription}
                    onChange={(event) => setAttachmentDescription(event.target.value)}
                  />
                </label>
              </div>
              <div className="button-row">
                <button className="button secondary" type="button" onClick={addAttachment} disabled={!selectedArtifactId}>
                  Add Attachment
                </button>
              </div>
              {attachments.length ? (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>Artifact</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {attachments.map((attachment) => (
                      <tr key={attachment.artifact_id}>
                        <td>{attachment.attachment_type}</td>
                        <td>
                          {attachment.label}
                          {attachment.description ? <span className="muted"> · {attachment.description}</span> : null}
                        </td>
                        <td>
                          <button
                            className="button secondary compact-button"
                            type="button"
                            onClick={() =>
                              setAttachments((current) =>
                                current.filter((candidate) => candidate.artifact_id !== attachment.artifact_id)
                              )
                            }
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="empty">No attachments selected.</div>
              )}
            </div>
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
              {result.attachments.length ? (
                <div>
                  <h3>Attached Context</h3>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th>Description</th>
                        <th>Artifact</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.attachments.map((attachment) => (
                        <tr key={attachment.id}>
                          <td>{attachment.attachment_type}</td>
                          <td>{attachment.description || "No description"}</td>
                          <td>{attachment.artifact_id.slice(0, 8)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
              <label className="field">
                <span>Feedback notes</span>
                <textarea
                  className="textarea"
                  style={{ minHeight: 72 }}
                  value={feedbackNote}
                  onChange={(event) => setFeedbackNote(event.target.value)}
                />
              </label>
              <div className="button-row">
                <button className="button secondary" type="button" onClick={() => submitFeedback("helpful")}>
                  Helpful
                </button>
                <button className="button secondary" type="button" onClick={() => submitFeedback("incorrect")}>
                  Incorrect
                </button>
                <button className="button secondary" type="button" onClick={() => submitFeedback("missing_source")}>
                  Missing Source
                </button>
                <button className="button secondary" type="button" onClick={() => submitFeedback("needs_review")}>
                  Needs Review
                </button>
              </div>
              {feedbackMessage ? <p className="status">{feedbackMessage}</p> : null}
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
