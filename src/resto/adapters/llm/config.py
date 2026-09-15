"""Configuration for the real `ToolAgent` (`adapters/llm/anthropic_client.py`), which talks to
OpenRouter rather than the Anthropic API directly (CLAUDE.md "LLM provider & cost policy").

Reads from the process environment, loading `.env` at the repo root first if present, so a local
`OPENROUTER_API_KEY` never has to be exported by hand — an explicitly exported environment
variable always wins over the `.env` file. **The key never appears in a log, a print, an
exception message, or this module's own repr/str output** — see `LlmConfig.__repr__`. Nothing
here reads `.env`'s contents into a variable this module prints or returns beyond `api_key`
itself; callers must keep that discipline (never `str()`/log an `OpenAI` client's headers).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
DEFAULT_MAX_OUTPUT_TOKENS = 2048
DEFAULT_MAX_STEPS = 6

_ENV_LOADED = False


class MissingApiKeyError(RuntimeError):
    """`OPENROUTER_API_KEY` is not set. Never put an env var's value in this message."""


@dataclass(frozen=True, slots=True, repr=False)
class LlmConfig:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    default_model: str = DEFAULT_MODEL
    escalation_model: str | None = None
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    max_steps: int = DEFAULT_MAX_STEPS

    def __repr__(self) -> str:  # never let a stray print()/log leak the key
        return (
            f"LlmConfig(api_key='***', base_url={self.base_url!r}, "
            f"default_model={self.default_model!r}, escalation_model={self.escalation_model!r}, "
            f"max_output_tokens={self.max_output_tokens}, max_steps={self.max_steps})"
        )

    __str__ = __repr__


def load_llm_config(env: Mapping[str, str] | None = None) -> LlmConfig:
    """Builds the config from `env` (defaults to `os.environ`, loading `.env` first).

    Raises:
        MissingApiKeyError: `OPENROUTER_API_KEY` is not set.
    """
    if env is None:
        _load_dotenv_once()
        env = os.environ

    api_key = env.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise MissingApiKeyError(
            "OPENROUTER_API_KEY is not set — copy .env.example to .env and fill it in"
        )
    escalation_model = env.get("RESTO_LLM_ESCALATION_MODEL", "").strip() or None
    return LlmConfig(
        api_key=api_key,
        base_url=env.get("OPENROUTER_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
        default_model=env.get("RESTO_LLM_DEFAULT_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        escalation_model=escalation_model,
        max_output_tokens=int(
            env.get("RESTO_LLM_MAX_OUTPUT_TOKENS", str(DEFAULT_MAX_OUTPUT_TOKENS))
        ),
        max_steps=int(env.get("RESTO_LLM_MAX_STEPS", str(DEFAULT_MAX_STEPS))),
    )


def _repo_root() -> Path:
    # this file is src/resto/adapters/llm/config.py
    return Path(__file__).resolve().parents[4]


def _load_dotenv_once() -> None:
    """Parses `.env` (KEY=VALUE per line, `#` comments, blank lines skipped) into `os.environ`,
    without ever overwriting a variable the shell already set. Silently does nothing if there is
    no `.env` — that's expected in CI, where real vars are exported directly."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    env_path = _repo_root() / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip()
