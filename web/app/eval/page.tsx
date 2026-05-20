"use client";

import { FormEvent, useState } from "react";
import { MetricsPanel } from "@/components/eval/MetricsPanel";
import { compareEvalRuns, createEvalCase, runEval, seedEvalCases } from "@/lib/api-client";
import type { EvalRunComparison, EvalRunResponse } from "@/lib/types";

export default function EvalPage() {
  const [question, setQuestion] = useState("How should USB power be used?");
  const [run, setRun] = useState<EvalRunResponse | null>(null);
  const [previousRunId, setPreviousRunId] = useState("");
  const [comparison, setComparison] = useState<EvalRunComparison | null>(null);
  const [message, setMessage] = useState("");

  async function submitCase(event: FormEvent) {
    event.preventDefault();
    await createEvalCase({ question_text: question });
    setMessage("EvalCase created.");
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
          <h2>Create EvalCase</h2>
          <label className="field">
            <span>Question</span>
            <textarea className="textarea" value={question} onChange={(event) => setQuestion(event.target.value)} />
          </label>
          <button className="button">Save EvalCase</button>
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
