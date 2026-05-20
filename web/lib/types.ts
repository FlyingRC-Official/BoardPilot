export type Product = {
  id: string;
  name: string;
  slug: string;
  description: string;
  status: string;
};

export type ProductAlias = {
  id: string;
  product_id: string;
  alias: string;
  alias_type: string;
  confidence: number;
};

export type ProviderConfig = {
  id: string;
  provider_type: string;
  provider_name: string;
  model_name: string;
  config_json: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
};

export type Source = {
  id: string;
  product_id: string;
  title: string;
  source_type: string;
  canonical_uri: string;
  status: string;
  trust_level: string;
};

export type SourceVersion = {
  id: string;
  source_id: string;
  version_label: string;
  content_hash: string;
  status: string;
  parser_version: string;
  created_at: string;
};

export type SourceArtifact = {
  id: string;
  source_version_id: string;
  artifact_type: string;
  storage_uri: string;
  mime_type: string;
  size_bytes: number;
  checksum: string;
  content: string;
};

export type IngestionJob = {
  id: string;
  source_version_id: string;
  status: string;
  error_message: string;
  chunk_count: number;
};

export type Chunk = {
  id: string;
  source_version_id: string;
  product_id: string;
  chunk_index: number;
  content: string;
  token_count: number;
};

export type Evidence = {
  id: string;
  retrieval_run_id: string;
  chunk_id: string;
  rank: number;
  score: number;
  quote: string;
  selection_reason: string;
};

export type RetrievalCandidate = {
  id: string;
  retrieval_run_id: string;
  chunk_id: string;
  stage: string;
  source: string;
  keyword_score: number;
  vector_score: number;
  merged_score: number;
  rerank_score: number;
  rank: number;
};

export type Answer = {
  id: string;
  answer_text: string;
  evidence_sufficiency: "sufficient" | "partial" | "insufficient";
  confidence: number;
  citation_map_json: Record<string, string[]>;
};

export type Question = {
  id: string;
  product_id?: string;
  raw_text: string;
  normalized_text: string;
};

export type ReviewItem = {
  id: string;
  source_type: string;
  status: string;
  priority: number;
  failure_category?: string;
  reviewer_notes?: string;
  edited_answer_text?: string;
};

export type EvalResult = {
  id: string;
  eval_run_id: string;
  eval_case_id: string;
  question_id: string;
  retrieval_run_id: string;
  answer_id: string;
  recall_at_20: number;
  rerank_at_5: number;
  citation_support_rate: number;
  unsupported_claim_rate: number;
  need_review: boolean;
  failure_category?: string | null;
  metrics_json: Record<string, unknown>;
};

export type ReviewItemDetail = {
  item: ReviewItem;
  question?: Question | null;
  answer?: Answer | null;
  evidence: Evidence[];
  candidates: RetrievalCandidate[];
  eval_result?: EvalResult | null;
};

export type AuditLog = {
  id: string;
  user_id?: string;
  action: string;
  entity_type: string;
  entity_id: string;
  before_json: Record<string, unknown>;
  after_json: Record<string, unknown>;
  created_at: string;
};

export type AskResponse = {
  evidence: Evidence[];
  candidates: RetrievalCandidate[];
  answer: Answer;
  review_item?: ReviewItem | null;
};

export type EvalRunResponse = {
  eval_run: {
    id: string;
    name: string;
    summary_metrics_json: Record<string, number | Record<string, number>>;
  };
  results: Array<Record<string, unknown>>;
};

export type EvalRunSummary = EvalRunResponse["eval_run"];

export type EvalRunComparison = {
  baseline: EvalRunSummary;
  candidate: EvalRunSummary;
  deltas: Record<string, number>;
};
