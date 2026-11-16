"""Shared settings for the AI services (Qwen through DashScope)."""
import os

from openai import AsyncOpenAI

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
QWEN_API_URL = os.getenv("QWEN_API_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL_NAME = os.getenv("QWEN_MODEL_NAME", "qwen3.8-flash")

qwen_client = AsyncOpenAI(
    api_key=DASHSCOPE_API_KEY or "mock",
    base_url=QWEN_API_URL,
    timeout=300.0,
    max_retries=2
)


def mock_mode(key: str | None, env_name: str) -> bool:
    """Fake AI answers only on an explicit "mock" key: a missing key must fail, not store invented results."""
    if not key:
        raise RuntimeError(f"{env_name} is not set. Set it, or set it to 'mock' for tests.")
    return key == "mock"
