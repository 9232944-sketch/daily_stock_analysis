# -*- coding: utf-8 -*-
"""Decision-first HTML posters for Markdown stock and market reports.

The notification pipeline currently owns a Markdown string, rather than the
original Pydantic/dataclass payload.  This module therefore extracts only the
stable, renderer-generated Markdown contract and turns it into a compact share
card.  Missing fields are hidden; no price, score, signal, or market statistic
is inferred.
"""

from __future__ import annotations

import base64
import html
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

import markdown2


PROJECT_URL = "https://github.com/ZhuLinsen/daily_stock_analysis"
XIAOHONGSHU_URL = "http://xhslink.com/m/tU520DWCKT"
_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "share_image"
_MARKET_RE = re.compile(
    r"(?:大盘复盘|市场复盘|market\s+(?:review|recap)|시황\s*리뷰)", re.IGNORECASE
)
_MARKET_SCOPE_RE = re.compile(
    r"(?:A股|港股|美股|日股|韩股|中国\s*A주|미국|홍콩|일본|한국|\b(?:cn|hk|us|jp|kr)\b|a[-\s]?share|hong\s+kong|japan|korea|u\.?s\.?)",
    re.IGNORECASE,
)
_DASHBOARD_RE = re.compile(r"(?:决策仪表盘|decision\s+dashboard)", re.IGNORECASE)
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.MULTILINE)
_QUOTE_RE = re.compile(r"^\s*>\s+(.+?)\s*$", re.MULTILINE)
_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})(?:[ T]\d{2}:\d{2}(?::\d{2})?)?\b")
_CODE_RE = re.compile(
    r"(?:\(|（)?((?:(?i:sh|sz|bj|hk))?\d{5,6}(?:\.[A-Z]{2})?|(?<![A-Za-z])[A-Z]{1,5}(?:\.[A-Z])?(?![A-Za-z]))(?:\)|）)?",
)
_NUMERIC_CODE_RE = re.compile(r"(?:(?i:sh|sz|bj|hk))?\d{5,6}(?:\.[A-Z]{2})?")
_NA_VALUES = {"", "-", "--", "n/a", "na", "none", "null", "暂无", "暂无数据"}
_MARKET_LABEL_PATTERNS = (
    (
        "A股",
        re.compile(
            r"(?:A\s*股|a[-\s]?share|\bcn\s+market\s+(?:review|recap)\b|\bchina\b|중국\s*A주)",
            re.IGNORECASE,
        ),
    ),
    (
        "港股",
        re.compile(
            r"(?:港\s*股|\bhk\s+market\s+(?:review|recap)\b|hong\s+kong|홍콩)",
            re.IGNORECASE,
        ),
    ),
    (
        "美股",
        re.compile(
            r"(?:美\s*股|\b(?:u\.?s\.?|us)\s+market\s+(?:review|recap)\b|united\s+states|미국)",
            re.IGNORECASE,
        ),
    ),
    ("日股", re.compile(r"(?:日\s*股|japan|일본)", re.IGNORECASE)),
    ("韩股", re.compile(r"(?:韩\s*股|korea|한국)", re.IGNORECASE)),
)


@dataclass
class Table:
    headers: list[str]
    rows: list[list[str]]
    raw_rows: list[list[str]] = field(default_factory=list)


@dataclass
class StockPoster:
    title: str
    code: str = ""
    report_date: str = ""
    action: str = ""
    score: str = ""
    trend: str = ""
    conclusion: str = ""
    snapshot: list[tuple[str, str, str]] = field(default_factory=list)
    sniper: list[tuple[str, str, str]] = field(default_factory=list)
    technical: list[tuple[str, str, str]] = field(default_factory=list)
    catalysts: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    no_position: str = ""
    has_position: str = ""
    position_size: str = ""
    entry_plan: str = ""
    risk_control: str = ""
    data_source: str = ""


@dataclass
class MarketPoster:
    title: str
    report_date: str = ""
    summary: str = ""
    score: str = ""
    temperature: str = ""
    signal: str = ""
    guidance: str = ""
    reasons: list[str] = field(default_factory=list)
    indices: list[tuple[str, str, str, str]] = field(default_factory=list)
    breadth: list[tuple[str, str, str]] = field(default_factory=list)
    sectors: list[tuple[str, str]] = field(default_factory=list)
    catalysts: list[str] = field(default_factory=list)
    plan: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


@dataclass
class MarketSegment:
    title: str
    markdown: str


