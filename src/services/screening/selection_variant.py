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
) -> SelectionVariant:
    """Rotate only the tail of Top-N among candidates with comparable scores.

    The highest-ranked part of the result remains protected. The opaque client
    seed only affects which near-cutoff candidates fill the remaining slots;
    hard filters, risk vetoes, score values, and portfolio penalties are never
    changed.
    """
    ordered = sorted(picks, key=lambda item: (-float(item.final_score), item.code))
    output_count = min(max(int(max_output), 0), len(ordered))
    normalized_seed = str(seed or "").strip()
    if output_count == 0:
        return SelectionVariant(picks=[])
    if not normalized_seed or len(ordered) <= output_count or output_count < 2:
        return SelectionVariant(picks=_rerank(ordered[:output_count]))

    rotation_slots = min(
        output_count - 1,
        max(1, int(round(output_count * max(float(rotation_ratio), 0.0)))),
    )
    protected_count = output_count - rotation_slots
    protected = ordered[:protected_count]
    cutoff_score = float(ordered[output_count - 1].final_score)
    minimum_score = cutoff_score - max(float(max_score_gap), 0.0)
    pool = [
        pick
        for pick in ordered[protected_count:]
        if float(pick.final_score) >= minimum_score
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
