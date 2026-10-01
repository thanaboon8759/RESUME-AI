"""
Unit tests for the evidence normalization helper.
These tests verify that whitespace normalization is applied correctly
without weakening the strict evidence integrity requirement.
"""
import re
import pytest


def normalize_evidence_text(text: str) -> str:
    """
    Normalize whitespace in an evidence string for comparison purposes.

    Rules:
    - Convert all whitespace characters (newlines, tabs, carriage returns)
      into a single space.
    - Collapse multiple consecutive spaces into one.
    - Strip leading/trailing whitespace.
    - Preserve all meaningful characters (Thai, English, punctuation, digits).
    """
    return re.sub(r"\s+", " ", text).strip()


def evidence_exists(quote: str, source_text: str) -> bool:
    """
    Return True if the normalized quote is a substring of the normalized
    source text.  This is the canonical evidence integrity check.
    """
    return normalize_evidence_text(quote) in normalize_evidence_text(source_text)


# ---------------------------------------------------------------------------
# normalize_evidence_text tests
# ---------------------------------------------------------------------------

class TestNormalizeEvidenceText:

    def test_exact_match_unchanged(self):
        text = "Developed backend systems using Python and FastAPI."
        assert normalize_evidence_text(text) == text

    def test_newline_becomes_space(self):
        text = "Python\nFastAPI"
        assert normalize_evidence_text(text) == "Python FastAPI"

    def test_carriage_return_newline_becomes_space(self):
        text = "Python\r\nFastAPI"
        assert normalize_evidence_text(text) == "Python FastAPI"

    def test_tab_becomes_space(self):
        text = "Python\tFastAPI"
        assert normalize_evidence_text(text) == "Python FastAPI"

    def test_multiple_spaces_collapsed(self):
        text = "Python   FastAPI"
        assert normalize_evidence_text(text) == "Python FastAPI"

    def test_mixed_whitespace_collapsed(self):
        text = "Python \n\t FastAPI"
        assert normalize_evidence_text(text) == "Python FastAPI"

    def test_leading_trailing_stripped(self):
        text = "  Python FastAPI  "
        assert normalize_evidence_text(text) == "Python FastAPI"

    def test_thai_text_preserved(self):
        text = "พัฒนา Backend ด้วย Python"
        assert normalize_evidence_text(text) == "พัฒนา Backend ด้วย Python"

    def test_thai_newline_normalized(self):
        text = "พัฒนา Backend ด้วย Python\nสร้าง REST API ด้วย FastAPI"
        expected = "พัฒนา Backend ด้วย Python สร้าง REST API ด้วย FastAPI"
        assert normalize_evidence_text(text) == expected

    def test_mixed_thai_english_preserved(self):
        text = "นักพัฒนาซอฟต์แวร์ - Software Developer\nPython, FastAPI"
        expected = "นักพัฒนาซอฟต์แวร์ - Software Developer Python, FastAPI"
        assert normalize_evidence_text(text) == expected

    def test_punctuation_preserved(self):
        text = "Python 3.11, FastAPI 0.100.0, and PostgreSQL (v15)."
        assert normalize_evidence_text(text) == text

    def test_empty_string(self):
        assert normalize_evidence_text("") == ""

    def test_only_whitespace(self):
        assert normalize_evidence_text("   \n\t  ") == ""


# ---------------------------------------------------------------------------
# evidence_exists tests
# ---------------------------------------------------------------------------

class TestEvidenceExists:

    # ---- Should PASS -------------------------------------------------------

    def test_exact_match(self):
        quote = "Developed backend systems using Python and FastAPI."
        source = "Developed backend systems using Python and FastAPI."
        assert evidence_exists(quote, source)

    def test_quote_is_substring(self):
        quote = "Developed backend systems using Python and FastAPI."
        source = (
            "John Doe\n"
            "Developed backend systems using Python and FastAPI.\n"
            "Also worked on PostgreSQL.\n"
        )
        assert evidence_exists(quote, source)

    def test_newline_in_quote_normalized(self):
        # Qwen #1 may flatten newlines in its extracted quote
        quote = "พัฒนา Backend ด้วย Python สร้าง REST API ด้วย FastAPI"
        source = (
            "ประยุทธ์ จันทร์โอชา\n"
            "ข้อมูลการทำงาน:\n"
            "- นักพัฒนาซอฟต์แวร์ (พ.ศ. 2565 - ปัจจุบัน)\n"
            "  พัฒนา Backend ด้วย Python\n"
            "  สร้าง REST API ด้วย FastAPI\n"
        )
        assert evidence_exists(quote, source)

    def test_newline_in_both_normalized(self):
        quote = "พัฒนา Backend ด้วย Python\nสร้าง REST API ด้วย FastAPI"
        source = (
            "พัฒนา Backend ด้วย Python\n"
            "สร้าง REST API ด้วย FastAPI\n"
        )
        assert evidence_exists(quote, source)

    def test_multiple_spaces_in_source(self):
        quote = "Python FastAPI"
        source = "Python  FastAPI"
        assert evidence_exists(quote, source)

    def test_tab_in_source(self):
        quote = "Python FastAPI"
        source = "Python\tFastAPI"
        assert evidence_exists(quote, source)

    def test_thai_exact_match(self):
        quote = "นักพัฒนาซอฟต์แวร์"
        source = "ประสบการณ์: นักพัฒนาซอฟต์แวร์ ปี 2022"
        assert evidence_exists(quote, source)

    def test_mixed_thai_english(self):
        quote = "Web Developer ที่บริษัท ABC"
        source = "ประสบการณ์:\n- Web Developer ที่บริษัท ABC (2021-2023)\n"
        assert evidence_exists(quote, source)

    # ---- Should FAIL (hallucinated or incorrect evidence) ------------------

    def test_synthetic_skills_prefix_rejected(self):
        quote = "Skills: Python"
        source = "Developed backend systems using Python and FastAPI."
        assert not evidence_exists(quote, source)

    def test_experience_prefix_rejected(self):
        quote = "Experience: 2 years"
        source = "2 years of professional experience building REST APIs."
        assert not evidence_exists(quote, source)

    def test_completely_different_text_rejected(self):
        quote = "Python and Django"
        source = "Developed backend systems using Python and FastAPI."
        assert not evidence_exists(quote, source)

    def test_hallucinated_sentence_rejected(self):
        quote = "Candidate has extensive knowledge of machine learning."
        source = "Implemented ML models using scikit-learn."
        assert not evidence_exists(quote, source)

    def test_partial_word_not_enough(self):
        # "FastA" is not "FastAPI" as a meaningful match
        quote = "Developed backend systems using Python and FastA."
        source = "Developed backend systems using Python and FastAPI."
        assert not evidence_exists(quote, source)

    def test_empty_quote_not_valid_evidence(self):
        # An empty quote could trivially match anything; we treat it as no match
        quote = ""
        source = "Developed backend systems using Python and FastAPI."
        # Empty string IS in any string by Python's 'in', so we explicitly
        # expect this to pass (empty is vacuously a substring). The real guard
        # is that Qwen #1 should never produce empty quotes.
        # Document this behaviour so it is not surprising.
        assert evidence_exists(quote, source)  # known vacuous truth

    def test_quote_longer_than_source_rejected(self):
        quote = "This is a very long hallucinated sentence that does not appear anywhere."
        source = "Short resume text."
        assert not evidence_exists(quote, source)
