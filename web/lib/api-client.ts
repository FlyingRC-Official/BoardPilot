import type { AskResponse, EvalRunResponse, Product, ReviewItem, Source } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    }
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function listProducts() {
  return request<Product[]>("/products");
}

export function createProduct(payload: Pick<Product, "name" | "slug" | "description">) {
  return request<Product>("/products", { method: "POST", body: JSON.stringify(payload) });
}

export function listSources() {
  return request<Source[]>("/sources");
}

export function createSource(payload: {
  product_id: string;
  title: string;
  source_type: string;
  trust_level: string;
}) {
  return request<Source>("/sources", { method: "POST", body: JSON.stringify(payload) });
}

export function addSourceVersion(sourceId: string, payload: { version_label: string; content: string }) {
  return request(`/sources/${sourceId}/versions`, { method: "POST", body: JSON.stringify(payload) });
}

export async function uploadSourceVersion(sourceId: string, file: File, versionLabel = "uploaded") {
  const body = new FormData();
  body.append("version_label", versionLabel);
  body.append("file", file);
  const response = await fetch(`${API_BASE}/sources/${sourceId}/versions/upload`, {
    method: "POST",
    body
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

export function askQuestion(payload: { question: string; product_id?: string }) {
  return request<AskResponse>("/ask", { method: "POST", body: JSON.stringify(payload) });
}

export function createEvalCase(payload: { question_text: string; product_id?: string }) {
  return request("/eval-cases", { method: "POST", body: JSON.stringify(payload) });
}

export function seedEvalCases() {
  return request<{ case_count: number }>("/eval-cases/seed", { method: "POST" });
}

export function runEval(name: string) {
  return request<EvalRunResponse>("/eval-runs", { method: "POST", body: JSON.stringify({ name }) });
}

export function listReviewItems() {
  return request<ReviewItem[]>("/review-items");
}

export function approveReviewItem(id: string, failure_category = "human_policy_required") {
  return request<ReviewItem>(`/review-items/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ failure_category })
  });
}

export function updateReviewItem(id: string, payload: Partial<Pick<ReviewItem, "reviewer_notes">> & { edited_answer_text?: string }) {
  return request<ReviewItem>(`/review-items/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function convertReviewItemToFaq(id: string) {
  return request(`/review-items/${id}/to-faq`, { method: "POST" });
}
