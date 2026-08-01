# -*- coding: utf-8 -*-
# Derived from AlphaSift revision 9f522747caafd3c0b1ddb7e14d5cf44c8580b6cf.
# Licensed under Apache-2.0 and modified for daily_stock_analysis.
"""Deterministic near-score rotation for per-client screening variants."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from src.services.screening.models import Pick


@dataclass(frozen=True)
class SelectionVariant:
    picks: list[Pick]
    applied: bool = False
    pool_size: int = 0
    rotated_slots: int = 0


def apply_seeded_selection_variant(
    picks: list[Pick],
    *,
    max_output: int,
    seed: str,
    period: str,
    max_score_gap: float = 1.5,
    rotation_ratio: float = 0.34,
    analyzer_names: list[str] | None = None,
) -> SelectionVariant:
    """Rotate only the tail of Top-N among candidates with comparable scores.

    The highest-ranked part of the result remains protected. The opaque client
    seed only affects which near-cutoff candidates fill the remaining slots;
    hard filters, risk vetoes, score values, and portfolio penalties are never
    changed.

    Compatibility note: when the client does not provide a seed (empty string
    or None), preserve the original pick ordering and return a strict Top-N
    slice. This avoids silently applying the new code-based tie-breaker for
    legacy callers that expect previous stable ordering.
    """
    normalized_seed = str(seed or "").strip()

    # Respect the original ordering when no seed is provided. This preserves
    # backward compatibility for legacy clients that did not opt into rotation.
    output_count = min(max(int(max_output), 0), len(picks))
    if output_count == 0:
        return SelectionVariant(picks=[])
    if not normalized_seed or output_count < 2 or len(picks) <= output_count:
        # Preserve original order; just trim to requested output_count.
        return SelectionVariant(picks=_rerank(picks[:output_count]))

    # From here on the seed is non-empty and rotation logic may reorder
    # near-cutoff candidates. Work on a deterministically ordered list so that
    # rotation selection is stable across runs.
    ordered = sorted(picks, key=lambda item: (-float(item.final_score), item.code))
    output_count = min(max(int(max_output), 0), len(ordered))

    rotation_slots = min(
        output_count - 1,
        max(1, int(round(output_count * max(float(rotation_ratio), 0.0)))),
    )
    protected_count = output_count - rotation_slots
    protected = ordered[:protected_count]
    cutoff_score = float(ordered[output_count - 1].final_score)
    minimum_score = cutoff_score - max(float(max_score_gap), 0.0)

    def _was_post_analyzed(pick: Pick) -> bool:
        # If analyzers were configured for this run, a pick must have explicit
        # non-skipped post-analysis results for all configured analyzers to be
        # eligible for near-cutoff rotation. This prevents promoting candidates
        # that never received the same L3 treatment as protected top picks.
        status_map = pick.post_analysis_status or {}
        if not analyzer_names:
            # No analyzers configured — fall back to legacy behavior: only
            # exclude picks explicitly marked as 'skipped'.
            return not any(status == "skipped" for status in status_map.values())

        # If analyzers were configured, require each configured analyzer to have
        # an explicit completed status recorded for this pick. Missing entries or
        # explicit 'not_requested' indicate the candidate did not receive the
        # same L3 treatment and must be excluded from near-cutoff rotation. This
        # prevents promoting candidates that never completed post-analysis.
        for analyzer in analyzer_names:
            s = status_map.get(analyzer)
            # Only allow picks that explicitly completed the analyzer run.
            if s != "completed":
                return False
        return True

    pool = [
        pick
        for pick in ordered[protected_count:]
        if float(pick.final_score) >= minimum_score and _was_post_analyzed(pick)
    ]
    if len(pool) <= rotation_slots:
        return SelectionVariant(
            picks=_rerank(ordered[:output_count]),
            pool_size=len(pool),
        )

    varied_pool = sorted(
        pool,
        key=lambda pick: _variant_key(
            normalized_seed,
            period,
            pick.code,
        ),
    )
    chosen_codes = {pick.code for pick in varied_pool[:rotation_slots]}
    chosen_tail = [pick for pick in pool if pick.code in chosen_codes]
    selected = sorted(
        [*protected, *chosen_tail],
        key=lambda item: (-float(item.final_score), item.code),
    )[:output_count]
    base_codes = [pick.code for pick in ordered[:output_count]]
    selected_codes = [pick.code for pick in selected]
    changed_count = len(set(selected_codes) - set(base_codes))
    return SelectionVariant(
        picks=_rerank(selected),
        applied=changed_count > 0,
        pool_size=len(pool),
        rotated_slots=changed_count,
    )


def _variant_key(seed: str, period: str, code: str) -> bytes:
    return hashlib.sha256(f"{seed}\0{period}\0{code}".encode("utf-8")).digest()


def _rerank(picks: list[Pick]) -> list[Pick]:
    for index, pick in enumerate(picks, start=1):
        pick.rank = index
    return picks
