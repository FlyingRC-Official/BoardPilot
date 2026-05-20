from app.db.store import InMemoryStore
from app.models.schemas import EvalCase, EvalCaseCreate, Product, Source, SourceCreate, SourceType, SourceVersionCreate
from app.sources.service import create_source, create_source_version


SEED_CASES = [
    ("Can I power servos from USB?", "USB power is only for configuration; do not power servos from USB.", ["power", "setup"]),
    ("Which outputs support PWM motors?", "PWM outputs are available on M1 to M4.", ["wiring", "pwm"]),
    ("When should I enable bidirectional DShot?", "Enable bidirectional DShot only after timer mapping and ESC firmware support are confirmed.", ["firmware", "dshot"]),
    ("What should I check before DShot setup?", "Check timer mapping and ESC firmware support before DShot setup.", ["firmware", "dshot"]),
    ("What is the safe USB use?", "Use USB for configuration only.", ["power", "safety"]),
    ("How do I handle a motor output issue?", "Inspect M1 to M4 wiring and confirm the configured output protocol.", ["hardware_fault", "wiring"]),
    ("What sources should support answers?", "Answers should use saved evidence chunks with visible citations.", ["policy", "citations"]),
    ("What happens with insufficient evidence?", "Insufficient evidence should route the answer to human review.", ["review", "policy"]),
    ("How are approved FAQs reused?", "Approved FAQs are re-ingested so future retrieval can find them.", ["review", "faq"]),
    ("What should source versions preserve?", "Source versions preserve exact content hashes and parser versions.", ["sources", "versioning"]),
    ("How should duplicate chunks be handled?", "Duplicate chunks are detected by content hash and not repeatedly inserted.", ["sources", "dedup"]),
    ("What should a retrieval trace show?", "Retrieval traces should expose candidates, stages, ranks, and scores.", ["retrieval", "trace"]),
    ("What is the evidence pack?", "The evidence pack contains selected chunks, quotes, ranks, scores, and reasons.", ["evidence", "retrieval"]),
    ("Can auto-detected product aliases be strict filters?", "Auto-detected aliases should usually be soft boosts unless confidence is high.", ["aliases", "metadata"]),
    ("When is a product hard filter allowed?", "A user-selected product can be used as a hard filter.", ["metadata", "filters"]),
    ("What does Citation Support Rate measure?", "Citation Support Rate measures whether answer claims are backed by saved evidence ids.", ["eval", "citations"]),
    ("What does Rerank@5 measure?", "Rerank@5 measures whether expected chunks appear in the reranked top five.", ["eval", "rerank"]),
    ("What does Recall@20 measure?", "Recall@20 measures whether expected chunks appear in the broader recall set.", ["eval", "recall"]),
    ("What should review failures include?", "Review failures should include a failure category for improvement tracking.", ["review", "failure_category"]),
    ("What roles should the MVP recognize?", "The MVP should recognize admin, support, reviewer, and viewer roles.", ["security", "roles"]),
]


def seed_eval_cases(store: InMemoryStore) -> tuple[Product, Source, list[EvalCase]]:
    product = next((p for p in store.products.values() if p.slug == "boardpilot-seed-controller"), None)
    if product is None:
        product = store.add_product(
            Product(
                name="BoardPilot Seed Controller",
                slug="boardpilot-seed-controller",
                description="Seed hardware support product for retrieval and eval smoke tests.",
            )
        )

    source = next((s for s in store.sources.values() if s.product_id == product.id and s.title == "BoardPilot Seed Hardware FAQ"), None)
    if source is None:
        source = create_source(
            store,
            SourceCreate(
                product_id=product.id,
                title="BoardPilot Seed Hardware FAQ",
                source_type=SourceType.markdown,
                trust_level="approved",
            ),
        )
        content = "\n\n".join(
            f"### Seed case {index}\nQuestion: {question}\nAnswer: {answer}"
            for index, (question, answer, _tags) in enumerate(SEED_CASES, start=1)
        )
        create_source_version(store, source.id, SourceVersionCreate(version_label="seed-v1", content=content, parser_version="seed-faq-v1"))

    seeded_cases: list[EvalCase] = []
    existing_questions = {case.question_text for case in store.eval_cases.values()}
    chunks = [chunk for chunk in store.chunks.values() if chunk.product_id == product.id]
    for question, answer, tags in SEED_CASES:
        expected_chunk_ids = [chunk.id for chunk in chunks if question in chunk.content]
        if question in existing_questions:
            seeded_cases.extend([case for case in store.eval_cases.values() if case.question_text == question])
            continue
        seeded_cases.append(
            store.add_eval_case(
                EvalCase(
                    **EvalCaseCreate(
                        product_id=product.id,
                        question_text=question,
                        expected_chunk_ids_json=expected_chunk_ids[:1],
                        expected_answer_points_json=[answer],
                        tags_json=["seed", *tags],
                        difficulty="seed",
                    ).model_dump()
                )
            )
        )
    return product, source, seeded_cases

