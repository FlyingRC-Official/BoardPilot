import type {
  AskResponse,
  AuditLog,
  EvalCase,
  EvalRunComparison,
  EvalRunResponse,
  EvalResult,
  Evidence,
  Product,
  ProductAlias,
  ProviderConfig,
  Answer,
  IngestionJob,
  Question,
  RetrievalCandidate,
  ReviewItem,
  ReviewItemDetail,
  Source,
  SourceArtifact,
  SourceVersion,
  Chunk
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_BOARDPILOT_API_KEY || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(API_KEY ? { "X-BoardPilot-API-Key": API_KEY } : {}),
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

export function createProductAlias(productId: string, payload: { alias: string; alias_type: string; confidence: number }) {
  return request<ProductAlias>(`/products/${productId}/aliases`, { method: "POST", body: JSON.stringify(payload) });
}

export function listProductAliases(productId: string) {
  return request<ProductAlias[]>(`/products/${productId}/aliases`);
}

export function listProviderConfigs() {
  return request<ProviderConfig[]>("/provider-configs");
}

export function createProviderConfig(payload: {
  provider_type: string;
  provider_name: string;
  model_name: string;
  config_json: Record<string, unknown>;
  enabled: boolean;
}) {
  return request<ProviderConfig>("/provider-configs", { method: "POST", body: JSON.stringify(payload) });
}

export function updateProviderConfig(
  id: string,
  payload: Partial<Pick<ProviderConfig, "provider_type" | "provider_name" | "model_name" | "config_json" | "enabled">>
) {
  return request<ProviderConfig>(`/provider-configs/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteProviderConfig(id: string) {
  return request<{ status: string }>(`/provider-configs/${id}`, { method: "DELETE" });
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

export function addWebpageSnapshot(sourceId: string, payload: { url: string; html: string; version_label?: string }) {
  return request(`/sources/${sourceId}/versions/webpage`, { method: "POST", body: JSON.stringify(payload) });
}

export function listSourceVersions(sourceId: string) {
  return request<SourceVersion[]>(`/sources/${sourceId}/versions`);
}

export function listSourceVersionArtifacts(versionId: string) {
  return request<SourceArtifact[]>(`/source-versions/${versionId}/artifacts`);
}

export function listSourceVersionChunks(versionId: string) {
  return request<Chunk[]>(`/source-versions/${versionId}/chunks`);
}

export function runIngestionJob(sourceVersionId: string) {
  return request<{ job: IngestionJob; chunks: Chunk[] }>("/ingestion/jobs", {
    method: "POST",
    body: JSON.stringify({ source_version_id: sourceVersionId })
  });
}

export function queueIngestionJob(sourceVersionId: string) {
  return request<{ job: IngestionJob; queue: string }>("/ingestion/jobs/enqueue", {
    method: "POST",
    body: JSON.stringify({ source_version_id: sourceVersionId })
  });
}

export function disableSourceVersion(versionId: string, reason: string) {
  return request<{ version: SourceVersion; disabled_chunk_count: number }>(`/source-versions/${versionId}/disable`, {
    method: "POST",
    body: JSON.stringify({ reason })
  });
}

export async function uploadSourceVersion(sourceId: string, file: File, versionLabel = "uploaded") {
  const body = new FormData();
  body.append("version_label", versionLabel);
  body.append("file", file);
  const response = await fetch(`${API_BASE}/sources/${sourceId}/versions/upload`, {
    method: "POST",
    body,
    headers: {
      ...(API_KEY ? { "X-BoardPilot-API-Key": API_KEY } : {})
    }
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function uploadImageAsset(payload: {
  product_id: string;
  image_type: string;
  manual_description: string;
  file: File;
}) {
  const body = new FormData();
  body.append("product_id", payload.product_id);
  body.append("image_type", payload.image_type);
  body.append("manual_description", payload.manual_description);
  body.append("file", payload.file);
  const response = await fetch(`${API_BASE}/image-assets/upload`, {
    method: "POST",
    body,
    headers: {
      ...(API_KEY ? { "X-BoardPilot-API-Key": API_KEY } : {})
    }
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

export function askQuestion(payload: {
  question: string;
  product_id?: string;
  metadata_filters_json?: Record<string, unknown>;
  attachments?: Array<{ artifact_id: string; attachment_type: string; description?: string }>;
}) {
  return request<AskResponse>("/ask", { method: "POST", body: JSON.stringify(payload) });
}

export function getQuestion(id: string) {
  return request<Question>(`/questions/${id}`);
}

export function getAnswer(id: string) {
  return request<Answer>(`/answers/${id}`);
}

export function getAnswerEvidence(answerId: string) {
  return request<Evidence[]>(`/answers/${answerId}/evidence`);
}

export function listRetrievalCandidates(runId: string) {
  return request<RetrievalCandidate[]>(`/retrieval-runs/${runId}/candidates`);
}

export function sendAnswerFeedback(answerId: string, payload: { feedback_type: string; notes: string }) {
  return request<ReviewItem>(`/answers/${answerId}/feedback`, { method: "POST", body: JSON.stringify(payload) });
}

export type EvalCasePayload = {
  question_text: string;
  product_id?: string;
  expected_source_ids_json?: string[];
  expected_chunk_ids_json?: string[];
  expected_answer_points_json?: string[];
  tags_json?: string[];
  difficulty?: string;
  active?: boolean;
};

export function createEvalCase(payload: EvalCasePayload) {
  return request<EvalCase>("/eval-cases", { method: "POST", body: JSON.stringify(payload) });
}

export function listEvalCases() {
  return request<EvalCase[]>("/eval-cases");
}

export function updateEvalCase(id: string, payload: Partial<EvalCasePayload>) {
  return request<EvalCase>(`/eval-cases/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function seedEvalCases() {
  return request<{ case_count: number }>("/eval-cases/seed", { method: "POST" });
}

export function runEval(name: string) {
  return request<EvalRunResponse>("/eval-runs", { method: "POST", body: JSON.stringify({ name }) });
}

export function compareEvalRuns(runA: string, runB: string) {
  return request<EvalRunComparison>(`/eval-runs/compare?run_a=${runA}&run_b=${runB}`);
}

export function listEvalRunResults(runId: string) {
  return request<EvalResult[]>(`/eval-runs/${runId}/results`);
}

export function convertEvalResultToReview(id: string) {
  return request<ReviewItem>(`/eval-results/${id}/to-review`, { method: "POST" });
}

export function listReviewItems() {
  return request<ReviewItem[]>("/review-items");
}

export function getReviewItemDetail(id: string) {
  return request<ReviewItemDetail>(`/review-items/${id}/detail`);
}

export function listAuditLogs() {
  return request<AuditLog[]>("/audit-logs");
}

export function approveReviewItem(id: string, failure_category = "human_policy_required") {
  return request<ReviewItem>(`/review-items/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ failure_category })
  });
}

export function markReviewSourceUpdateNeeded(id: string, failure_category = "stale_source") {
  return request<ReviewItem>(`/review-items/${id}/source-update-needed`, {
    method: "POST",
    body: JSON.stringify({ failure_category })
  });
}

export function updateReviewItem(
  id: string,
  payload: Partial<Pick<ReviewItem, "failure_category" | "reviewer_notes" | "edited_answer_text">>
) {
  return request<ReviewItem>(`/review-items/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function convertReviewItemToFaq(id: string) {
  return request(`/review-items/${id}/to-faq`, { method: "POST" });
}

export function convertReviewItemToEvalCase(id: string) {
  return request(`/review-items/${id}/to-eval-case`, { method: "POST" });
}
