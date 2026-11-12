"""
Pydantic v2 data models for the Resume Parsing Pipeline.

Defines all schemas used across phases:
- Routing (Phase 1)
- Extraction (Phase 3)
- Benchmarking (Phase 5)
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Phase 1: Routing Models ─────────────────────────────────────────────


class FileType(str, Enum):
    """Supported input file types."""

    PDF = "pdf"
    DOCX = "docx"
    IMAGE = "image"


class RouteDecision(str, Enum):
    """Where the file should be sent for text extraction."""

    DOCLING = "docling"  # Clean, machine-readable documents
    OCR = "ocr"  # Scanned / garbled / image-based documents


class RoutingResult(BaseModel):
    """Output of the file routing gateway."""

    file_path: str = Field(description="Absolute path to the input file")
    file_type: FileType = Field(description="Detected file type")
    route: RouteDecision = Field(description="Chosen extraction route")
    requires_ocr: bool = Field(
        default=False,
        description="True if the garble test flagged the document",
    )
    garble_score: float = Field(
        default=0.0,
        description="Garble score from 0.0 (clean) to 1.0 (fully garbled)",
    )
    extracted_char_count: int = Field(
        default=0,
        description="Number of characters extracted by PyMuPDF in the garble test",
    )
    extracted_preview: str = Field(
        default="",
        description="First 200 chars of extracted text (for debugging)",
    )
    reason: str = Field(
        default="",
        description="Human-readable explanation of the routing decision",
    )


# ── Phase 3: Extraction Models ──────────────────────────────────────────


class WorkExperience(BaseModel):
    """A single work experience entry extracted from a resume."""

    company: str = Field(description="Company or organization name")
    role: str = Field(description="Job title or position")
    start_date: Optional[str] = Field(
        default=None,
        description="Start date (ISO format or free text, e.g. '2020-01' or 'Jan 2020')",
    )
    end_date: Optional[str] = Field(
        default=None,
        description="End date or 'Present' if current role",
    )
    achievements: list[str] = Field(
        default_factory=list,
        description="Key achievements, responsibilities, or bullet points",
    )


class Education(BaseModel):
    """A single education entry extracted from a resume."""

    institution: str = Field(description="University or school name")
    degree: Optional[str] = Field(
        default=None,
        description="Degree type (e.g. 'B.Sc.', 'M.Eng.', 'ปริญญาตรี')",
    )
    field_of_study: Optional[str] = Field(
        default=None,
        description="Major or field of study",
    )
    graduation_year: Optional[str] = Field(
        default=None,
        description="Year of graduation or expected graduation",
    )


class CandidateProfile(BaseModel):
    """
    Complete structured profile extracted from a resume.

    This is the target schema that local LLMs must output via
    instructor-constrained generation.
    """

    full_name: str = Field(description="Candidate's full name")
    contact_email: Optional[str] = Field(
        default=None,
        description="Primary email address",
    )
    contact_phone: Optional[str] = Field(
        default=None,
        description="Primary phone number",
    )
    languages: list[str] = Field(
        default_factory=list,
        description="Languages spoken (e.g. ['Thai', 'English'])",
    )
    skills: list[str] = Field(
        default_factory=list,
        description="Explicit technical and soft skills listed in the resume",
    )
    implicit_skills: list[str] = Field(
        default_factory=list,
        description="Inferred skills deduced from job achievements and duties",
    )
    seniority_level: Optional[str] = Field(
        default=None,
        description="Estimated seniority: Junior, Mid-Level, Senior, Lead/Principal, Executive",
    )
    total_years_experience: Optional[float] = Field(
        default=None,
        description="Estimated total professional experience in years",
    )
    executive_summary: Optional[str] = Field(
        default=None,
        description="Concise 2-3 sentence executive summary of the candidate profile",
    )
    extraction_confidence: Optional[float] = Field(
        default=1.0,
        description="Extraction confidence score between 0.0 and 1.0",
    )
    experience: list[WorkExperience] = Field(
        default_factory=list,
        description="Work experience entries, ordered most recent first",
    )
    education: list[Education] = Field(
        default_factory=list,
        description="Education entries",
    )


# ── Phase 5: Benchmarking Models ────────────────────────────────────────


class ModelBenchmarkResult(BaseModel):
    """Evaluation metrics for a single model on the benchmark suite."""

    model_name: str = Field(description="Ollama model tag (e.g. 'qwen2.5:7b')")
    total_samples: int = Field(description="Number of test samples evaluated")
    schema_validity_rate: float = Field(
        description="Fraction of outputs that were valid Pydantic objects (0.0–1.0)",
    )
    avg_latency_seconds: float = Field(
        description="Average inference time per document in seconds",
    )
    avg_tokens_per_second: float = Field(
        default=0.0,
        description="Average generation speed in tokens/sec",
    )
    precision: float = Field(
        description="Skill extraction precision (0.0–1.0)",
    )
    recall: float = Field(
        description="Skill extraction recall (0.0–1.0)",
    )
    f1_score: float = Field(
        description="Harmonic mean of precision and recall (0.0–1.0)",
    )


class BenchmarkReport(BaseModel):
    """Complete benchmark report across all tested models."""

    results: list[ModelBenchmarkResult] = Field(
        default_factory=list,
        description="Per-model benchmark results",
    )
    best_model: Optional[str] = Field(
        default=None,
        description="Model with the highest F1 score",
    )
