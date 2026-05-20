"use client";

import { FormEvent, useState } from "react";
import { MetricsPanel } from "@/components/eval/MetricsPanel";
import { createEvalCase, runEval } from "@/lib/api-client";
import type { EvalRunResponse } from "@/lib/types";

export default function EvalPage() {
  const [question, setQuestion] = useState("How should USB power be used?");
  const [run, setRun] = useState<EvalRunResponse | null>(null);
  const [message, setMessage] = useState("");

  async function submitCase(event: FormEvent) {
    event.preventDefault();
    await createEvalCase({ question_text: question });
    setMessage("EvalCase created.");
  }

  async function submitRun() {
    const response = await runEval("Workbench eval");
    setRun(response);
    setMessage("EvalRun completed.");
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Eval</h1>
          <p>Measure whether expected chunks enter recall and reranked Top 5, then inspect answer grounding metrics.</p>
        </div>
        <button className="button" onClick={submitRun}>
          Run Eval
        </button>
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
    </>
  );
}

