"use client";

import { FormEvent, useEffect, useState } from "react";
import { createProviderConfig, listProviderConfigs } from "@/lib/api-client";
import type { ProviderConfig } from "@/lib/types";

export default function SettingsPage() {
  const [configs, setConfigs] = useState<ProviderConfig[]>([]);
  const [providerType, setProviderType] = useState("llm");
  const [providerName, setProviderName] = useState("fake");
  const [modelName, setModelName] = useState("fake-citation-llm");
  const [configJson, setConfigJson] = useState("{}");
  const [enabled, setEnabled] = useState(true);
  const [message, setMessage] = useState("");

  async function refresh() {
    setConfigs(await listProviderConfigs().catch(() => []));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function submitProvider(event: FormEvent) {
    event.preventDefault();
    let parsedConfig: Record<string, unknown>;
    try {
      parsedConfig = configJson.trim() ? JSON.parse(configJson) : {};
    } catch {
      setMessage("Config JSON is invalid.");
      return;
    }
    await createProviderConfig({
      provider_type: providerType,
      provider_name: providerName,
      model_name: modelName,
      config_json: parsedConfig,
      enabled
    });
    await refresh();
    setMessage("Provider config saved.");
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Settings</h1>
          <p>Configure model providers used by retrieval, answer generation, reranking, and OCR.</p>
        </div>
      </header>
      <section className="grid two">
        <form className="panel form" onSubmit={submitProvider}>
          <h2>Provider Config</h2>
          <label className="field">
            <span>Type</span>
            <select className="select" value={providerType} onChange={(event) => setProviderType(event.target.value)}>
              <option value="llm">LLM</option>
              <option value="embedding">Embedding</option>
              <option value="reranker">Reranker</option>
              <option value="ocr">OCR</option>
            </select>
          </label>
          <label className="field">
            <span>Provider</span>
            <input className="input" value={providerName} onChange={(event) => setProviderName(event.target.value)} />
          </label>
          <label className="field">
            <span>Model</span>
            <input className="input" value={modelName} onChange={(event) => setModelName(event.target.value)} />
          </label>
          <label className="field">
            <span>Config JSON</span>
            <textarea className="textarea" value={configJson} onChange={(event) => setConfigJson(event.target.value)} />
          </label>
          <label className="checkline">
            <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />
            <span>Enabled</span>
          </label>
          <button className="button">Save Provider</button>
          {message ? <p className="status">{message}</p> : null}
        </form>
        <section className="panel">
          <h2>Saved Providers</h2>
          {configs.length ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Provider</th>
                  <th>Model</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {configs.map((config) => (
                  <tr key={config.id}>
                    <td>{config.provider_type}</td>
                    <td>{config.provider_name}</td>
                    <td>{config.model_name}</td>
                    <td>{config.enabled ? "enabled" : "disabled"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty">No provider configs saved in this API session.</div>
          )}
        </section>
      </section>
    </>
  );
}
