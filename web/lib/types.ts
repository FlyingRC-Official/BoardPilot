export type Product = {
  id: string;
  name: string;
  slug: string;
  description: string;
  status: string;
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

export type ReviewItem = {
  id: string;
  source_type: string;
  status: string;
  priority: number;
  failure_category?: string;
  reviewer_notes?: string;
  edited_answer_text?: string;
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
    summary_metrics_json: Record<string, number>;
  };
  results: Array<Record<string, unknown>>;
};
