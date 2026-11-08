from app.schemas.candidate import CriterionEvaluation
from app.schemas.core import DecisionEnum
from app.schemas.job import Job
from app.services.scoring import criterion_weight, evaluate, is_mandatory


def job(**kw):
    base = dict(id="j", title="Dev", jd="", required=[], preferred=[], weights={},
                experience="", education="", location="", salary="", mandatory=[])
    return Job(**{**base, **kw})


def c(label, status):
    return CriterionEvaluation(label=label, status=status)


def test_weighted_score():
    j = job(weights={"Python": 5, "AWS": 1})
    out = evaluate([c("Python", "met"), c("AWS", "unmet")], j, ai_score=10)
    assert out.score == 83  # 5/6
    assert out.decision == DecisionEnum.shortlisted and not out.has_blocker


def test_partial_counts_half_and_default_weight_3():
    out = evaluate([c("Go", "partial"), c("SQL", "met")], job(), ai_score=0)
    assert out.score == 75 and out.decision == DecisionEnum.shortlisted


def test_unmet_mandatory_blocks():
    out = evaluate([c("Python", "unmet"), c("SQL", "met")], job(mandatory=["Python"]), ai_score=99)
    assert out.has_blocker and out.decision == DecisionEnum.rejected


def test_partial_or_unknown_mandatory_is_undecided():
    for s in ("partial", "unknown"):
        out = evaluate([c("Python", s)], job(mandatory=["Python"]), ai_score=99)
        assert out.decision == DecisionEnum.undecided and not out.has_blocker


def test_missing_mandatory_is_undecided():
    out = evaluate([c("SQL", "met")], job(mandatory=["Python"]), ai_score=99)
    assert out.decision == DecisionEnum.undecided


def test_label_matching_ignores_case_and_space():
    j = job(weights={"Python": 5}, mandatory=["Python"])
    assert criterion_weight(" python ", j) == 5 and is_mandatory("PYTHON", j)


def test_thresholds():
    assert evaluate([c("A", "partial")], job(), 0).decision == DecisionEnum.undecided  # 50
    assert evaluate([c("A", "met"), c("B", "unmet"), c("C", "unmet")], job(), 0).decision == DecisionEnum.rejected  # 33


def test_no_scorable_criteria_keeps_ai_score():
    assert evaluate([], job(), ai_score=64).score == 64
    assert evaluate([c("A", "unknown")], job(), ai_score=64).score == 64


def test_reworded_label_still_counts_as_job_item():
    j = job(weights={"Python": 5}, mandatory=["Python"])
    out = evaluate([c("Python programming", "unmet")], j, ai_score=90)
    assert out.has_blocker and out.decision == DecisionEnum.rejected
    assert criterion_weight("Python programming", j) == 5 and is_mandatory("Python programming", j)


def test_word_match_does_not_cross_word_boundaries():
    j = job(weights={"Java": 5}, mandatory=["Java"])
    assert not is_mandatory("JavaScript", j) and criterion_weight("JavaScript", j) == 3


def test_zero_weights_do_not_crash():
    out = evaluate([c("A", "met")], job(weights={"A": 0}), ai_score=42)
    assert out.score == 42
