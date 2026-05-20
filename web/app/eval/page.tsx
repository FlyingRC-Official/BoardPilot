"use client";

import { FormEvent, useEffect, useState } from "react";
import { MetricsPanel } from "@/components/eval/MetricsPanel";
import { compareEvalRuns, createEvalCase, listEvalCases, listProducts, runEval, seedEvalCases, updateEvalCase } from "@/lib/api-client";
import type { EvalCase, EvalRunComparison, EvalRunResponse, Product } from "@/lib/types";

function splitList(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

export default function EvalPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [cases, setCases] = useState<EvalCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [productId, setProductId] = useState("");
  const [question, setQuestion] = useState("How should USB power be used?");
  const [expectedSources, setExpectedSources] = useState("");
  const [expectedChunks, setExpectedChunks] = useState("");
  const [answerPoints, setAnswerPoints] = useState("USB is for configuration");
  const [tags, setTags] = useState("power, usb");
  const [difficulty, setDifficulty] = useState("normal");
  const [active, setActive] = useState(true);
  const [run, setRun] = useState<EvalRunResponse | null>(null);
  const [previousRunId, setPreviousRunId] = useState("");
  const [comparison, setComparison] = useState<EvalRunComparison | null>(null);
  const [message, setMessage] = useState("");

  async function refreshCases() {
    setCases(await listEvalCases().catch(() => []));
  }

  useEffect(() => {
    listProducts().then(setProducts).catch(() => setProducts([]));
    refreshCases();
  }, []);

  function editCase(evalCase: EvalCase) {
    setSelectedCaseId(evalCase.id);
    setProductId(evalCase.product_id || "");
    setQuestion(evalCase.question_text);
    setExpectedSources(evalCase.expected_source_ids_json.join(", "));
    setExpectedChunks(evalCase.expected_chunk_ids_json.join(", "));
    setAnswerPoints(evalCase.expected_answer_points_json.join(", "));
    setTags(evalCase.tags_json.join(", "));
    setDifficulty(evalCase.difficulty);
    setActive(evalCase.active);
    setMessage("Editing EvalCase.");
  }

  function clearCaseForm() {
    setSelectedCaseId("");
    setProductId("");
    setQuestion("How should USB power be used?");
    setExpectedSources("");
    setExpectedChunks("");
    setAnswerPoints("USB is for configuration");
    setTags("power, usb");
    setDifficulty("normal");
    setActive(true);
    setMessage("");
  }

  async function submitCase(event: FormEvent) {
    event.preventDefault();
    const payload = {
      product_id: productId || undefined,
      question_text: question,
      expected_source_ids_json: splitList(expectedSources),
      expected_chunk_ids_json: splitList(expectedChunks),
      expected_answer_points_json: splitList(answerPoints),
      tags_json: splitList(tags),
      difficulty,
      active
    };
    if (selectedCaseId) {
      await updateEvalCase(selectedCaseId, payload);
    } else {
      await createEvalCase(payload);
    }
    await refreshCases();
    setMessage(selectedCaseId ? "EvalCase updated." : "EvalCase created.");
  }

  async function submitRun() {
    const response = await runEval("Workbench eval");
    if (run?.eval_run.id) {
      setPreviousRunId(run.eval_run.id);
      setComparison(await compareEvalRuns(run.eval_run.id, response.eval_run.id));
    }
    setRun(response);
    setMessage("EvalRun completed.");
  }

  async function submitSeed() {
    const response = await seedEvalCases();
    await refreshCases();
    setMessage(`${response.case_count} seed EvalCases are ready.`);
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Eval</h1>
          <p>Measure whether expected chunks enter recall and reranked Top 5, then inspect answer grounding metrics.</p>
        </div>
        <div className="button-row">
          <button className="button secondary" onClick={submitSeed}>
            Seed 20 Cases
          </button>
          <button className="button" onClick={submitRun}>
            Run Eval
          </button>
        </div>
      </header>
      <section className="grid two">
        <form className="panel form" onSubmit={submitCase}>
          <h2>{selectedCaseId ? "Edit EvalCase" : "Create EvalCase"}</h2>
          <label className="field">
            <span>Product</span>
            <select className="select" value={productId} onChange={(event) => setProductId(event.target.value)}>
              <option value="">No product filter</option>
              {products.map((product) => (
                <option value={product.id} key={product.id}>{product.name}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Question</span>
            <textarea className="textarea" value={question} onChange={(event) => setQuestion(event.target.value)} />
          </label>
          <label className="field">
            <span>Expected source IDs</span>
            <input className="input" value={expectedSources} onChange={(event) => setExpectedSources(event.target.value)} />
          </label>
          <label className="field">
            <span>Expected chunk IDs</span>
            <input className="input" value={expectedChunks} onChange={(event) => setExpectedChunks(event.target.value)} />
          </label>
          <label className="field">
            <span>Expected answer points</span>
            <input className="input" value={answerPoints} onChange={(event) => setAnswerPoints(event.target.value)} />
          </label>
          <label className="field">
            <span>Tags</span>
            <input className="input" value={tags} onChange={(event) => setTags(event.target.value)} />
          </label>
          <label className="field">
            <span>Difficulty</span>
            <select className="select" value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
              <option value="normal">Normal</option>
              <option value="hard">Hard</option>
              <option value="review">Review</option>
            </select>
          </label>
          <label className="checkline">
            <input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} />
            <span>Active</span>
          </label>
          <div className="button-row">
            <button className="button">{selectedCaseId ? "Update EvalCase" : "Save EvalCase"}</button>
            {selectedCaseId ? (
              <button className="button secondary" type="button" onClick={clearCaseForm}>
                New Case
              </button>
            ) : null}
          </div>
          {message ? <p className="status">{message}</p> : null}
        </form>
        <div className="panel">
          <h2>Latest Run</h2>
          {run ? (
            <div className="grid">
              <p>
                <strong>{run.eval_run.name}</strong> <span className="muted">{run.results.length} results</span>
              </p>
              <MetricsPanel metrics={run.eval_run.summary_metrics_json} />
            </div>
          ) : (
            <div className="empty">Create cases and run an EvalRun to see aggregate metrics.</div>
          )}
        </div>
      </section>
      <section className="panel" style={{ marginTop: 16 }}>
        <h2>EvalCases</h2>
        {cases.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Question</th>
                <th>Expected</th>
                <th>Difficulty</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {cases.slice(-12).reverse().map((evalCase) => (
                <tr key={evalCase.id}>
                  <td>{evalCase.question_text}</td>
                  <td>
                    {evalCase.expected_chunk_ids_json.length} chunks · {evalCase.expected_answer_points_json.length} points
                  </td>
                  <td>{evalCase.difficulty}</td>
                  <td>{evalCase.active ? "active" : "inactive"}</td>
                  <td>
                    <button className="button secondary" type="button" onClick={() => editCase(evalCase)}>
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty">No EvalCases in this API session.</div>
        )}
      </section>
      <section className="panel" style={{ marginTop: 16 }}>
        <h2>Compare Runs</h2>
        {comparison ? (
          <table className="table">
            <thead>
              <tr>
                <th>Metric</th>
                <th>Delta</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(comparison.deltas).map(([key, value]) => (
                <tr key={key}>
                  <td>{key.replaceAll("_", " ")}</td>
                  <td>{value.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty">
            Run Eval twice in this session to compare the latest run against {previousRunId ? "the previous run" : "a previous run"}.
          </div>
        )}
      </section>
    </>
  );
}
