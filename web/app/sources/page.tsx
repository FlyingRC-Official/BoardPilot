"use client";

import { FormEvent, useEffect, useState } from "react";
import { SourceViewer } from "@/components/source-viewer/SourceViewer";
import { addSourceVersion, createProduct, createSource, listProducts, listSources, uploadSourceVersion } from "@/lib/api-client";
import type { Product, Source } from "@/lib/types";

export default function SourcesPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [productName, setProductName] = useState("FlyingRC F4");
  const [productSlug, setProductSlug] = useState("flyingrc-f4");
  const [sourceTitle, setSourceTitle] = useState("FlyingRC F4 Manual");
  const [sourceType, setSourceType] = useState("markdown");
  const [sourceId, setSourceId] = useState("");
  const [content, setContent] = useState("USB power is for configuration. Do not power servos from the USB connector.");
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");

  async function refresh() {
    setProducts(await listProducts().catch(() => []));
    setSources(await listSources().catch(() => []));
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
        <form className="panel form" onSubmit={submitVersion}>
          <h2>Version</h2>
          <label className="field">
            <span>Content</span>
            <textarea className="textarea" value={content} onChange={(event) => setContent(event.target.value)} />
          </label>
          <button className="button">Ingest Version</button>
        </form>
      </section>
      <section className="panel" style={{ marginTop: 16 }}>
        <form className="form" onSubmit={submitUpload}>
          <h2>Upload Artifact</h2>
          <label className="field">
            <span>File</span>
            <input className="input" type="file" onChange={(event) => setFile(event.target.files?.[0] || null)} />
          </label>
          <button className="button secondary">Upload and Ingest</button>
        </form>
      </section>
      {message ? <p className="status" style={{ marginTop: 16 }}>{message}</p> : null}
      <section className="panel" style={{ marginTop: 16 }}>
        <h2>Current Sources</h2>
        <SourceViewer sources={sources} />
      </section>
    </>
  );
}
