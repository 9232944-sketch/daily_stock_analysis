"""Tests for bounded per-client screening result rotation."""

from __future__ import annotations

import copy

from src.services.screening.models import Pick
from src.services.screening.selection_variant import apply_seeded_selection_variant


def _picks() -> list[Pick]:
    scores = [90.0, 86.0, 84.0, 83.7, 83.3, 82.0, 80.0]
    return [
        Pick(
            rank=index,
            code=f"00000{index}",
            name=f"Stock {index}",
            screen_score=score,
            final_score=score,
            risk_flags=["kept-risk"] if index == 4 else [],
        )
        for index, score in enumerate(scores, start=1)
    ]


def test_selection_variant_without_seed_preserves_top_n() -> None:
    result = apply_seeded_selection_variant(
        _picks(),
        max_output=3,
        seed="",
        period="2026-08-01",
    )

    assert [pick.code for pick in result.picks] == ["000001", "000002", "000003"]
    assert result.applied is False


def test_selection_variant_is_stable_for_same_seed_and_period() -> None:
    first = apply_seeded_selection_variant(
        copy.deepcopy(_picks()),
        max_output=3,
        seed="browser-a",
        period="2026-08-01",
    )
    second = apply_seeded_selection_variant(
        copy.deepcopy(_picks()),
        max_output=3,
        seed="browser-a",
        period="2026-08-01",
    )

    assert [pick.code for pick in first.picks] == [pick.code for pick in second.picks]
    assert [pick.rank for pick in first.picks] == [1, 2, 3]


def test_selection_variant_produces_multiple_bounded_client_variants() -> None:
    variants = {
        tuple(
            pick.code
            for pick in apply_seeded_selection_variant(
                copy.deepcopy(_picks()),
                max_output=3,
                seed=f"browser-{index}",
                period="2026-08-01",
            ).picks
        )
        for index in range(20)
    }

    assert len(variants) >= 2
    assert all(codes[:2] == ("000001", "000002") for codes in variants)
    assert all(codes[2] in {"000003", "000004", "000005"} for codes in variants)


def test_selection_variant_keeps_scores_and_risk_metadata_unchanged() -> None:
    picks = _picks()
    original = {
        pick.code: (pick.final_score, list(pick.risk_flags))
        for pick in picks
    }

    result = apply_seeded_selection_variant(
        picks,
        max_output=5,
        seed="browser-risk-check",
        period="2026-08-01",
    )

    assert result.pool_size >= result.rotated_slots
    for pick in result.picks:
        assert (pick.final_score, pick.risk_flags) == original[pick.code]


def test_selection_variant_never_promotes_skipped_post_analysis() -> None:
    """Regression: rotation must not promote picks whose post_analysis status is 'skipped'."""
    picks = _picks()
    # Simulate post-analysis: first 3 completed, ranks 4-5 skipped
    for i, pick in enumerate(picks, start=1):
        if i <= 3:
            pick.post_analysis_status = {"scorecard": "completed"}
        elif i in (4, 5):
            pick.post_analysis_status = {"scorecard": "skipped"}
        else:
            pick.post_analysis_status = {}

    result = apply_seeded_selection_variant(
        picks,
        max_output=3,
        seed="browser-variation",
        period="2026-08-01",
        analyzer_names=["scorecard"],
    )

    # Ensure none of the final picks have 'skipped' for scorecard
    for pick in result.picks:
        assert pick.post_analysis_status.get("scorecard") != "skipped"
