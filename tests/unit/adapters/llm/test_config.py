"""`load_llm_config` (E2.2): defaults, required key, and that the key never shows up in repr/str.

Every test passes `env=` explicitly so none of this ever touches the real `.env` at the repo
root or `os.environ` — the cost policy in CLAUDE.md requires the key stay out of anything that
could be printed or logged, and a test that read the real file would risk exactly that."""

from __future__ import annotations

import pytest

from resto.adapters.llm.config import LlmConfig, MissingApiKeyError, load_llm_config


def test_requires_an_api_key() -> None:
    with pytest.raises(MissingApiKeyError):
        load_llm_config(env={})


def test_defaults_match_the_cost_policy() -> None:
    config = load_llm_config(env={"OPENROUTER_API_KEY": "fake-test-key"})
    assert config.base_url == "https://openrouter.ai/api/v1"
    assert config.default_model == "deepseek/deepseek-v4.1-flash"
    assert config.escalation_model is None
    assert config.max_output_tokens == 2048
    assert config.max_steps == 6


def test_every_field_is_overridable() -> None:
    config = load_llm_config(
        env={
            "OPENROUTER_API_KEY": "fake-test-key",
            "OPENROUTER_BASE_URL": "https://example.test/v1",
            "RESTO_LLM_DEFAULT_MODEL": "deepseek/deepseek-v4-pro-0813",
            "RESTO_LLM_ESCALATION_MODEL": "deepseek/deepseek-v4-pro-0813",
            "RESTO_LLM_MAX_OUTPUT_TOKENS": "4096",
            "RESTO_LLM_MAX_STEPS": "10",
        }
    )
    assert config.base_url == "https://example.test/v1"
    assert config.default_model == "deepseek/deepseek-v4-pro-0813"
    assert config.escalation_model == "deepseek/deepseek-v4-pro-0813"
    assert config.max_output_tokens == 4096
    assert config.max_steps == 10


def test_repr_and_str_never_include_the_key() -> None:
    config = load_llm_config(env={"OPENROUTER_API_KEY": "super-secret-value"})
    assert "super-secret-value" not in repr(config)
    assert "super-secret-value" not in str(config)
    assert "***" in repr(config)


def test_dataclass_fields_are_still_readable_by_code_that_needs_the_key() -> None:
    config = load_llm_config(env={"OPENROUTER_API_KEY": "fake-test-key"})
    assert config.api_key == "fake-test-key"
    assert isinstance(config, LlmConfig)
