from collections import defaultdict
from typing import Dict, Iterable, List, Optional
from uuid import UUID

from app.models.schemas import (
    Answer,
    ApprovedFAQ,
    Chunk,
    EvalCase,
    EvalResult,
    EvalRun,
    Evidence,
    Product,
    ProductAlias,
    ModelRun,
    Question,
    RetrievalCandidate,
    RetrievalRun,
    ReviewItem,
    Source,
    SourceArtifact,
    SourceVersion,
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
        self.chunks: Dict[UUID, Chunk] = {}
        self.questions: Dict[UUID, Question] = {}
        self.retrieval_runs: Dict[UUID, RetrievalRun] = {}
        self.retrieval_candidates: Dict[UUID, RetrievalCandidate] = {}
        self.evidences: Dict[UUID, Evidence] = {}
        self.answers: Dict[UUID, Answer] = {}
        self.model_runs: Dict[UUID, ModelRun] = {}
        self.review_items: Dict[UUID, ReviewItem] = {}
        self.approved_faqs: Dict[UUID, ApprovedFAQ] = {}
        self.eval_cases: Dict[UUID, EvalCase] = {}
        self.eval_runs: Dict[UUID, EvalRun] = {}
        self.eval_results: Dict[UUID, EvalResult] = {}
        self.tickets: List[dict] = []
        self.log_sources: List[dict] = []
        self.image_assets: List[dict] = []
        self.audit_log: List[dict] = []
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

    def add_review_item(self, item: ReviewItem) -> ReviewItem:
        self.review_items[item.id] = item
        self.audit_log.append({"action": "review_item_created", "entity_type": "ReviewItem", "entity_id": str(item.id)})
        return item

    def add_approved_faq(self, faq: ApprovedFAQ) -> ApprovedFAQ:
        self.approved_faqs[faq.id] = faq
        self.audit_log.append({"action": "approved_faq_created", "entity_type": "ApprovedFAQ", "entity_id": str(faq.id)})
        return faq

    def add_eval_case(self, case: EvalCase) -> EvalCase:
        self.eval_cases[case.id] = case
        self.audit_log.append({"action": "eval_case_created", "entity_type": "EvalCase", "entity_id": str(case.id)})
        return case

    def add_eval_run(self, run: EvalRun) -> EvalRun:
        self.eval_runs[run.id] = run
        return run

    def add_eval_result(self, result: EvalResult) -> EvalResult:
        self.eval_results[result.id] = result
        return result


store = InMemoryStore()
