from collections import defaultdict
from typing import Dict, Iterable, List, Optional
from uuid import UUID

from app.models.schemas import (
    Answer,
    ApprovedFAQ,
    AuditLog,
    Chunk,
    ChunkEmbedding,
    EvalCase,
    EvalResult,
    EvalRun,
    Evidence,
    ImageAsset,
    IngestionJob,
    LogSource,
    Product,
    ProductAlias,
    ProviderConfig,
    ModelRun,
    OcrResult,
    Question,
    RetrievalCandidate,
    RetrievalRun,
    ReviewItem,
    Source,
    SourceArtifact,
    SourceVersion,
    Ticket,
)


class InMemoryStore:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.products: Dict[UUID, Product] = {}
        self.product_aliases: Dict[UUID, ProductAlias] = {}
        self.sources: Dict[UUID, Source] = {}
        self.source_versions: Dict[UUID, SourceVersion] = {}
        self.source_artifacts: Dict[UUID, SourceArtifact] = {}
        self.ingestion_jobs: Dict[UUID, IngestionJob] = {}
        self.chunks: Dict[UUID, Chunk] = {}
        self.chunk_embeddings: Dict[UUID, ChunkEmbedding] = {}
        self.questions: Dict[UUID, Question] = {}
        self.retrieval_runs: Dict[UUID, RetrievalRun] = {}
        self.retrieval_candidates: Dict[UUID, RetrievalCandidate] = {}
        self.evidences: Dict[UUID, Evidence] = {}
        self.answers: Dict[UUID, Answer] = {}
        self.model_runs: Dict[UUID, ModelRun] = {}
        self.provider_configs: Dict[UUID, ProviderConfig] = {}
        self.review_items: Dict[UUID, ReviewItem] = {}
        self.approved_faqs: Dict[UUID, ApprovedFAQ] = {}
        self.eval_cases: Dict[UUID, EvalCase] = {}
        self.eval_runs: Dict[UUID, EvalRun] = {}
        self.eval_results: Dict[UUID, EvalResult] = {}
        self.tickets: Dict[UUID, Ticket] = {}
        self.log_sources: Dict[UUID, LogSource] = {}
        self.image_assets: Dict[UUID, ImageAsset] = {}
        self.ocr_results: Dict[UUID, OcrResult] = {}
        self.audit_logs: Dict[UUID, AuditLog] = {}
        self.chunk_hashes_by_version: Dict[UUID, set] = defaultdict(set)

    def add_product(self, product: Product) -> Product:
        self.products[product.id] = product
        return product

    def add_alias(self, alias: ProductAlias) -> ProductAlias:
        self.product_aliases[alias.id] = alias
        return alias

    def aliases_for_product(self, product_id: UUID) -> List[ProductAlias]:
        return [a for a in self.product_aliases.values() if a.product_id == product_id]

    def add_source(self, source: Source) -> Source:
        self.sources[source.id] = source
        return source

    def add_source_version(self, version: SourceVersion) -> SourceVersion:
        self.source_versions[version.id] = version
        return version

    def add_artifact(self, artifact: SourceArtifact) -> SourceArtifact:
        self.source_artifacts[artifact.id] = artifact
        return artifact

    def add_ingestion_job(self, job: IngestionJob) -> IngestionJob:
        self.ingestion_jobs[job.id] = job
        return job

    def add_chunks(self, chunks: Iterable[Chunk]) -> List[Chunk]:
        inserted: List[Chunk] = []
        for chunk in chunks:
            seen = self.chunk_hashes_by_version[chunk.source_version_id]
            if chunk.content_hash in seen:
                continue
            seen.add(chunk.content_hash)
            self.chunks[chunk.id] = chunk
            inserted.append(chunk)
        return inserted

    def add_chunk_embedding(self, embedding: ChunkEmbedding) -> ChunkEmbedding:
        for existing in self.chunk_embeddings.values():
            if (
                existing.chunk_id == embedding.chunk_id
                and existing.provider_name == embedding.provider_name
                and existing.model_name == embedding.model_name
            ):
                return existing
        self.chunk_embeddings[embedding.id] = embedding
        return embedding

    def embeddings_for_chunk(self, chunk_id: UUID) -> List[ChunkEmbedding]:
        return [embedding for embedding in self.chunk_embeddings.values() if embedding.chunk_id == chunk_id]

    def enabled_chunks(self, product_id: Optional[UUID] = None) -> List[Chunk]:
        chunks = [c for c in self.chunks.values() if c.enabled]
        if product_id:
            chunks = [c for c in chunks if c.product_id == product_id]
        return chunks

    def add_question(self, question: Question) -> Question:
        self.questions[question.id] = question
        return question

    def add_retrieval_run(self, run: RetrievalRun) -> RetrievalRun:
        self.retrieval_runs[run.id] = run
        return run

    def add_candidates(self, candidates: Iterable[RetrievalCandidate]) -> List[RetrievalCandidate]:
        result = list(candidates)
        for candidate in result:
            self.retrieval_candidates[candidate.id] = candidate
        return result

    def candidates_for_run(self, run_id: UUID) -> List[RetrievalCandidate]:
        return sorted(
            [c for c in self.retrieval_candidates.values() if c.retrieval_run_id == run_id],
            key=lambda c: (c.stage != "reranked", c.rank),
        )

    def add_evidence(self, evidence: Iterable[Evidence]) -> List[Evidence]:
        result = list(evidence)
        for item in result:
            self.evidences[item.id] = item
        return result

    def evidence_for_run(self, run_id: UUID) -> List[Evidence]:
        return sorted([e for e in self.evidences.values() if e.retrieval_run_id == run_id], key=lambda e: e.rank)

    def add_answer(self, answer: Answer) -> Answer:
        self.answers[answer.id] = answer
        return answer

    def add_model_run(self, model_run: ModelRun) -> ModelRun:
        self.model_runs[model_run.id] = model_run
        return model_run

    def add_provider_config(self, config: ProviderConfig, user_id: Optional[str] = None) -> ProviderConfig:
        self.provider_configs[config.id] = config
        self.add_audit_log(
            "provider_config_created",
            "ProviderConfig",
            str(config.id),
            user_id=user_id,
            after_json=config.model_dump(mode="json"),
        )
        return config

    def add_ticket(self, ticket: Ticket) -> Ticket:
        self.tickets[ticket.id] = ticket
        return ticket

    def add_log_source(self, log_source: LogSource) -> LogSource:
        self.log_sources[log_source.id] = log_source
        return log_source

    def add_image_asset(self, image_asset: ImageAsset) -> ImageAsset:
        self.image_assets[image_asset.id] = image_asset
        return image_asset

    def add_ocr_result(self, ocr_result: OcrResult) -> OcrResult:
        self.ocr_results[ocr_result.id] = ocr_result
        return ocr_result

    def add_review_item(self, item: ReviewItem) -> ReviewItem:
        self.review_items[item.id] = item
        self.add_audit_log("review_item_created", "ReviewItem", str(item.id))
        return item

    def add_approved_faq(self, faq: ApprovedFAQ) -> ApprovedFAQ:
        self.approved_faqs[faq.id] = faq
        self.add_audit_log("approved_faq_created", "ApprovedFAQ", str(faq.id), after_json=faq.model_dump(mode="json"))
        return faq

    def add_eval_case(self, case: EvalCase) -> EvalCase:
        self.eval_cases[case.id] = case
        self.add_audit_log("eval_case_created", "EvalCase", str(case.id), after_json=case.model_dump(mode="json"))
        return case

    def add_eval_run(self, run: EvalRun) -> EvalRun:
        self.eval_runs[run.id] = run
        return run

    def add_eval_result(self, result: EvalResult) -> EvalResult:
        self.eval_results[result.id] = result
        return result

    def add_audit_log(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        user_id: Optional[str] = None,
        before_json: Optional[dict] = None,
        after_json: Optional[dict] = None,
    ) -> AuditLog:
        log = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_json=before_json or {},
            after_json=after_json or {},
        )
        self.audit_logs[log.id] = log
        return log


store = InMemoryStore()
