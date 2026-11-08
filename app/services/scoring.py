"""Turns per-criterion AI statuses plus the job's own rules into a score and decision."""
from dataclasses import dataclass

from app.schemas.candidate import CriterionEvaluation
from app.schemas.core import CriterionStatusEnum, DecisionEnum
from app.schemas.job import Job

DEFAULT_WEIGHT = 3
SHORTLIST_AT = 70
REJECT_BELOW = 50
POINTS = {CriterionStatusEnum.met: 1.0, CriterionStatusEnum.partial: 0.5, CriterionStatusEnum.unmet: 0.0}


@dataclass(frozen=True)
class Outcome:
    score: int
    decision: DecisionEnum
    has_blocker: bool


def _norm(label: str) -> str:
    return label.strip().lower()


def criterion_weight(label: str, job: Job) -> int:
    weights = {_norm(k): v for k, v in job.weights.items()}
    return weights.get(_norm(label), DEFAULT_WEIGHT)


def is_mandatory(label: str, job: Job) -> bool:
    return _norm(label) in {_norm(m) for m in job.mandatory}


def evaluate(criteria: list[CriterionEvaluation], job: Job, ai_score: int) -> Outcome:
    statuses = {_norm(c.label): CriterionStatusEnum(c.status) for c in criteria}

    total = earned = 0.0
    for c in criteria:
        status = CriterionStatusEnum(c.status)
        if status in POINTS:
            w = criterion_weight(c.label, job)
            total += w
            earned += w * POINTS[status]
    # Nothing scorable (no criteria, all unknown, or all weight 0): keep the AI's own score.
    score = round(100 * earned / total) if total > 0 else ai_score

    mandatory = [statuses.get(_norm(m)) for m in job.mandatory]
    if CriterionStatusEnum.unmet in mandatory:
        return Outcome(score, DecisionEnum.rejected, True)
    if any(s != CriterionStatusEnum.met for s in mandatory):  # partial, unknown, or never evaluated (None)
        return Outcome(score, DecisionEnum.undecided, False)
    if score >= SHORTLIST_AT:
        return Outcome(score, DecisionEnum.shortlisted, False)
    if score < REJECT_BELOW:
        return Outcome(score, DecisionEnum.rejected, False)
    return Outcome(score, DecisionEnum.undecided, False)
