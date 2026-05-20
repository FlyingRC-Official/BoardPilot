"use client";

import { FormEvent, useEffect, useState } from "react";
import { SourceViewer } from "@/components/source-viewer/SourceViewer";
import {
  addSourceVersion,
  createProduct,
  createProductAlias,
  createSource,
  disableSourceVersion,
  listProductAliases,
  listProducts,
  listSourceVersionArtifacts,
  listSourceVersionChunks,
  listSourceVersions,
  listSources,
  queueIngestionJob,
  runIngestionJob,
  uploadSourceVersion
} from "@/lib/api-client";
import type { Chunk, Product, ProductAlias, Source, SourceArtifact, SourceVersion } from "@/lib/types";

export default function SourcesPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [aliases, setAliases] = useState<ProductAlias[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);
  const [versions, setVersions] = useState<SourceVersion[]>([]);
  const [artifacts, setArtifacts] = useState<SourceArtifact[]>([]);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [productName, setProductName] = useState("FlyingRC F4");
  const [productSlug, setProductSlug] = useState("flyingrc-f4");
  const [alias, setAlias] = useState("F4 FC");
  const [sourceTitle, setSourceTitle] = useState("FlyingRC F4 Manual");
  const [sourceType, setSourceType] = useState("markdown");
  const [sourceId, setSourceId] = useState("");
  const [content, setContent] = useState("USB power is for configuration. Do not power servos from the USB connector.");
  const [file, setFile] = useState<File | null>(null);
  const [disableReason, setDisableReason] = useState("bad import");
  const [message, setMessage] = useState("");

  async function refresh() {
    const nextProducts = await listProducts().catch(() => []);
    setProducts(nextProducts);
    if (nextProducts[0]) {
      setAliases(await listProductAliases(nextProducts[0].id).catch(() => []));
    }
    setSources(await listSources().catch(() => []));
  }

  async function inspectSource(source: Source) {
    setSelectedSource(source);
    const nextVersions = await listSourceVersions(source.id).catch(() => []);
    setVersions(nextVersions);
    const latestVersion = nextVersions[nextVersions.length - 1];
    if (!latestVersion) {
      setArtifacts([]);
      setChunks([]);
      setMessage("Source has no versions yet.");
      return;
    }
    setArtifacts(await listSourceVersionArtifacts(latestVersion.id).catch(() => []));
    setChunks(await listSourceVersionChunks(latestVersion.id).catch(() => []));
    setMessage(`Inspecting ${source.title}.`);
  }

  async function reingestLatestVersion() {
    if (!selectedSource || !versions.length) {
      setMessage("Select a source with a version first.");
      return;
    }
    const latestVersion = versions[versions.length - 1];
    const result = await runIngestionJob(latestVersion.id);
    setChunks(result.chunks);
    setVersions(await listSourceVersions(selectedSource.id).catch(() => versions));
    setMessage(`Reingestion ${result.job.status}: ${result.job.chunk_count} new chunks.`);
  }

  async function queueLatestVersion() {
    if (!selectedSource || !versions.length) {
      setMessage("Select a source with a version first.");
      return;
    }
    const latestVersion = versions[versions.length - 1];
    const result = await queueIngestionJob(latestVersion.id);
    setMessage(`Queued ingestion job ${result.job.id.slice(0, 8)} on ${result.queue}.`);
  }

  async function disableLatestVersion() {
    if (!selectedSource || !versions.length) {
      setMessage("Select a source with a version first.");
      return;
    }
    const latestVersion = versions[versions.length - 1];
    const result = await disableSourceVersion(latestVersion.id, disableReason);
    setVersions(await listSourceVersions(selectedSource.id).catch(() => versions));
    setChunks(await listSourceVersionChunks(latestVersion.id).catch(() => chunks));
    setMessage(`Disabled ${result.disabled_chunk_count} chunks from ${result.version.version_label}.`);
  }

  useEffect(() => {
    refresh();
  }, []);

  async function submitProduct(event: FormEvent) {
    event.preventDefault();
    await createProduct({ name: productName, slug: productSlug, description: "Hardware support product" });
    await refresh();
    setMessage("Product created.");
  }

  async function submitSource(event: FormEvent) {
    event.preventDefault();
    const product = products[0];
    if (!product) {
      setMessage("Create a product first.");
      return;
    }
    const source = await createSource({
      product_id: product.id,
      title: sourceTitle,
      source_type: sourceType,
      trust_level: "official"
    });
    setSourceId(source.id);
    await refresh();
    setMessage("Source created.");
  }

  async function submitAlias(event: FormEvent) {
    event.preventDefault();
    const product = products[0];
    if (!product) {
      setMessage("Create a product first.");
      return;
    }
    await createProductAlias(product.id, { alias, alias_type: "user_facing", confidence: 0.9 });
    await refresh();
    setMessage("Product alias created.");
  }

  async function submitVersion(event: FormEvent) {
    event.preventDefault();
    const targetSourceId = sourceId || sources[0]?.id;
    if (!targetSourceId) {
      setMessage("Create a source first.");
      return;
    }
    await addSourceVersion(targetSourceId, { version_label: "v1", content });
    await refresh();
    setMessage("Source version ingested into chunks.");
  }

  async function submitUpload(event: FormEvent) {
    event.preventDefault();
    const targetSourceId = sourceId || sources[0]?.id;
    if (!targetSourceId || !file) {
      setMessage("Choose a source and file first.");
      return;
    }
    await uploadSourceVersion(targetSourceId, file, "uploaded");
    await refresh();
    setMessage("Uploaded artifact stored and ingested into chunks.");
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Sources</h1>
          <p>Create products, register source material, and ingest text into deduplicated chunks for retrieval.</p>
        </div>
      </header>
      <section className="grid three">
        <form className="panel form" onSubmit={submitProduct}>
          <h2>Product</h2>
          <label className="field">
            <span>Name</span>
            <input className="input" value={productName} onChange={(event) => setProductName(event.target.value)} />
          </label>
          <label className="field">
            <span>Slug</span>
            <input className="input" value={productSlug} onChange={(event) => setProductSlug(event.target.value)} />
          </label>
          <button className="button">Create Product</button>
        </form>
        <form className="panel form" onSubmit={submitSource}>
          <h2>Source</h2>
          <label className="field">
            <span>Title</span>
            <input className="input" value={sourceTitle} onChange={(event) => setSourceTitle(event.target.value)} />
          </label>
          <label className="field">
            <span>Type</span>
            <select className="select" value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
              <option value="markdown">Markdown</option>
              <option value="csv_faq">CSV/FAQ</option>
              <option value="text_log">Text log</option>
              <option value="pdf">PDF text</option>
              <option value="image">Image description</option>
            </select>
          </label>
          <button className="button">Create Source</button>
        </form>
        <form className="panel form" onSubmit={submitAlias}>
          <h2>Alias</h2>
          <label className="field">
            <span>Alias</span>
            <input className="input" value={alias} onChange={(event) => setAlias(event.target.value)} />
          </label>
          <button className="button">Create Alias</button>
          <p className="muted">{aliases.length} aliases on the first product.</p>
        </form>
      </section>
      <section className="grid two" style={{ marginTop: 16 }}>
        <form className="panel form" onSubmit={submitVersion}>
          <h2>Version</h2>
          <label className="field">
            <span>Content</span>
            <textarea className="textarea" value={content} onChange={(event) => setContent(event.target.value)} />
          </label>
          <button className="button">Ingest Version</button>
        </form>
        <section className="panel">
        <form className="form" onSubmit={submitUpload}>
          <h2>Upload Artifact</h2>
          <label className="field">
            <span>File</span>
            <input className="input" type="file" onChange={(event) => setFile(event.target.files?.[0] || null)} />
          </label>
          <button className="button secondary">Upload and Ingest</button>
        </form>
        </section>
      </section>
      {message ? <p className="status" style={{ marginTop: 16 }}>{message}</p> : null}
      <section className="panel" style={{ marginTop: 16 }}>
        <h2>Current Sources</h2>
        <SourceViewer sources={sources} onInspect={inspectSource} />
      </section>
      {selectedSource ? (
        <section className="panel" style={{ marginTop: 16 }}>
          <h2>Source Detail</h2>
          <p className="muted">
            {selectedSource.title} · {versions.length} versions · {chunks.length} chunks in latest version
          </p>
          <div className="button-row" style={{ marginTop: 12 }}>
            <button className="button secondary" type="button" onClick={reingestLatestVersion}>
              Reingest Latest
            </button>
            <button className="button secondary" type="button" onClick={queueLatestVersion}>
              Queue Latest
            </button>
            <button className="button secondary" type="button" onClick={disableLatestVersion}>
              Disable Latest
            </button>
          </div>
          <label className="field" style={{ marginTop: 12 }}>
            <span>Disable reason</span>
            <input className="input" value={disableReason} onChange={(event) => setDisableReason(event.target.value)} />
          </label>
          <div className="grid two" style={{ marginTop: 12 }}>
            <div>
              <h3>Version History</h3>
              {versions.length ? (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Label</th>
                      <th>Status</th>
                      <th>Parser</th>
                    </tr>
                  </thead>
                  <tbody>
                    {versions.map((version) => (
                      <tr key={version.id}>
                        <td>{version.version_label}</td>
                        <td>{version.status}</td>
                        <td>{version.parser_version}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="empty">No versions for this source.</div>
              )}
            </div>
            <div>
              <h3>Artifacts</h3>
              {artifacts.length ? (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>MIME</th>
                      <th>Bytes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {artifacts.map((artifact) => (
                      <tr key={artifact.id}>
                        <td>{artifact.artifact_type}</td>
                        <td>{artifact.mime_type}</td>
                        <td>{artifact.size_bytes}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="empty">No artifacts on the latest version.</div>
              )}
            </div>
          </div>
          <div style={{ marginTop: 16 }}>
            <h3>Chunk Preview</h3>
            {chunks.length ? (
              <div className="evidence-list">
                {chunks.slice(0, 5).map((chunk) => (
                  <article className="evidence-item" key={chunk.id}>
                    <strong>Chunk {chunk.chunk_index}</strong>
                    <span className="muted"> {chunk.token_count} tokens</span>
                    <blockquote>{chunk.content.slice(0, 320)}</blockquote>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty">No chunks on the latest version.</div>
            )}
          </div>
        </section>
      ) : null}
    </>
  );
}