def _asset_data_uri(filename: str, mime_type: str) -> str:
    payload = (_ASSET_DIR / filename).read_bytes()
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _plain(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[*_`~]", "", text)
    text = re.sub(r"^[^\w\u4e00-\u9fff+\-]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_value(value: object, *, limit: int = 90) -> str:
    text = _plain(value)
    text = re.sub(
        r"^(?:理想买入点|次优买入点|止损位?|目标位?|ideal entry|secondary entry|stop loss|target)\s*[:：]\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    if text.lower() in _NA_VALUES:
        return ""
    if len(text) > limit:
        return text[: limit - 1].rstrip("，,；;。.") + "…"
    return text


def _escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def _extract_sections(markdown_text: str) -> list[tuple[str, str, int]]:
    matches = list(_HEADING_RE.finditer(markdown_text or ""))
    sections: list[tuple[str, str, int]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown_text)
        sections.append((_plain(match.group(2)), markdown_text[start:end].strip(), len(match.group(1))))
    return sections


def _section(markdown_text: str, *terms: str) -> str:
    matches = list(_HEADING_RE.finditer(markdown_text or ""))
    for index, match in enumerate(matches):
        title = _plain(match.group(2)).lower()
        if not any(term.lower() in title for term in terms):
            continue
        level = len(match.group(1))
        end = len(markdown_text)
        for following in matches[index + 1 :]:
            if len(following.group(1)) <= level:
                end = following.start()
                break
        return markdown_text[match.end() : end].strip()
    return ""


def _parse_tables(markdown_text: str) -> list[Table]:
    lines = (markdown_text or "").splitlines()
    tables: list[Table] = []
    index = 0
    while index < len(lines):
        if not lines[index].strip().startswith("|"):
            index += 1
            continue
        block: list[str] = []
        while index < len(lines) and lines[index].strip().startswith("|"):
            block.append(lines[index].strip())
            index += 1
        if len(block) < 2:
            continue
        raw_cells = [[cell.strip() for cell in row.strip("|").split("|")] for row in block]
        if not all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in raw_cells[1]):
            continue
        cells = [
            [_clean_value(cell, limit=140) for cell in row.strip("|").split("|")]
            for row in block
        ]
        width = len(cells[0])
        rows = [row[:width] + [""] * max(0, width - len(row)) for row in cells[2:]]
        tables.append(Table(headers=cells[0], rows=rows, raw_rows=raw_cells[2:]))
    return tables


def _table_map(table: Table) -> dict[str, str]:
    return {
        _plain(row[0]).lower(): _clean_value(row[1], limit=120)
        for row in table.rows
        if len(row) >= 2 and _plain(row[0])
    }


def _find_table(markdown_text: str, *header_terms: str) -> Optional[Table]:
    for table in _parse_tables(markdown_text):
        header = " ".join(table.headers).lower()
        body = " ".join(" ".join(row) for row in table.rows).lower()
        if all(term.lower() in f"{header} {body}" for term in header_terms):
            return table
    return None


def _mapped_value(mapping: dict[str, str], *labels: str) -> str:
    for key, value in mapping.items():
        if any(label.lower() in key for label in labels) and _clean_value(value):
            return _clean_value(value)
    return ""


def _labeled_value(text: str, *labels: str, limit: int = 100) -> str:
    joined = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:\*{{0,2}}(?:{joined})\*{{0,2}})\s*[:：]\s*(.+?)(?=\s*\||\n|$)",
        text or "",
        flags=re.IGNORECASE,
    )
    return _clean_value(match.group(1), limit=limit) if match else ""


def _list_after_label(text: str, *labels: str, limit: int = 3) -> list[str]:
    joined = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:\*{{0,2}}[^\n]*(?:{joined})[^\n]*\*{{0,2}})\s*[:：]?\s*\n(?P<body>.*?)(?=\n\s*\*{{1,2}}[^\n]+\*{{1,2}}\s*[:：]|\n#|\Z)",
        text or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []
    items = []
    for line in match.group("body").splitlines():
        cleaned = _clean_value(re.sub(r"^\s*(?:[-*+]\s+|\d+[.)、]\s*)", "", line), limit=72)
        if cleaned:
            items.append(cleaned)
        if len(items) >= limit:
            break
    return items


def _section_items(text: str, *, limit: int = 3) -> list[str]:
    items: list[str] = []
    for line in (text or "").splitlines():
        if not re.match(r"^\s*(?:[-*+]\s+|\d+[.)、]\s*)", line):
            continue
        cleaned = _clean_value(re.sub(r"^\s*(?:[-*+]\s+|\d+[.)、]\s*)", "", line), limit=88)
        if cleaned and "不构成投资建议" not in cleaned:
            items.append(cleaned)
        if len(items) >= limit:
            break
    return items


def _sentences(text: str, *, limit: int = 2) -> list[str]:
    clean = _plain(re.sub(r"^\s*(?:[-*+]\s+|\d+[.)、]\s*)", "", text or "", flags=re.MULTILINE))
    clean = re.sub(r"#{1,4}\s*", "", clean)
    pieces = re.split(r"(?<=[。！？!?])\s*", clean)
    result = [_clean_value(piece, limit=88) for piece in pieces if _clean_value(piece, limit=88)]
    return result[:limit]


def _extract_date(markdown_text: str, fallback: date) -> str:
    match = _DATE_RE.search(markdown_text or "")
    return match.group(1) if match else fallback.isoformat()


def _market_label(text: str) -> str:
    scope = _plain(text)
    for label, pattern in _MARKET_LABEL_PATTERNS:
        if pattern.search(scope):
            return label
    return ""


def _stock_heading_entry(raw_title: str) -> Optional[tuple[str, str]]:
    def _heading_name(fragment: str) -> str:
        name = _plain(fragment).strip(" -—()（）")
        return re.sub(r"\b(?:分析报告|analysis report)$", "", name, flags=re.IGNORECASE).strip()

    def _is_parenthesized(match: re.Match[str]) -> bool:
        start, end = match.span(1)
        return start > 0 and raw_title[start - 1] in "(（" and end < len(raw_title) and raw_title[end] in ")）"

    trailing_candidate: Optional[tuple[str, str]] = None
    leading_candidate: Optional[tuple[str, str]] = None
    for match in _CODE_RE.finditer(raw_title):
        code = match.group(1).upper()
        name = _heading_name(raw_title[: match.start()])
        if name:
            if _is_parenthesized(match):
                return name, code
            if leading_candidate is None:
                leading_candidate = (name, code)
            continue
        if _NUMERIC_CODE_RE.fullmatch(code):
            trailing_name = _heading_name(raw_title[match.end() :])
            if trailing_name and trailing_candidate is None:
                trailing_candidate = (trailing_name, code)
    return trailing_candidate or leading_candidate


def _stock_headings(markdown_text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for raw_title, _body, level in _extract_sections(markdown_text):
        if level > 2 or _MARKET_RE.search(raw_title) or _DASHBOARD_RE.search(raw_title):
            continue
        entry = _stock_heading_entry(raw_title)
        if entry:
            found.append(entry)
    return found


def _is_market_review_title(title: str) -> bool:
    return bool(_MARKET_RE.search(_plain(title)))


def _has_market_scope(title: str) -> bool:
    return bool(_MARKET_SCOPE_RE.search(_plain(title)))


def _market_segments(markdown_text: str) -> list[MarketSegment]:
    top_level_matches = [
        match
        for match in _HEADING_RE.finditer(markdown_text or "")
        if len(match.group(1)) == 1
    ]
    matches = [match for match in top_level_matches if _is_market_review_title(match.group(2))]
    if len(matches) < 2:
        return []
    if top_level_matches and matches[0].start() == top_level_matches[0].start():
        first_title = matches[0].group(2)
        if not _has_market_scope(first_title):
            scoped_matches = [match for match in top_level_matches if _has_market_scope(match.group(2))]
            if len(scoped_matches) >= 2:
                matches = scoped_matches

    segments: list[MarketSegment] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown_text)
        segments.append(
            MarketSegment(
                title=_plain(match.group(2)),
                markdown=markdown_text[match.start() : end].strip(),
            )
        )
    return segments


def _stock_data(markdown_text: str, generated_on: date) -> StockPoster:
    headings = _stock_headings(markdown_text)
    if headings:
        name, code = headings[0]
    else:
        first_title = next((title for title, _body, _level in _extract_sections(markdown_text)), "个股分析")
        entry = _stock_heading_entry(first_title)
        if entry:
            name, code = entry
        else:
            match = _CODE_RE.search(first_title)
            if match and match.start() == 0:
                # US ticker-only titles (and titles containing escaped HTML) read
                # better as one title than as an empty name plus a detached code.
                code = ""
                name = _plain(first_title)
            else:
                code = match.group(1).upper() if match else ""
                name = _plain(first_title[: match.start()] if match else first_title)
            name = re.sub(r"(?:分析报告|analysis report)$", "", name, flags=re.IGNORECASE).strip()

    score_match = re.search(r"(?:评分|score)\s*[:：]?\s*\*{0,2}(\d{1,3})", markdown_text, re.IGNORECASE)
    core = _section(markdown_text, "核心结论", "core conclusion", "核心判断")
    action_match = re.search(
        r"\*\*[^\w\u4e00-\u9fff]*(买入|加仓|持有|观望|减仓|卖出|回避|警戒|buy|add|hold|watch|reduce|sell|avoid|alert)\*\*",
        core or markdown_text,
        re.IGNORECASE,
    )
    trend_match = re.search(r"\*\*[^\n]+?\*\*\s*\|\s*([^\n]+)", core)
    conclusion = _labeled_value(core, "一句话决策", "One-line Decision", limit=110)
    if not conclusion:
        match = re.search(r"\*\*[^\n]+?\*\*\s*[:：]\s*(.+)", core)
        conclusion = _clean_value(match.group(1), limit=110) if match else ""

    poster = StockPoster(
        title=name or "个股分析",
        code=code,
        report_date=_extract_date(markdown_text, generated_on),
        action=_clean_value(action_match.group(1), limit=12) if action_match else "",
        score=score_match.group(1) if score_match else "",
        trend=_clean_value(trend_match.group(1), limit=16) if trend_match else "",
        conclusion=conclusion,
    )

    snapshot_section = _section(markdown_text, "市场快照", "market snapshot")
    snapshot_map: dict[str, str] = {}
    for table in _parse_tables(snapshot_section):
        if len(table.rows) == 1:
            snapshot_map.update(
                {_plain(header).lower(): _clean_value(value) for header, value in zip(table.headers, table.rows[0])}
            )
        snapshot_map.update(_table_map(table))
    current = _mapped_value(snapshot_map, "当前价", "current price", "price", "收盘价", "close")
    change = _mapped_value(snapshot_map, "涨跌幅", "change %", "change pct")
    ratio = _mapped_value(snapshot_map, "量比", "volume ratio")
    turnover = _mapped_value(snapshot_map, "换手率", "turnover rate")
    for label, value, tone in (
        ("当前/收盘", current, "primary"),
        ("涨跌幅", change, "up" if not change.startswith("-") else "down"),
        ("量比", ratio, "neutral"),
        ("换手率", turnover, "neutral"),
    ):
        if value:
            poster.snapshot.append((label, value, tone))
    poster.data_source = _mapped_value(snapshot_map, "数据源", "source")

    data_section = _section(markdown_text, "数据透视", "data view", "技术面", "technicals")
    data_map: dict[str, str] = {}
    for table in _parse_tables(data_section):
        data_map.update(_table_map(table))
    ma = _labeled_value(data_section, "均线排列", "MA Alignment", limit=42)
    volume_ratio = _labeled_value(data_section, "量能", "Volume", limit=42)
    support = _mapped_value(data_map, "支撑位", "support")
    resistance = _mapped_value(data_map, "压力位", "resistance")
    for label, value, tone in (
        ("均线", ma, "positive" if "多头" in ma.lower() or "bull" in ma.lower() else "neutral"),
        ("量能", volume_ratio, "neutral"),
        ("支撑", support, "positive"),
        ("压力", resistance, "negative"),
    ):
        if value:
            poster.technical.append((label, value, tone))

    battle = _section(markdown_text, "作战计划", "battle plan", "操作计划", "操作点位", "action levels")
    sniper_table = _find_table(battle, "理想") or _find_table(battle, "ideal")
    sniper_values: dict[str, str] = {}
    if sniper_table:
        if len(sniper_table.headers) >= 3 and len(sniper_table.rows) == 1:
            sniper_values = {
                _plain(header).lower(): _clean_value(value, limit=62)
                for header, value in zip(sniper_table.headers, sniper_table.rows[0])
            }
        else:
            sniper_values = _table_map(sniper_table)
    for labels, display, tone in (
        (("理想买入点", "ideal entry"), "理想买入", "buy"),
        (("次优买入点", "secondary entry"), "次优买入", "secondary"),
        (("止损位", "stop loss"), "止损", "stop"),
        (("目标位", "target"), "目标", "target"),
    ):
        value = _mapped_value(sniper_values, *labels)
        if value:
            poster.sniper.append((display, value, tone))

    info = _section(markdown_text, "重要信息", "key updates", "消息面", "news flow")
    poster.catalysts = _list_after_label(info, "利好催化", "positive catalysts")
    poster.risks = _list_after_label(info, "风险警报", "risk alerts")
    if not poster.risks:
        poster.risks = _section_items(_section(markdown_text, "风险提示", "risk warning", "risk alerts"), limit=2)

    position_table = _find_table(core, "持仓") or _find_table(core, "position")
    if position_table:
        position_map = _table_map(position_table)
        poster.no_position = _mapped_value(position_map, "空仓", "no position")
        poster.has_position = _mapped_value(position_map, "持仓者", "holding")
    position_section = _section(markdown_text, "持仓建议", "position advice")
    if not poster.no_position:
        poster.no_position = _labeled_value(position_section, "空仓者", "no position", limit=90)
    if not poster.has_position:
        poster.has_position = _labeled_value(position_section, "持仓者", "holding", limit=90)
    poster.position_size = _labeled_value(battle, "仓位建议", "position size", limit=68)
    poster.entry_plan = _labeled_value(battle, "建仓策略", "entry plan", limit=86)
    poster.risk_control = _labeled_value(battle, "风控策略", "risk control", limit=86)
    return poster


def _market_title(markdown_text: str) -> str:
    first_title = next((title for title, _body, _level in _extract_sections(markdown_text)), "")
    for candidate in (first_title, markdown_text[:600]):
        market = _market_label(candidate)
        if market:
            return f"{market}市场复盘"
    if _is_market_review_title(first_title):
        return first_title
    return "A股市场复盘"


def _parsed_breadth_metrics(overview: str) -> list[tuple[str, str]]:
    metrics: list[tuple[str, str]] = []
    advance_match = re.search(
        r"Advancers\s+([^/;\n]+?)\s*/\s*Decliners\s+([^/;\n]+?)(?:\s*/\s*Flat\s+([^;\n]+?))?(?=$|;|\n)",
        overview or "",
        flags=re.IGNORECASE,
    )
    if advance_match:
        metrics.extend(
            [
                ("上涨", _clean_value(advance_match.group(1), limit=32)),
                ("下跌", _clean_value(advance_match.group(2), limit=32)),
            ]
        )

    limit_match = re.search(
        r"Limit(?:-|\s)?up\s+([^/;\n]+?)\s*/\s*Limit(?:-|\s)?down\s+([^;\n]+?)(?=$|;|\n)",
        overview or "",
        flags=re.IGNORECASE,
    )
    if limit_match:
        metrics.extend(
            [
                ("涨停", _clean_value(limit_match.group(1), limit=32)),
                ("跌停", _clean_value(limit_match.group(2), limit=32)),
            ]
        )

    turnover_match = re.search(
        r"Turnover\s+(.+?)(?=$|;|\n)",
        overview or "",
        flags=re.IGNORECASE,
    )
    if turnover_match:
        metrics.append(("成交额", _clean_value(turnover_match.group(1), limit=48)))
    return [(label, value) for label, value in metrics if value]


def _market_data(markdown_text: str, generated_on: date) -> MarketPoster:
    overview = _section(markdown_text, "盘面总览", "market summary", "breadth & liquidity")
    score_match = re.search(r"(?:盘面信号|市场信号|market signal)\*{0,2}\s*[:：]\s*(\d{1,3})/100(?:\s*[（(]([^，,)]+)[，,]\s*([^）)]+)[）)])?", markdown_text, re.IGNORECASE)
    quote = _QUOTE_RE.search(markdown_text)
    poster = MarketPoster(
        title=_market_title(markdown_text),
        report_date=_extract_date(markdown_text, generated_on),
        summary=_clean_value(quote.group(1), limit=100) if quote else "",
        score=score_match.group(1) if score_match else "",
        temperature=_clean_value(score_match.group(2), limit=12) if score_match and score_match.group(2) else "",
        signal=_clean_value(score_match.group(3), limit=12) if score_match and score_match.group(3) else "",
        guidance=_labeled_value(overview, "操作建议", "Guidance", limit=100),
    )
    reason_text = _labeled_value(overview, "信号依据", "Drivers", limit=220)
    poster.reasons = [
        _clean_value(item, limit=72)
        for item in re.split(r"[；;]", reason_text)
        if _clean_value(item, limit=72)
    ][:3]
    if not poster.reasons and poster.summary:
        poster.reasons = _sentences(poster.summary, limit=2)

    index_section = _section(markdown_text, "指数结构", "major indices", "index commentary")
    index_table = _find_table(index_section, "指数", "涨跌幅") or _find_table(index_section, "index", "change")
    positive_color = "green"
    if index_table:
        headers = [header.lower() for header in index_table.headers]
        name_i = next((i for i, value in enumerate(headers) if "指数" in value or "index" in value), 0)
        current_i = next((i for i, value in enumerate(headers) if "最新" in value or "last" in value), 1)
        change_i = next((i for i, value in enumerate(headers) if "涨跌幅" in value or "change" in value), 2)
        for row_index, row in enumerate(index_table.rows[:3]):
            if len(row) > max(name_i, current_i, change_i):
                raw_change = (
                    index_table.raw_rows[row_index][change_i]
                    if row_index < len(index_table.raw_rows)
                    and len(index_table.raw_rows[row_index]) > change_i
                    else row[change_i]
                )
                color = "green" if "🟢" in raw_change else "red" if "🔴" in raw_change else ""
                if not color:
                    color = "red" if row[change_i].strip().startswith("-") else "green"
                if not row[change_i].strip().startswith("-"):
                    positive_color = color
                poster.indices.append((row[name_i], row[current_i], row[change_i], color))

    breadth_table = _find_table(overview, "上涨", "成交额") or _find_table(overview, "breadth")
    if breadth_table:
        mapping = _table_map(breadth_table)
        advance = _mapped_value(mapping, "上涨/下跌", "advancers")
        limits = _mapped_value(mapping, "涨停/跌停", "limit-up")
        amount = _mapped_value(mapping, "成交额", "turnover")
        if advance:
            parts = [part.strip() for part in advance.split("/")]
            if parts:
                poster.breadth.append(("上涨", parts[0], positive_color))
            if len(parts) > 1:
                negative_color = "red" if positive_color == "green" else "green"
                poster.breadth.append(("下跌", parts[1], negative_color))
        if limits:
            parts = [part.strip() for part in limits.split("/")]
            if parts:
                poster.breadth.append(("涨停", parts[0], positive_color))
            if len(parts) > 1:
                negative_color = "red" if positive_color == "green" else "green"
                poster.breadth.append(("跌停", parts[1], negative_color))
        if amount:
            poster.breadth.append(("成交额", amount, "primary"))
    if not poster.breadth:
        for label, value in _parsed_breadth_metrics(overview):
            if label == "上涨":
                tone = positive_color
            elif label in {"下跌", "跌停"}:
                tone = "red" if positive_color == "green" else "green"
            elif label == "涨停":
                tone = positive_color
            else:
                tone = "primary"
            poster.breadth.append((label, value, tone))

    sector_section = _section(markdown_text, "板块主线", "sector highlights")
    sector_table = _find_table(sector_section, "板块", "涨跌幅") or _find_table(sector_section, "sector", "change")
    if sector_table:
        for row in sector_table.rows[:3]:
            if len(row) >= 3:
                poster.sectors.append((_clean_value(row[-2], limit=20), _clean_value(row[-1], limit=12)))

    catalyst_section = _section(markdown_text, "消息催化", "news catalysts")
    poster.catalysts = _section_items(catalyst_section, limit=2) or _sentences(catalyst_section, limit=2)
    plan_section = _section(markdown_text, "明日交易计划", "strategy plan", "outlook")
    for label in ("结论", "仓位区间", "关注方向", "回避方向", "触发失效条件"):
        value = _labeled_value(plan_section, label, limit=86)
        if value:
            poster.plan.append(f"{label}：{value}")
        if len(poster.plan) >= 3:
            break
    if not poster.plan:
        poster.plan = _section_items(plan_section, limit=3) or _sentences(plan_section, limit=3)
    poster.risks = _section_items(_section(markdown_text, "风险提示", "risk alerts"), limit=3)
    return poster


def _tone_for_action(action: str) -> str:
    normalized = (action or "").lower()
    if any(term in normalized for term in ("买", "加仓", "buy", "add")):
        return "positive"
    if any(term in normalized for term in ("卖", "减仓", "回避", "sell", "reduce", "avoid")):
        return "negative"
    return "primary"


def _metric_cards(items: Iterable[tuple[str, str, str]], class_name: str = "") -> str:
    cards = []
    for label, value, tone in items:
        cards.append(
            f'<div class="metric {class_name} {_escape(tone)}"><span>{_escape(label)}</span><strong>{_escape(value)}</strong></div>'
        )
    return "".join(cards)


def _list_html(items: Iterable[str], empty: str = "") -> str:
    values = [value for value in items if value]
    if not values:
        return f'<p class="muted">{_escape(empty)}</p>' if empty else ""
    return "<ul>" + "".join(f"<li>{_escape(value)}</li>" for value in values) + "</ul>"


def _section_html(title: str, icon: str, content: str, class_name: str = "") -> str:
    if not content:
        return ""
    return f'<section class="poster-section {class_name}"><h2><b>{_escape(icon)}</b>{_escape(title)}</h2>{content}</section>'


def _render_markdown_fragment(markdown_text: str) -> str:
    return markdown2.markdown(
        markdown_text,
        extras=["tables", "fenced-code-blocks", "break-on-newline", "cuddled-lists"],
        safe_mode="escape",
    )


def _stock_body(data: StockPoster, fallback_html: str) -> str:
    tone = _tone_for_action(data.action)
    score = f'<div class="signal-score"><span>评分</span><strong>{_escape(data.score)}</strong><small>/100</small></div>' if data.score else ""
    trend = f'<div class="signal-trend"><span>趋势</span><strong>{_escape(data.trend)}</strong></div>' if data.trend else ""
    action = f'<div class="action-chip {tone}">{_escape(data.action)}</div>' if data.action else ""
    signal_row = f'<div class="signal-row">{action}{score}{trend}</div>' if action or score or trend else ""
    conclusion = _section_html("核心结论", "◎", f'<div class="conclusion">{_escape(data.conclusion)}</div>') if data.conclusion else ""
    snapshot = _section_html("市场快照", "▥", f'<div class="metric-grid snapshot-grid">{_metric_cards(data.snapshot)}</div>') if data.snapshot else ""
    sniper = _section_html("执行计划", "◎", f'<div class="metric-grid sniper-grid sniper-table">{_metric_cards(data.sniper, "sniper")}</div>') if data.sniper else ""
    technical = _section_html("技术参考", "⌁", f'<div class="metric-grid technical-grid">{_metric_cards(data.technical)}</div>') if data.technical else ""
    insight_cards = ""
    if data.catalysts:
        insight_cards += f'<div class="insight positive"><h3>利好催化</h3>{_list_html(data.catalysts)}</div>'
    if data.risks:
        insight_cards += f'<div class="insight negative"><h3>风险警报</h3>{_list_html(data.risks)}</div>'
    insights = _section_html("催化与风险", "!", f'<div class="two-column">{insight_cards}</div>') if insight_cards else ""
    position_rows = ""
    for label, value, tone_name in (
        ("未持仓", data.no_position, "primary"),
        ("已持仓", data.has_position, "warning"),
        ("仓位", data.position_size, "positive"),
    ):
        if value:
            position_rows += f'<div class="position-row"><span class="pill {tone_name}">{label}</span><p>{_escape(value)}</p></div>'
    if data.entry_plan:
        position_rows += f'<div class="position-row"><span class="pill primary">建仓</span><p>{_escape(data.entry_plan)}</p></div>'
    if data.risk_control:
        position_rows += f'<div class="position-row"><span class="pill negative">风控</span><p>{_escape(data.risk_control)}</p></div>'
    positions = _section_html("持仓建议", "▣", f'<div class="position-box">{position_rows}</div>') if position_rows else ""
    structured = any((signal_row, conclusion, snapshot, sniper, technical, insights, positions))
    fallback = f'<section class="report-fallback"><article class="report-content">{fallback_html}</article></section>' if not structured else ""
    return f"{signal_row}{conclusion}{snapshot}{sniper}{technical}{insights}{positions}{fallback}"


def _market_body(data: MarketPoster, fallback_html: str) -> str:
    signal = ""
    if data.score:
        signal = (
            '<section class="market-signal">'
            '<div class="signal-main"><span>市场信号</span>'
            f'<strong>{_escape(data.score)}</strong><small>/100</small></div>'
            f'<div class="market-label">{_escape(data.signal or data.temperature)}</div>'
            f'<div class="signal-reasons"><span>信号依据</span>{_list_html(data.reasons)}</div>'
            f'<p class="signal-guidance">{_escape(data.guidance or data.summary)}</p>'
            '</section>'
        )
    indices = ""
    if data.indices:
        cards = []
        for name, current, change, color in data.indices:
            cards.append(f'<div class="index-card"><span>{_escape(name)}</span><strong class="{color}">{_escape(change)}</strong><small>{_escape(current)}</small></div>')
        indices = f'<div class="index-grid">{"".join(cards)}</div>'
    breadth = _section_html("市场宽度", "↕", f'<div class="metric-grid breadth-grid">{_metric_cards(data.breadth)}</div>') if data.breadth else ""
    sector_rows = "".join(
        f'<div class="ranking-row"><b>{index:02d}</b><span>{_escape(name)}</span><strong>{_escape(change)}</strong></div>'
        for index, (name, change) in enumerate(data.sectors, 1)
    )
    sectors = _section_html("强势板块", "◆", f'<div class="ranking">{sector_rows}</div>') if sector_rows else ""
    catalysts = _section_html("消息催化", "▤", _list_html(data.catalysts)) if data.catalysts else ""
    plan = _section_html("明日计划", "✓", _list_html(data.plan)) if data.plan else ""
    dual = (
        f'<div class="market-two-column"><div class="market-left">{sectors}</div>'
        f'<div class="market-right">{catalysts}{plan}</div></div>'
        if sectors or catalysts or plan else ""
    )
    risks = _section_html("风险提示", "!", _list_html(data.risks), "risk-strip") if data.risks else ""
    structured = any((signal, indices, breadth, dual, risks))
    fallback = f'<section class="report-fallback"><article class="report-content">{fallback_html}</article></section>' if not structured else ""
    return f"{signal}{indices}{breadth}{dual}{risks}{fallback}"


def _generic_body(report_html: str) -> str:
    return f'<section class="report-fallback"><article class="report-content">{report_html}</article></section>'


def _multi_market_body(segments: list[MarketSegment], generated_on: date) -> str:
    blocks: list[str] = []
    for segment in segments:
        body_markdown = _HEADING_RE.sub("", segment.markdown, count=1).strip()
        fallback_html = _render_markdown_fragment(body_markdown)
        data = _market_data(segment.markdown, generated_on)
        title = data.title or segment.title
        blocks.append(
            f'<section class="poster-section market-region-title"><h2><b>◎</b>{_escape(title)}</h2></section>'
            f"{_market_body(data, fallback_html)}"
        )
    return "".join(blocks)


def _footer(project_qr: str, xiaohongshu_qr: str, source_line: str) -> str:
    return f"""
    <footer class="poster-footer">
      <div class="footer-brand"><strong>DSA</strong><span>AI 股票分析</span><small>开源股票智能分析系统</small><small class="project-url">{_escape(PROJECT_URL)}</small></div>
      <div class="qr-card"><div class="qr-frame"><img src="{project_qr}" alt="项目主页二维码"></div><span>GitHub 项目</span></div>
      <div class="qr-card"><div class="qr-frame"><img src="{xiaohongshu_qr}" alt="小红书二维码"></div><span>小红书</span></div>
    </footer>
    <div class="disclaimer">AI 生成，仅供研究交流，不构成投资建议。市场有风险，决策需谨慎。{_escape(source_line)}</div>
    """


def build_share_image_html(markdown_text: str, *, generated_on: Optional[date] = None) -> str:
    """Build a deterministic 1080px stock, market, or dashboard share poster.

    Data is populated from the stable Markdown emitted by ``NotificationService``
    and ``MarketAnalyzer``.  Unknown or unavailable fields are omitted.  Both QR
    codes are embedded as data URIs so rendering never depends on network access.
    """

    generated = generated_on or date.today()
    headings = _extract_sections(markdown_text)
    first_title = headings[0][0] if headings else "Daily Stock Analysis"
    stock_headings = _stock_headings(markdown_text)
    market_segments = _market_segments(markdown_text)
    candidate_market_titles = headings[:2]
    is_market = any(
        level <= 2 and _is_market_review_title(title)
        for title, _body, level in candidate_market_titles
    )
    is_single_stock = len(stock_headings) == 1
    report_kind = "market" if is_market else "stock" if is_single_stock else "dashboard"

    body_markdown = _HEADING_RE.sub("", markdown_text, count=1).strip()
    fallback_html = _render_markdown_fragment(body_markdown)
    stamp = _extract_date(markdown_text, generated)
    source_line = ""
    if report_kind == "market":
        if market_segments:
            title = "多市场复盘"
            subtitle = "按市场分段展示指数、主线与风险边界"
            content = _multi_market_body(market_segments, generated)
        else:
            data = _market_data(markdown_text, generated)
            title = data.title
            subtitle = data.summary or "指数、宽度、主线与风险的收盘复盘"
            content = _market_body(data, fallback_html)
    elif report_kind == "stock":
        data = _stock_data(markdown_text, generated)
        title = data.title
        subtitle = "个股决策卡 · 结论、点位与风险一图读懂"
        content = _stock_body(data, fallback_html)
        source_line = f" 数据源：{data.data_source}。" if data.data_source else ""
    else:
        title = first_title
        subtitle = "多股决策摘要"
        content = _generic_body(fallback_html)

    project_qr = _asset_data_uri("project_qr.png", "image/png")
    xiaohongshu_qr = _asset_data_uri("xiaohongshu_qr.png", "image/png")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=1080, initial-scale=1">
  <title>{_escape(title)}</title>
  <style>
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; width: 1080px; background: #eef4fd; }}
    body {{ color: #081b40; font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "PingFang SC", "Microsoft YaHei", Arial, sans-serif; font-size: 22px; line-height: 1.5; -webkit-font-smoothing: antialiased; }}
    .poster {{ width: 1080px; padding: 38px 34px 24px; border: 1px solid #aebdd4; border-radius: 28px; background: radial-gradient(circle at 92% 6%, rgba(48,123,255,.15), transparent 260px), linear-gradient(180deg,#fff 0%,#fbfdff 78%,#eef5ff 100%); }}
    .poster-header {{ display: table; width: 100%; margin-bottom: 28px; }}
    .brand, .meta {{ display: table-cell; vertical-align: middle; }}
    .brand {{ font-size: 26px; font-weight: 650; }} .brand strong {{ margin: 0 14px 0 13px; font-size: 43px; letter-spacing: -2px; }} .brand em {{ color: #8b9bb3; font-style: normal; }}
    .brand-mark {{ display: inline-block; width: 39px; height: 40px; vertical-align: middle; white-space: nowrap; }} .brand-mark i {{ display:inline-block; width:8px; margin-right:4px; border-radius:5px 5px 2px 2px; vertical-align:bottom; }} .brand-mark i:nth-child(1){{height:18px;background:#ff3b30}} .brand-mark i:nth-child(2){{height:28px;background:#00a86b}} .brand-mark i:nth-child(3){{height:40px;margin:0;background:#1677ff}}
    .meta {{ text-align:right; color:#3e506c; font-size:21px; }} .date-chip {{ display:inline-block; padding:10px 17px; border:1px solid #aec4e7; border-radius:16px; background:rgba(255,255,255,.85); }}
    .hero {{ min-height: 145px; margin-bottom: 24px; padding: 10px 10px 20px; }} .hero h1 {{ margin:0 0 8px; max-width:820px; font-size:68px; line-height:1.15; letter-spacing:-3px; }} .hero .code {{ margin-left:18px; color:#1768e8; font-size:38px; letter-spacing:0; white-space:nowrap; }} .hero p {{ margin:0; max-width:810px; color:#3c4f70; font-size:24px; }}
    .signal-row {{ display:table; width:100%; margin:0 0 26px; border-spacing:14px 0; table-layout:fixed; }} .signal-row>div {{ display:table-cell; height:88px; padding:14px 20px; border:1px solid #cad8ec; border-radius:16px; vertical-align:middle; background:rgba(255,255,255,.92); }} .signal-row .action-chip {{ width:24%; color:#fff; text-align:center; font-size:38px; font-weight:850; background:#1974ed; box-shadow:0 10px 24px rgba(25,116,237,.22); }} .signal-row .action-chip.positive{{background:linear-gradient(135deg,#118a55,#19b66f)}} .signal-row .action-chip.negative{{background:linear-gradient(135deg,#e63b45,#ff5a52)}} .signal-score span,.signal-trend span{{margin-right:14px;font-weight:750}} .signal-score strong{{color:#0da15d;font-size:41px}} .signal-score small{{color:#53627b;font-size:20px}} .signal-trend strong{{color:#0a9c58;font-size:30px}}
    .poster-section {{ margin:0 10px 25px; }} .poster-section h2 {{ margin:0 0 12px; font-size:29px; line-height:1.3; }} .poster-section h2 b {{ display:inline-block; width:34px; color:#176ff2; font-family:Arial,sans-serif; }}
    .conclusion {{ padding:16px 24px; border:1.5px solid #72a8ff; border-radius:14px; color:#13294e; background:linear-gradient(90deg,#f9fcff,#eff6ff); font-size:25px; font-weight:600; }}
    .metric-grid {{ display:table; width:100%; border-spacing:12px 0; table-layout:fixed; }} .metric {{ display:table-cell; height:112px; padding:14px 12px; border:1px solid #d0dced; border-radius:16px; text-align:center; vertical-align:middle; background:rgba(255,255,255,.92); }} .metric span {{ display:block; margin-bottom:5px; color:#233653; font-weight:700; }} .metric strong {{ display:block; color:#10254b; font-size:31px; line-height:1.25; overflow-wrap:anywhere; }} .metric.primary strong{{color:#1768e8}} .metric.up strong,.metric.positive strong,.metric.buy strong,.metric.green strong{{color:#0a9c58}} .metric.down strong,.metric.negative strong,.metric.stop strong,.metric.red strong{{color:#ed343d}} .metric.hot strong{{color:#ff4a36}} .metric.secondary strong{{color:#1768e8}} .metric.target strong{{color:#ff8a00}} .sniper-grid .metric{{height:128px}} .sniper-grid .metric strong{{font-size:23px}} .technical-grid .metric strong{{font-size:22px}}
    .two-column {{ display:table; width:100%; border-spacing:12px 0; table-layout:fixed; }} .insight {{ display:table-cell; width:50%; padding:15px 20px; border:1px solid #d5e1f0; border-radius:15px; background:#fff; vertical-align:top; }} .insight.positive{{background:#f4fcf7}} .insight.negative{{background:#fff7f7}} .insight h3{{margin:0 0 6px;color:#0a9c58;font-size:23px}} .insight.negative h3{{color:#ed343d}} ul{{margin:4px 0;padding-left:25px}} li{{margin:5px 0}}
    .position-box {{ overflow:hidden; border:1px solid #d5e1f0; border-radius:15px; background:#fff; }} .position-row {{ display:table; width:100%; padding:10px 18px; border-bottom:1px solid #e5ecf5; }} .position-row:last-child{{border:0}} .position-row .pill,.position-row p{{display:table-cell;vertical-align:middle}} .position-row .pill{{width:92px;padding:5px 10px;border-radius:8px;color:#fff;text-align:center;font-size:18px;font-weight:750;background:#357dea}} .position-row .pill.warning{{background:#f2a20c}} .position-row .pill.positive{{background:#13a365}} .position-row .pill.negative{{background:#eb3e47}} .position-row p{{margin:0;padding-left:16px}}
    .market-signal {{ display:table; position:relative; width:calc(100% - 20px); min-height:190px; margin:0 10px 24px; padding:18px 27px 52px; border:1px solid #d0dced; border-radius:20px; background:rgba(255,255,255,.94); box-shadow:0 10px 32px rgba(18,71,153,.07); table-layout:fixed; }} .signal-main,.market-label,.signal-reasons{{display:table-cell;vertical-align:middle}} .signal-main{{width:28%}} .market-signal span{{display:block;font-weight:750}} .market-signal strong{{color:#1768e8;font-size:82px;line-height:1.15}} .market-signal small{{font-size:34px}} .market-label{{width:18%;padding:8px 13px;border:1px solid #23ad69;border-radius:9px;color:#0d9958;text-align:center;font-weight:750;background:#f1fff7}} .signal-reasons{{width:54%;padding-left:28px}} .signal-reasons ul{{margin-top:7px;font-size:19px}} .signal-guidance{{position:absolute;left:27px;right:27px;bottom:14px;margin:0;color:#435572;font-size:20px}}
    .index-grid {{ display:table; width:100%; margin:0 0 24px; border-spacing:12px 0; table-layout:fixed; }} .index-card{{display:table-cell;padding:16px 22px;border:1px solid #d0dced;border-radius:17px;background:#fff}} .index-card span,.index-card small{{display:block}} .index-card span{{font-weight:750}} .index-card strong{{display:block;margin:8px 0 0;font-size:36px}} .index-card strong.red{{color:#ed3f36}} .index-card strong.green{{color:#0a9c58}} .index-card small{{color:#3d506f;font-size:20px}}
    .breadth-grid .metric strong{{font-size:29px}} .market-two-column{{display:table;width:calc(100% - 20px);margin:0 10px 24px;border-spacing:7px 0;table-layout:fixed}} .market-left,.market-right{{display:table-cell;width:50%;vertical-align:top}} .market-two-column .poster-section{{margin:0 0 14px;padding:18px 20px;border:1px solid #d3dfef;border-radius:18px;background:#fff}} .ranking-row{{display:table;width:100%;padding:11px 0;border-bottom:1px solid #e6edf6}} .ranking-row:last-child{{border:0}} .ranking-row>*{{display:table-cell;vertical-align:middle}} .ranking-row b{{width:44px;color:#fff;border-radius:9px;text-align:center;background:#1677ff}} .ranking-row span{{padding-left:13px}} .ranking-row strong{{text-align:right;color:#ed3f36}}
    .risk-strip{{padding:14px 20px;border:1px solid #ffc5c5;border-radius:16px;background:#fff6f6}} .risk-strip h2{{color:#e7373f}} .risk-strip ul{{display:table;width:100%;padding-left:25px}} .risk-strip li{{display:table-cell;width:33%;padding-right:20px}}
    .report-fallback {{ margin:0 10px 26px; padding:24px 28px; border:1px solid #d5e1f0; border-radius:18px; background:#fff; }} .report-content h1,.report-content h2,.report-content h3{{color:#153d78}} .report-content h2{{font-size:29px}} .report-content h3{{font-size:25px}} .report-content table{{width:100%;border-collapse:collapse;font-size:19px}} .report-content th,.report-content td{{padding:10px;border:1px solid #dbe4f1}} .report-content th{{background:#eef4fc}} .report-content blockquote{{margin:15px 0;padding:12px 18px;border-left:5px solid #4385ef;background:#f3f7fd}}
    .poster-footer {{ display:table; width:100%; margin-top:20px; padding:20px 34px 8px; border-top:1px solid #ccdaec; table-layout:fixed; }} .footer-brand,.qr-card{{display:table-cell;vertical-align:middle}} .footer-brand{{width:50%}} .footer-brand strong,.footer-brand span,.footer-brand small{{display:block}} .footer-brand strong{{color:#1768e8;font-size:52px;font-style:italic}} .footer-brand span{{font-size:29px;font-weight:800}} .footer-brand small{{color:#536683}} .footer-brand .project-url{{margin-top:5px;color:#8795aa;font-size:12px}} .qr-card{{width:25%;text-align:center;font-weight:750}} .qr-frame{{width:172px;height:172px;margin:0 auto 5px;padding:6px;border:1px solid #d3deed;border-radius:14px;background:#fff}} .qr-frame img{{display:block;width:160px;height:160px;object-fit:contain;image-rendering:pixelated}} .disclaimer{{margin:8px -34px -24px;padding:10px 34px;color:#285b9d;font-size:15px;text-align:center;background:#eaf3ff}}
  </style>
</head>
<body>
  <main class="poster {report_kind}">
    <header class="poster-header"><div class="brand"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span><strong>DSA</strong><em>|</em> AI 股票分析</div><div class="meta"><span class="date-chip">{_escape(stamp)}</span></div></header>
    <section class="hero"><h1>{_escape(title)}{f'<span class="code">{_escape(data.code)}</span>' if report_kind == 'stock' and data.code else ''}</h1><p>{_escape(subtitle)}</p></section>
    {content}
    {_footer(project_qr, xiaohongshu_qr, source_line)}
  </main>
</body>
</html>"""


__all__ = ["PROJECT_URL", "XIAOHONGSHU_URL", "build_share_image_html"]
