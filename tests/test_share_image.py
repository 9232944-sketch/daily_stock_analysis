# -*- coding: utf-8 -*-

from datetime import date
from pathlib import Path

from src.share_image import PROJECT_URL, build_share_image_html


def test_stock_share_image_has_brand_content_and_two_embedded_qr_codes():
    html = build_share_image_html(
        "# 贵州茅台 600519 分析报告\n\n## 核心判断\n\n- 趋势偏多\n",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster stock"' in html
    assert "个股决策卡" in html
    assert "贵州茅台" in html
    assert '<span class="code">600519</span>' in html
    assert html.count('class="qr-frame"') == 2
    assert "data:image/png;base64," in html
    assert html.count("data:image/png;base64,") == 2
    assert "项目主页二维码" in html
    assert "小红书二维码" in html
    assert PROJECT_URL in html
    assert "2026-07-31" in html
    assert html.count("<h1>") == 1


def test_market_share_image_uses_market_variant_and_preserves_tables():
    html = build_share_image_html(
        "# A 股大盘复盘\n\n## 指数表现\n\n| 指数 | 涨跌 |\n| --- | --- |\n| 上证 | +0.8% |",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster market"' in html
    assert "市场复盘" in html
    assert "<table>" in html
    assert "上证" in html
    assert "+0.8%" in html


def test_market_share_image_populates_decision_modules_from_report_contract():
    html = build_share_image_html(
        """# 🎯 大盘复盘

## 2026-07-31 大盘复盘

> 今日A股温和上行，但仍需观察成交额能否延续。

### 一、盘面总览

- **盘面信号**：66/100（偏暖，可进攻）
- **操作建议**：关注主线延续，避免追高。

| 指标 | 数值 | 观察 |
| --- | --- | --- |
| 上涨/下跌/平盘 | 3298 / 1687 / 70 | 扩散 |
| 涨停/跌停 | 72 / 6 | 正向 |
| 两市成交额 | 1.12 万亿 | 活跃 |

### 二、指数结构

| 指数 | 最新 | 涨跌幅 |
| --- | --- | --- |
| 上证指数 | 3185.53 | +0.80% |
| 深证成指 | 9732.28 | +1.12% |
| 创业板指 | 1875.90 | +0.65% |

### 三、板块主线

#### 领涨板块 Top 3

| 排名 | 板块 | 涨跌幅 |
| --- | --- | --- |
| 1 | 半导体 | +3.2% |
| 2 | 消费电子 | +2.6% |
| 3 | 机器人 | +2.1% |

### 五、消息催化

- 国产算力产业链活跃。

### 六、明日交易计划

**结论：建设性偏多。**
**仓位区间：** 5-7成。
**关注方向：** 权重板块承接。

### 七、风险提示

1. 高位板块回撤。
""",
        generated_on=date(2026, 7, 31),
    )

    assert '<section class="market-signal">' in html
    assert '<strong>66</strong><small>/100</small>' in html
    assert "上证指数" in html
    assert "3298" in html
    assert "半导体" in html
    assert "建设性偏多" in html
    assert "高位板块回撤" in html


def test_market_share_image_preserves_report_color_scheme_from_index_markers():
    html = build_share_image_html(
        """# 大盘复盘

### 一、盘面总览

- **盘面信号**：60/100（偏暖，可进攻）

| 指标 | 数值 |
| --- | --- |
| 上涨/下跌/平盘 | 3000 / 1800 / 20 |
| 涨停/跌停 | 60 / 8 |
| 两市成交额 | 10000 亿 |

### 二、指数结构

| 指数 | 最新 | 涨跌幅 |
| --- | --- | --- |
| 上证指数 | 3200 | 🔴 +0.80% |
""",
        generated_on=date(2026, 7, 31),
    )

    assert '<strong class="red">+0.80%</strong>' in html
    assert 'class="metric  red"><span>上涨</span>' in html


def test_real_single_stock_shape_uses_h2_title_score_and_sniper_contract():
    html = build_share_image_html(
        """## 🟢 贵州茅台 (600519)

> 2026-07-31 15:30 | 评分: **72** | 看多

### 📌 核心结论

**买入**: 回调到支撑区可分批关注。

### 🎯 操作点位

| 操作点位 | 当前价格 |
| --- | --- |
| 🎯 理想买入点 | 1420-1450 |
| 🔵 次优买入点 | 1380-1400 |
| 🛑 止损位 | 1350 |
| 🎊 目标位 | 1580 |
""",
        generated_on=date(2026, 7, 31),
    )

    assert "贵州茅台" in html
    assert '<span class="code">600519</span>' in html
    assert "个股决策卡" in html
    assert '<strong>72</strong><small>/100</small>' in html
    assert "回调到支撑区可分批关注" in html
    assert "综合评分" not in html
    assert "多空趋势" not in html
    assert "sniper-table" in html
    assert 'class="metric sniper buy"' in html
    assert 'class="metric sniper stop"' in html
    assert 'class="metric sniper target"' in html


def test_stock_share_image_reads_notification_service_chinese_market_snapshot_heading():
    html = build_share_image_html(
        """# 贵州茅台 600519 分析报告

## 核心结论

**买入**：回调到支撑区可分批关注。

### 当日行情

| 当前价 | 涨跌幅 | 量比 | 换手率 | 行情来源 |
| --- | --- | --- | --- | --- |
| 1425.00 | +1.20% | 1.35 | 0.82% | 腾讯财经 |
""",
        generated_on=date(2026, 7, 31),
    )

    assert "市场快照" in html
    assert "1425.00" in html
    assert "+1.20%" in html
    assert "1.35" in html
    assert "0.82%" in html
    assert "数据源：腾讯财经" in html


def test_share_image_escapes_title_but_keeps_markdown_body_markup():
    html = build_share_image_html(
        "# AAPL <script>alert(1)</script>\n\n**结论**：关注。",
        generated_on=date(2026, 7, 31),
    )

    assert "AAPL alert(1)" in html
    assert "<script>" not in html
    assert "<strong>结论</strong>" in html


def test_english_company_name_is_not_mistaken_for_a_ticker():
    html = build_share_image_html(
        "## Apple Inc. (AAPL)\n\n> 2026-07-31 | Score: **70** | Bullish",
        generated_on=date(2026, 7, 31),
    )

    assert "Apple Inc." in html
    assert '<span class="code">AAPL</span>' in html


def test_dotted_us_ticker_is_preserved_in_stock_heading():
    html = build_share_image_html(
        "## Berkshire Hathaway (BRK.B)\n\n> 2026-07-31 | Score: **70** | Bullish",
        generated_on=date(2026, 7, 31),
    )

    assert "Berkshire Hathaway" in html
    assert '<span class="code">BRK.B</span>' in html


def test_korean_market_review_heading_uses_market_poster():
    html = build_share_image_html(
        "# 미국 시황 리뷰\n\n## 지수 구조\n\n| 지수 | 최신 | 涨跌幅 |\n| --- | --- | --- |\n| S&P 500 | 6200 | +0.8% |",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster market"' in html
    assert "多股决策摘要" not in html
    assert "美股市场复盘" in html


def test_korean_multi_market_review_skips_root_wrapper_segment():
    html = build_share_image_html(
        """# 🎯 시황 리뷰

> 여러 시장 마감 요약.

# 미국 시황 리뷰

## 2026-07-31 미국 시황 리뷰

### 1. 시장 요약

- **시장 신호**: 66/100 (건설적, 위험 선호)

### 2. 주요 지수

| 지수 | 최신 | 등락률 |
| --- | --- | --- |
| S&P 500 | 6200 | +0.8% |

> 다음 시장 시황 리뷰

# 홍콩 시황 리뷰

## 2026-07-31 홍콩 시황 리뷰

### 1. 시장 요약

- **시장 신호**: 58/100 (중립, 선별)

### 2. 주요 지수

| 지수 | 최신 | 등락률 |
| --- | --- | --- |
| Hang Seng | 18200 | +1.2% |
""",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster market"' in html
    assert "多市场复盘" in html
    assert "美股市场复盘" in html
    assert "港股市场复盘" in html
    assert "여러 시장 마감 요약" not in html


def test_stock_report_market_snapshot_does_not_route_to_market_poster():
    html = build_share_image_html(
        """# Apple Inc. (AAPL)

## Core Conclusion

**Buy**: Pullbacks into support remain actionable.

## Market Snapshot

| Current Price | Change % | Volume Ratio | Source |
| --- | --- | --- | --- |
| 210.15 | +1.5% | 1.2x | IEX |

## Action Levels

| Ideal Entry | Secondary Entry | Stop Loss | Target |
| --- | --- | --- | --- |
| 205-207 | 202-204 | 198 | 220 |

## Risk Alerts

- A failed earnings guide can break momentum.
""",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster stock"' in html
    assert "个股决策卡" in html
    assert "Apple Inc." in html
    assert "理想买入" in html
    assert "A failed earnings guide can break momentum." in html


def test_multi_market_review_keeps_every_region_in_share_image():
    html = build_share_image_html(
        """# A股大盘复盘

## 2026-07-31 A股大盘复盘

> 今日A股情绪修复。

### 一、盘面总览

- **盘面信号**：66/100（偏暖，可进攻）

| 指标 | 数值 |
| --- | --- |
| 上涨/下跌 | 3200 / 1500 |

### 二、指数结构

| 指数 | 最新 | 涨跌幅 |
| --- | --- | --- |
| 上证指数 | 3200 | +0.80% |

---

> 以下为下一市场大盘复盘

# 港股大盘复盘

## 2026-07-31 港股大盘复盘

> 今日港股科技反弹。

### 一、盘面总览

- **盘面信号**：61/100（偏暖，可进攻）

| 指标 | 数值 |
| --- | --- |
| 上涨/下跌 | 900 / 700 |

### 二、指数结构

| 指数 | 最新 | 涨跌幅 |
| --- | --- | --- |
| 恒生指数 | 18200 | +1.20% |
""",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster market"' in html
    assert "多市场复盘" in html
    assert "A股市场复盘" in html
    assert "港股市场复盘" in html
    assert "上证指数" in html
    assert "恒生指数" in html


def test_multi_market_review_ignores_root_wrapper_title_when_splitting_regions():
    html = build_share_image_html(
        """# 🎯 大盘复盘

> 汇总多个市场的收盘观察。

# A股大盘复盘

## 2026-07-31 A股大盘复盘

> 今日A股情绪修复。

### 一、盘面总览

- **盘面信号**：66/100（偏暖，可进攻）

| 指标 | 数值 |
| --- | --- |
| 上涨/下跌 | 3200 / 1500 |

### 二、指数结构

| 指数 | 最新 | 涨跌幅 |
| --- | --- | --- |
| 上证指数 | 3200 | +0.80% |

---

> 以下为下一市场大盘复盘

# 港股大盘复盘

## 2026-07-31 港股大盘复盘

> 今日港股科技反弹。

### 一、盘面总览

- **盘面信号**：61/100（偏暖，可进攻）

| 指标 | 数值 |
| --- | --- |
| 上涨/下跌 | 900 / 700 |

### 二、指数结构

| 指数 | 最新 | 涨跌幅 |
| --- | --- | --- |
| 恒生指数 | 18200 | +1.20% |
""",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster market"' in html
    assert html.count("A股市场复盘") == 1
    assert html.count("港股市场复盘") == 1
    assert "汇总多个市场的收盘观察" not in html
    assert "上证指数" in html
    assert "恒生指数" in html


def test_english_multi_market_review_maps_region_titles_from_headings():
    html = build_share_image_html(
        """# US Market Recap

## 2026-07-31 US Market Recap

> US breadth improved into the close.

### 1. Market Summary

- **Market Signal**: 62/100 (constructive, risk-on)

### 2. Index Commentary

| Index | Last | Change % |
| --- | --- | --- |
| S&P 500 | 6500 | +0.80% |

# HK Market Recap

## 2026-07-31 HK Market Recap

> Hong Kong tech outperformed.

### 1. Market Summary

- **Market Signal**: 58/100 (neutral, selective)

### 2. Index Commentary

| Index | Last | Change % |
| --- | --- | --- |
| Hang Seng Index | 18200 | +1.20% |
""",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster market"' in html
    assert "美股市场复盘" in html
    assert "港股市场复盘" in html
    assert "A股市场复盘" not in html


def test_generic_market_review_does_not_treat_english_pronoun_us_as_us_market():
    html = build_share_image_html(
        """# 大盘复盘

> This gives us more room to focus on the strongest sectors.

## 2026-07-31 大盘复盘

### 1. 盘面总览

- **盘面信号**：60/100（中性，均衡）

### 2. 指数结构

| 指数 | 最新 | 涨跌幅 |
| --- | --- | --- |
| 上证指数 | 3400 | +0.20% |
""",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster market"' in html
    assert "大盘复盘" in html
    assert "美股市场复盘" not in html


def test_hidden_market_region_metadata_preserves_single_region_chinese_market_title():
    html = build_share_image_html(
        """[dsa-market-region]: # (us)

# 🎯 大盘复盘

## 2026-07-31 大盘复盘

> 今晚先看科技股财报与指数承接。

### 一、盘面总览

- **盘面信号**：63/100（偏暖，可进攻）

### 二、指数结构

| 指数 | 最新 | 涨跌幅 |
| --- | --- | --- |
| 纳斯达克 | 19000 | +0.95% |
""",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster market"' in html
    assert "美股市场复盘" in html
    assert "A股市场复盘" not in html


def test_hidden_market_region_metadata_overrides_body_scope_mentions():
    html = build_share_image_html(
        """[dsa-market-region]: # (us)

# 🎯 大盘复盘

## 2026-07-31 大盘复盘

> 今晚主要看美股科技股财报，同时留意其与A股风险偏好的联动。

### 一、盘面总览

- **盘面信号**：63/100（偏暖，可进攻）

### 二、指数结构

| 指数 | 最新 | 涨跌幅 |
| --- | --- | --- |
| 纳斯达克 | 19000 | +0.95% |
""",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster market"' in html
    assert "美股市场复盘" in html
    assert "A股市场复盘" not in html


def test_english_breadth_line_populates_structured_market_breadth_cards():
    html = build_share_image_html(
        """# US Market Recap

## 2026-07-31 US Market Recap

> Breadth and liquidity both improved.

### 1. Market Summary

- **Market Signal**: 66/100 (constructive, risk-on)
- **Breadth**: Advancers 3200 / Decliners 1800 / Flat 100; Limit-up 88 / Limit-down 5; Turnover 14567 (CNY 100m)

### 2. Major Indices

| Index | Last | Change % |
| --- | --- | --- |
| S&P 500 | 6500 | +0.80% |
""",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster market"' in html
    assert "美股市场复盘" in html
    assert "市场宽度" in html
    assert "3200" in html
    assert "1800" in html
    assert "88" in html
    assert "14567 (CNY 100m)" in html


def test_market_share_image_keeps_signal_card_without_breadth_for_hk_review():
    html = build_share_image_html(
        """# HK Market Recap

## 2026-07-31 HK Market Recap

> Hong Kong tech outperformed into the close.

### 1. Market Summary

- **Market Signal**: 58/100 (neutral, selective)
- **Drivers**: Hang Seng held above prior support; average major-index change +0.42%
- **Guidance**: Signals are mixed; keep position sizing moderate and wait for confirmation.

### 2. Major Indices

| Index | Last | Change % |
| --- | --- | --- |
| Hang Seng Index | 18200 | +1.20% |
| Hang Seng Tech | 3900 | +1.85% |
""",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster market"' in html
    assert '<section class="market-signal">' in html
    assert '<strong>58</strong><small>/100</small>' in html
    assert "selective" in html
    assert "Hang Seng held above prior support" in html
    assert "Signals are mixed; keep position sizing moderate" in html
    assert "市场宽度" not in html


def test_single_stock_dashboard_title_routes_to_stock_poster():
    html = build_share_image_html(
        """# 2026-07-31 Decision Dashboard

## Apple Inc. (AAPL)

> 2026-07-31 15:30 | Score: **70** | Bullish

### Core Conclusion

**Buy**: Pullbacks into support remain actionable.

### Action Levels

| Ideal Entry | Secondary Entry | Stop Loss | Target |
| --- | --- | --- | --- |
| 205-207 | 202-204 | 198 | 220 |
""",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster stock"' in html
    assert "个股决策卡" in html
    assert "Apple Inc." in html
    assert '<span class="code">AAPL</span>' in html


def test_single_stock_dashboard_prefers_parenthesized_numeric_code_after_st_prefix():
    html = build_share_image_html(
        """# 2026-07-31 决策仪表盘

## 🟡 *ST 海越 (600387)

> 2026-07-31 15:30 | 评分：**62** | 中性

### 核心结论

**观望**：等待趋势进一步确认。
""",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster stock"' in html
    assert "个股决策卡" in html
    assert "ST 海越" in html
    assert '<span class="code">600387</span>' in html


def test_single_stock_dashboard_uses_trailing_parenthesized_us_ticker():
    html = build_share_image_html(
        """# 2026-07-31 Decision Dashboard

## IBM (IBM)

> 2026-07-31 15:30 | Score: **64** | Neutral

### Core Conclusion

**Hold**: Wait for a clearer breakout.
""",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster stock"' in html
    assert "个股决策卡" in html
    assert "IBM" in html
    assert '<span class="code">IBM</span>' in html


def test_single_stock_dashboard_uses_numeric_code_prefix_with_trailing_name():
    html = build_share_image_html(
        """# 2026-07-31 决策仪表盘

## 600519 贵州茅台

> 2026-07-31 15:30 | 评分：**72** | 看多

### 核心结论

**买入**：回调到支撑区可分批关注。
""",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster stock"' in html
    assert "个股决策卡" in html
    assert "贵州茅台" in html
    assert '<span class="code">600519</span>' in html


def test_multi_stock_daily_report_uses_generic_poster_and_keeps_all_stocks():
    html = build_share_image_html(
        """# 股票分析报告

## 📈 股票分析报告

### 贵州茅台 (600519)

**操作建议：买入** | **评分：72**

### 宁德时代 (300750)

**操作建议：观望** | **评分：61**
""",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster dashboard"' in html
    assert "贵州茅台" in html
    assert "宁德时代" in html
    assert '<span class="code">' not in html


def test_brief_aggregate_report_without_single_stock_heading_uses_generic_poster():
    html = build_share_image_html(
        """# Stock Analysis Report

## Summary

- Buy leaders on pullbacks.
- Avoid weak late-cycle names.
""",
        generated_on=date(2026, 7, 31),
    )

    assert 'class="poster dashboard"' in html
    assert "Summary" in html
    assert "Buy leaders on pullbacks." in html


def test_desktop_backend_build_scripts_bundle_share_image_assets():
    root = Path(__file__).resolve().parents[1]
    for relative_path in ("scripts/build-backend.ps1", "scripts/build-backend-macos.sh"):
        content = (root / relative_path).read_text(encoding="utf-8")
        assert "src/assets/share_image" in content
