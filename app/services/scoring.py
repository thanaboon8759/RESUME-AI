"""Turns per-criterion AI statuses plus the job's own rules into a score and decision."""
import re
from dataclasses import dataclass

from app.schemas.candidate import CriterionEvaluation
from app.schemas.core import CriterionStatusEnum, DecisionEnum
from app.schemas.job import Job

DEFAULT_WEIGHT = 3
SHORTLIST_AT = 70
REJECT_BELOW = 50
_WORST_FIRST = [CriterionStatusEnum.unmet, CriterionStatusEnum.partial, CriterionStatusEnum.unknown, CriterionStatusEnum.met]
POINTS = {CriterionStatusEnum.met: 1.0, CriterionStatusEnum.partial: 0.5, CriterionStatusEnum.unmet: 0.0}


@dataclass(frozen=True)
class Outcome:
    score: int
    decision: DecisionEnum
    has_blocker: bool


def _norm(label: str) -> str:
    return label.strip().lower()


def _find(item: str, labels: list[str]) -> int | None:
    """Index of the label naming this job item: exact match first, else the item as whole words
    inside a reworded label ("Python" in "Python programming", but not "Java" in "JavaScript")."""
    norm = [_norm(l) for l in labels]
    target = _norm(item)
    if target in norm:
        return norm.index(target)
    word = re.compile(rf"(?<!\w){re.escape(target)}(?!\w)")
    # shortcut: whole-word match misses translations and Thai (no spaces); upgrade to id-based matching if that shows up.
    return next((i for i, l in enumerate(norm) if target and word.search(l)), None)


def criterion_weight(label: str, job: Job) -> int:
    keys = list(job.weights)
    hit = next((k for k in keys if _norm(k) == _norm(label)), None) or \
        next((k for k in keys if _find(k, [label]) is not None), None)
    return job.weights[hit] if hit is not None else DEFAULT_WEIGHT


def is_mandatory(label: str, job: Job) -> bool:
    return any(_find(m, [label]) is not None for m in job.mandatory)


def evaluate(criteria: list[CriterionEvaluation], job: Job, ai_score: int) -> Outcome:
    # The AI may list one item twice; keep it once, with its worst status, so a "met" copy can't hide an "unmet".
    unique: dict[str, CriterionEvaluation] = {}
    for c in criteria:
        key, prev = _norm(c.label), unique.get(_norm(c.label))
        if prev is None or _WORST_FIRST.index(CriterionStatusEnum(c.status)) < _WORST_FIRST.index(CriterionStatusEnum(prev.status)):
            unique[key] = c if prev is None else prev.model_copy(update={"status": c.status})
    criteria = list(unique.values())
    labels = [c.label for c in criteria]

    total = earned = 0.0
    for c in criteria:
        status = CriterionStatusEnum(c.status)
        if status in POINTS:
            w = criterion_weight(c.label, job)
            total += w
            earned += w * POINTS[status]
    # Nothing scorable (no criteria, all unknown, or all weight 0): keep the AI's own score.
    score = round(100 * earned / total) if total > 0 else ai_score

    found = [_find(m, labels) for m in job.mandatory]
    mandatory = [CriterionStatusEnum(criteria[i].status) if i is not None else None for i in found]
    if CriterionStatusEnum.unmet in mandatory:
        return Outcome(score, DecisionEnum.rejected, True)
    if any(s != CriterionStatusEnum.met for s in mandatory):  # partial, unknown, or never evaluated (None)
        return Outcome(score, DecisionEnum.undecided, False)
    if score >= SHORTLIST_AT:
        return Outcome(score, DecisionEnum.shortlisted, False)
    if score < REJECT_BELOW:
        return Outcome(score, DecisionEnum.rejected, False)
    return Outcome(score, DecisionEnum.undecided, False)
