"use client";

import { FormEvent, useEffect, useState } from "react";
import { SourceViewer } from "@/components/source-viewer/SourceViewer";
import {
  addSourceVersion,
  addWebpageSnapshot,
  createProduct,
  createProductAlias,
  createSource,
  disableSourceVersion,
  listImageAssets,
  listImageOcrResults,
  listLogSources,
  listProductAliases,
  listProducts,
  listSourceVersionArtifacts,
  listSourceVersionChunks,
  listSourceVersions,
  listSources,
  listTickets,
  queueIngestionJob,
  runIngestionJob,
  uploadImageAsset,
  uploadSourceVersion
} from "@/lib/api-client";
import type {
  Chunk,
  ImageAsset,
  LogSource,
  OcrResult,
  Product,
  ProductAlias,
  Source,
  SourceArtifact,
  SourceVersion,
  Ticket
} from "@/lib/types";

function chunkMetadataRows(chunk: Chunk) {
  return [
    ["Status", chunk.enabled ? "enabled" : "disabled"],
    ["Section", chunk.section_name || chunk.title_path || "-"],
    ["Chars", `${chunk.char_start}-${chunk.char_end}`],
    ["Page", chunk.page_number != null ? String(chunk.page_number) : "-"],
    ["Hash", chunk.content_hash.slice(0, 12)],
    ...Object.entries(chunk.metadata_json || {}).map(([key, value]) => [key, typeof value === "string" ? value : JSON.stringify(value) ?? String(value)])
  ];
}

