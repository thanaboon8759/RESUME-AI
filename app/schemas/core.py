from enum import Enum

class DecisionEnum(str, Enum):
    shortlisted = "shortlisted"
    rejected = "rejected"
    undecided = "undecided"

class CriterionStatusEnum(str, Enum):
    met = "met"
    partial = "partial"
    unmet = "unmet"
    unknown = "unknown"

class UploadStatusEnum(str, Enum):
    queued = "queued"
    reading = "reading"
    done = "done"
    failed = "failed"
