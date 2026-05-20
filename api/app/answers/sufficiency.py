from app.models.schemas import Evidence, EvidenceSufficiency


def assess_sufficiency(evidence: list[Evidence]) -> tuple[EvidenceSufficiency, float]:
    if len(evidence) >= 3 and evidence[0].score >= 0.35:
        return EvidenceSufficiency.sufficient, min(0.95, evidence[0].score)
    if evidence:
        return EvidenceSufficiency.partial, min(0.7, evidence[0].score)
    return EvidenceSufficiency.insufficient, 0.0

