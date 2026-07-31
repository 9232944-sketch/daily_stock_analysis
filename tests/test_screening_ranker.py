# -*- coding: utf-8 -*-
"""Regression tests for screening LiteLLM ranking request compatibility."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

from src.llm.generation_params import clear_litellm_generation_param_recovery_cache
from src.services.screening.ranker import _call_llm


def _response(content: str = "ok") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_screening_ranker_direct_call_omits_temperature_for_gpt5() -> None:
    clear_litellm_generation_param_recovery_cache()
    completion_calls: list[dict[str, object]] = []

    def completion(**kwargs):
        completion_calls.append(dict(kwargs))
        return _response()

    fake_litellm = SimpleNamespace(completion=completion)

    with patch.dict(sys.modules, {"litellm": fake_litellm}, clear=False):
        result = _call_llm(
            "rank candidates",
            api_key="test-key",
            model="openai/gpt-5-mini",
            base_url="",
            temperature=0.2,
            json_mode=False,
        )

    assert result == "ok"
    assert "temperature" not in completion_calls[0]


def test_screening_ranker_direct_call_retries_temperature_with_param_recovery() -> None:
    clear_litellm_generation_param_recovery_cache()
    completion_calls: list[dict[str, object]] = []

    def completion(**kwargs):
        completion_calls.append(dict(kwargs))
        if len(completion_calls) == 1:
            raise RuntimeError("Unsupported parameter: temperature is not supported")
        return _response()

    fake_litellm = SimpleNamespace(completion=completion)

    with patch.dict(sys.modules, {"litellm": fake_litellm}, clear=False):
        result = _call_llm(
            "rank candidates",
            api_key="test-key",
            model="openai/custom-temp-locked",
            base_url="",
            temperature=0.7,
            json_mode=False,
        )

    assert result == "ok"
    assert completion_calls[0]["temperature"] == 0.7
    assert "temperature" not in completion_calls[1]


def test_screening_ranker_router_call_applies_kimi_temperature_and_recovery(tmp_path) -> None:
    clear_litellm_generation_param_recovery_cache()
    router_calls: list[dict[str, object]] = []

    class FakeRouter:
        def __init__(self, *, model_list):
            self.model_list = model_list

        def completion(self, **kwargs):
            router_calls.append(dict(kwargs))
            if len(router_calls) == 1:
                raise RuntimeError("Unsupported parameter: temperature is not supported")
            return _response()

    fake_litellm = SimpleNamespace(Router=FakeRouter, completion=lambda **_: _response())
    config_path = tmp_path / "litellm.yaml"
    config_path.write_text(
        """
model_list:
  - model_name: moonshot/kimi-k2.6
    litellm_params:
      model: moonshot/kimi-k2.6
        """.strip(),
        encoding="utf-8",
    )

    with patch.dict(sys.modules, {"litellm": fake_litellm}, clear=False):
        result = _call_llm(
            "rank candidates",
            api_key="test-key",
            model="moonshot/kimi-k2.6",
            base_url="",
            temperature=0.2,
            json_mode=False,
            config_path=str(config_path),
        )

    assert result == "ok"
    assert router_calls[0]["temperature"] == 1.0
    assert "temperature" not in router_calls[1]
