# -*- coding: utf-8 -*-
"""Regression contracts for the DSA-owned screening implementation."""

from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient as FastAPITestClient

from api.v1.router import router
from src.services.screening import REFERENCE_REVISION
from src.services.screening.filter import apply_hard_filters
from src.services.screening.models import HardFilterConfig, ScreeningConfig
from src.services.screening.scorer import compute_screen_scores
from src.services.screening import snapshot as screening_snapshot
from src.services.screening.strategy import load_all_strategies


REPO_ROOT = Path(__file__).resolve().parents[1]
SCREENING_ROOT = REPO_ROOT / "src" / "services" / "screening"


def test_screening_engine_is_collected_from_the_internal_package() -> None:
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    dockerfile = (REPO_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")

    assert "alphasift.git" not in requirements
    assert "#egg=alphasift" not in requirements
    assert "import src.services.screening.pipeline" in dockerfile


def test_screening_routes_have_a_primary_prefix_and_no_install_endpoint() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    schema_paths = app.openapi()["paths"]
    assert "/api/v1/screening/status" in schema_paths
    assert "/api/v1/alphasift/status" not in schema_paths

    client = FastAPITestClient(app)
    assert client.request("OPTIONS", "/api/v1/screening/status").status_code != 404
    assert client.request("OPTIONS", "/api/v1/alphasift/status").status_code == 404
    assert client.request("POST", "/api/v1/screening/install").status_code == 404


def test_bundled_engine_keeps_source_and_license_notices() -> None:
    notice = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    license_text = (SCREENING_ROOT / "LICENSE").read_text(encoding="utf-8")

    assert REFERENCE_REVISION in notice
    assert "Apache License" in license_text
    derived_files = [
        *SCREENING_ROOT.glob("*.py"),
        *(SCREENING_ROOT / "strategies").glob("*.yaml"),
    ]
    assert derived_files
    for path in derived_files:
        source = path.read_text(encoding="utf-8")
        assert f"Derived from AlphaSift revision {REFERENCE_REVISION}." in source


def test_bundled_strategies_are_loaded_from_the_internal_package() -> None:
    strategies = load_all_strategies(SCREENING_ROOT / "strategies")

    assert set(strategies) == {
        "balanced_alpha",
        "blue_chip_income",
        "capital_heat",
        "dual_low",
        "low_volatility_quality",
        "momentum_quality",
        "oversold_reversal",
        "quality_value",
        "shrink_pullback",
        "volume_breakout",
    }
    assert strategies["dual_low"].screening.factor_weights["value"] < 0.40


def test_hard_filter_and_factor_scoring_keep_core_semantics() -> None:
    frame = pd.DataFrame(
        [
            {
                "code": "low_value",
                "name": "Low Value",
                "price": 10.0,
                "amount": 200_000_000,
                "pe_ratio": 5.0,
                "pb_ratio": 0.6,
                "turnover_rate": 2.0,
                "volume_ratio": 1.2,
                "change_pct": 0.0,
            },
            {
                "code": "high_value",
                "name": "High Value",
                "price": 10.0,
                "amount": 20_000_000,
                "pe_ratio": 15.0,
                "pb_ratio": 2.0,
                "turnover_rate": 2.0,
                "volume_ratio": 1.2,
                "change_pct": 0.0,
            },
        ]
    )

    filtered = apply_hard_filters(frame, HardFilterConfig(amount_min=100_000_000))
    assert filtered["code"].tolist() == ["low_value"]

    scored = compute_screen_scores(
        frame,
        ScreeningConfig(factor_weights={"value": 1.0}),
    ).set_index("code")
    assert scored.loc["low_value", "screen_score"] > scored.loc["high_value", "screen_score"]


def test_snapshot_schema_mismatch_counts_toward_source_circuit_breaker(
    monkeypatch,
) -> None:
    bad_snapshot = pd.DataFrame([{"code": "000001", "name": "Ping An", "price": 10.0}])
    good_snapshot = pd.DataFrame(
        [{"code": "000001", "name": "Ping An", "price": 10.0, "volume_ratio": 1.5}]
    )
    source_health: dict[str, dict[str, object]] = {}
    calls: list[str] = []

    def fake_fetch(source: str) -> pd.DataFrame:
        calls.append(source)
        if source == "sina":
            return bad_snapshot
        if source == "efinance":
            return good_snapshot.copy()
        raise AssertionError(f"unexpected source {source}")

    monkeypatch.setattr(screening_snapshot, "_SOURCE_HEALTH", source_health)
    monkeypatch.setattr(screening_snapshot, "fetch_cn_snapshot", fake_fetch)

    for _ in range(3):
        result = screening_snapshot.fetch_snapshot_with_fallback(
            ["sina", "efinance"],
            required_columns=["volume_ratio"],
        )
        assert result.attrs["snapshot_source"] == "efinance"

    health = screening_snapshot.snapshot_source_health_snapshot(["sina"])
    assert health["sina"]["failures"] == 3
    assert health["sina"]["disabled"] is True

    calls.clear()
    result = screening_snapshot.fetch_snapshot_with_fallback(
        ["sina", "efinance"],
        required_columns=["volume_ratio"],
    )

    assert calls == ["efinance"]
    assert result.attrs["snapshot_source"] == "efinance"
    assert "temporarily disabled" in result.attrs["source_errors"][0]