export default function SourcesPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [aliases, setAliases] = useState<ProductAlias[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);
  const [versions, setVersions] = useState<SourceVersion[]>([]);
  const [artifacts, setArtifacts] = useState<SourceArtifact[]>([]);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [logSources, setLogSources] = useState<LogSource[]>([]);
  const [imageAssets, setImageAssets] = useState<ImageAsset[]>([]);
  const [ocrResultsByImage, setOcrResultsByImage] = useState<Record<string, OcrResult[]>>({});
  const [productName, setProductName] = useState("FlyingRC F4");
  const [productSlug, setProductSlug] = useState("flyingrc-f4");
  const [alias, setAlias] = useState("F4 FC");
  const [sourceTitle, setSourceTitle] = useState("FlyingRC F4 Manual");
  const [sourceType, setSourceType] = useState("markdown");
  const [sourceId, setSourceId] = useState("");
  const [content, setContent] = useState("USB power is for configuration. Do not power servos from the USB connector.");
  const [webpageUrl, setWebpageUrl] = useState("https://example.com/flyingrc-f4");
  const [webpageHtml, setWebpageHtml] = useState("<h1>FlyingRC F4</h1><p>USB power is for configuration only.</p>");
  const [file, setFile] = useState<File | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imageType, setImageType] = useState("wiring_photo");
  const [imageDescription, setImageDescription] = useState("Photo shows USB connector is for configuration only.");
  const [disableReason, setDisableReason] = useState("bad import");
  const [message, setMessage] = useState("");

  async function refresh() {
    const nextProducts = await listProducts().catch(() => []);
    setProducts(nextProducts);
    if (nextProducts[0]) {
      setAliases(await listProductAliases(nextProducts[0].id).catch(() => []));
    }
    setSources(await listSources().catch(() => []));
    setTickets(await listTickets().catch(() => []));
    setLogSources(await listLogSources().catch(() => []));
    const nextImageAssets = await listImageAssets().catch(() => []);
    setImageAssets(nextImageAssets);
    const nextOcrEntries = await Promise.all(
      nextImageAssets.map(async (image) => [image.id, await listImageOcrResults(image.id).catch(() => [])] as const)
    );
    setOcrResultsByImage(Object.fromEntries(nextOcrEntries));
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

  async function submitWebpage(event: FormEvent) {
    event.preventDefault();
    const targetSource =
      sources.find((source) => source.id === sourceId && source.source_type === "webpage") ||
      sources.find((source) => source.source_type === "webpage");
    if (!targetSource || !webpageUrl.trim() || !webpageHtml.trim()) {
      setMessage("Choose a webpage source, URL, and HTML snapshot first.");
      return;
    }
    await addWebpageSnapshot(targetSource.id, {
      url: webpageUrl,
      html: webpageHtml,
      version_label: "webpage-snapshot"
    });
    await refresh();
    setMessage("Webpage snapshot stored and ingested into chunks.");
  }

  async function submitImage(event: FormEvent) {
    event.preventDefault();
    const product = products[0];
    if (!product || !imageFile) {
      setMessage("Create a product and choose an image first.");
      return;
    }
    await uploadImageAsset({
      product_id: product.id,
      image_type: imageType,
      manual_description: imageDescription,
      file: imageFile
    });
    await refresh();
    setMessage("Image asset uploaded and manual description ingested into chunks.");
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
              <option value="webpage">Webpage snapshot</option>
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
      <section className="grid three" style={{ marginTop: 16 }}>
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
        <form className="panel form" onSubmit={submitWebpage}>
          <h2>Webpage Snapshot</h2>
          <label className="field">
            <span>URL</span>
            <input className="input" value={webpageUrl} onChange={(event) => setWebpageUrl(event.target.value)} />
          </label>
          <label className="field">
            <span>HTML snapshot</span>
            <textarea className="textarea" value={webpageHtml} onChange={(event) => setWebpageHtml(event.target.value)} />
          </label>
          <button className="button secondary">Import Snapshot</button>
        </form>
      </section>
      <section className="grid two" style={{ marginTop: 16 }}>
        <form className="panel form" onSubmit={submitImage}>
          <h2>Image Asset</h2>
          <label className="field">
            <span>File</span>
            <input className="input" type="file" accept="image/*" onChange={(event) => setImageFile(event.target.files?.[0] || null)} />
          </label>
          <label className="field">
            <span>Type</span>
            <input className="input" value={imageType} onChange={(event) => setImageType(event.target.value)} />
          </label>
          <label className="field">
            <span>Manual description</span>
            <textarea className="textarea" value={imageDescription} onChange={(event) => setImageDescription(event.target.value)} />
          </label>
          <button className="button secondary">Upload Image</button>
        </form>
      </section>
      <section className="panel" style={{ marginTop: 16 }}>
        <h2>Support Imports</h2>
        <div className="grid three" style={{ marginTop: 12 }}>
          <div>
            <h3>Tickets</h3>
            {tickets.length ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>External</th>
                    <th>Status</th>
                    <th>Title</th>
                  </tr>
                </thead>
                <tbody>
                  {tickets.slice(0, 5).map((ticket) => (
                    <tr key={ticket.id}>
                      <td>{ticket.external_id || ticket.id.slice(0, 8)}</td>
                      <td>{ticket.status}</td>
                      <td>{ticket.title || ticket.body.slice(0, 48)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty">No imported tickets.</div>
            )}
          </div>
          <div>
            <h3>Logs</h3>
            {logSources.length ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Content</th>
                  </tr>
                </thead>
                <tbody>
                  {logSources.slice(0, 5).map((logSource) => (
                    <tr key={logSource.id}>
                      <td>{logSource.log_type || "log"}</td>
                      <td>{logSource.content.slice(0, 64)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty">No imported logs.</div>
            )}
          </div>
          <div>
            <h3>Images</h3>
            {imageAssets.length ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>OCR</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {imageAssets.slice(0, 5).map((image) => {
                    const imageOcrResults = ocrResultsByImage[image.id] || [];
                    const latestOcr = imageOcrResults[imageOcrResults.length - 1];
                    return (
                      <tr key={image.id}>
                        <td>{image.image_type || "image"}</td>
                        <td>{latestOcr?.ocr_text?.slice(0, 48) || image.manual_description.slice(0, 48) || "-"}</td>
                        <td>{latestOcr?.status || "manual"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <div className="empty">No image assets.</div>
            )}
          </div>
        </div>
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
                      <th>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {versions.map((version) => (
                      <tr key={version.id}>
                        <td>{version.version_label}</td>
                        <td>{version.status}</td>
                        <td>{version.parser_version}</td>
                        <td>{version.error_message || "-"}</td>
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
                    <dl className="metadata-grid">
                      {chunkMetadataRows(chunk).map(([label, value]) => (
                        <div key={`${chunk.id}-${label}`}>
                          <dt>{label}</dt>
                          <dd>{value}</dd>
                        </div>
                      ))}
                    </dl>
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
