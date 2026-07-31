# 分享图片模板与数据填充

分享图片用于把个股分析和市场复盘转换为适合社交平台传播的 1080px 长图。个股和大盘使用两套独立的信息结构，但共用 DSA 品牌、项目二维码、小红书二维码和风险声明。

## 运行时如何填充

现有通知链路不需要手工组装图片数据：

```text
个股 AnalysisResult
  -> NotificationService 生成稳定 Markdown
  -> share_image 提取决策字段
  -> 个股决策卡 HTML
  -> wkhtmltoimage / markdown-to-file 输出 PNG

大盘 MarketOverview + market_light + LLM 复盘
  -> MarketAnalyzer 生成稳定 Markdown
  -> share_image 提取市场字段
  -> 市场复盘卡 HTML
  -> wkhtmltoimage / markdown-to-file 输出 PNG
```

`MARKDOWN_TO_IMAGE_CHANNELS`、`MD2IMG_ENGINE`、`MARKDOWN_TO_IMAGE_MAX_CHARS` 继续控制哪些通知渠道转图、使用哪个引擎以及最大输入长度。转换失败时仍回退为文本通知。

模板只读取报告中已经存在的数据，不根据分数自行推导操作、不补造价格或指标。字段为 `N/A`、`-`、空值或没有对应模块时，相关卡片自动隐藏。

## 个股卡字段映射

| 图片区域 | 项目字段 / 生成来源 | 填充规则 |
| --- | --- | --- |
| 股票名称、代码 | `AnalysisResult.name`、`AnalysisResult.code` | 从个股标题提取 |
| 操作、评分、趋势 | 最终展示动作、`sentiment_score`、`trend_prediction` | 使用通知报告已经校准后的展示结果，评分范围 0–100 |
| 核心结论 | `dashboard.core_conclusion.one_sentence` | 没有时隐藏 |
| 市场快照 | `market_snapshot` | 当前/收盘价、涨跌幅、量比、换手率按可用字段展示；数据源进入底部声明 |
| 执行计划 | `dashboard.battle_plan.sniper_points` | `ideal_buy`、`secondary_buy`、`stop_loss`、`take_profit`；支持数值、区间和带条件的文本 |
| 技术参考 | `dashboard.data_perspective` | 展示均线、量能、支撑和压力；项目没有稳定 RSI 字段，因此不会为了版面补造 RSI |
| 催化与风险 | `dashboard.intelligence` | `positive_catalysts` 与 `risk_alerts` 最多各展示 3 条 |
| 持仓建议 | `core_conclusion.position_advice`、`battle_plan.position_strategy` | 区分未持仓、已持仓、仓位、建仓和风控 |

模板支持项目当前的中英文报告标签。一个“决策仪表盘”只有一只股票时会自动使用个股卡；包含多只股票时保留多股报告布局，避免错误地把第一只股票当成整份报告。

## 大盘卡字段映射

| 图片区域 | 项目字段 / 生成来源 | 填充规则 |
| --- | --- | --- |
| 日期、市场范围 | `MarketOverview.date`、复盘区域 | 生成 A股/美股/港股/日股/韩股市场复盘标题 |
| 市场信号 | `market_light.score`、`temperature_label`、`label`、`guidance` | 使用确定性市场灯号结果，不由模板二次评分 |
| 指数表现 | `MarketOverview.indices` | 最多展示 3 个主要指数的最新值和涨跌幅 |
| 市场宽度 | `up_count`、`down_count`、`limit_up_count`、`limit_down_count`、`total_amount` | 仅在数据源支持且报告包含结构化数据时展示 |
| 强势板块 | `top_sectors` | 展示领涨 Top 3；没有板块榜的市场自动隐藏 |
| 消息催化 | 复盘“消息催化”章节 | 最多提炼 2 条已有内容，不新增事实 |
| 明日计划 | 复盘“明日交易计划”章节 | 优先展示结论、仓位区间、关注方向 |
| 风险提示 | 复盘“风险提示”章节 | 最多展示 3 条，过滤重复免责声明 |

## 手工填充或本地预览

模板输入仍然是项目生成的 Markdown。调试时可以准备一份最小个股报告：

```markdown
## 🟢 贵州茅台 (600519)

> 2026-07-31 15:00 | 评分: **72** | 看多

### 📌 核心结论

**买入**: 趋势偏强，等待回踩支撑后分批执行。

| 持仓情况 | 操作建议 |
| --- | --- |
| 空仓者 | 等待回踩确认，不追高。 |
| 持仓者 | 继续持有，跌破止损位退出。 |

### 🎯 作战计划

| 点位类型 | 价格 |
| --- | --- |
| 理想买入点 | 1420-1450 |
| 次优买入点 | 1380-1400 |
| 止损位 | 1350 |
| 目标位 | 1580 |
```

生成 HTML 预览：

```python
from pathlib import Path
from src.share_image import build_share_image_html

markdown_text = Path("reports/example.md").read_text(encoding="utf-8")
html = build_share_image_html(markdown_text)
Path("share-preview.html").write_text(html, encoding="utf-8")
```

实际通知转 PNG 仍调用：

```python
from src.md2img import markdown_to_image

png_bytes = markdown_to_image(markdown_text)
```

大盘报告应沿用 `MarketAnalyzer` 生成的“盘面信号、指数结构、板块主线、消息催化、明日交易计划、风险提示”章节；不建议在外部另造一套字段名称，否则模板会按缺失字段处理。

## 视觉与内容边界

- 涨跌颜色以最终报告内容为准；模板不改变项目现有市场颜色配置和业务判断。
- 买入点允许是价格区间或“价格 + 触发条件”，不会强制截成一个可能误导的数字。
- 没有真实价格序列时不绘制伪 K 线；顶部仅保留非数据化的品牌光晕。
- 二维码使用仓库随包资源并以内嵌 Data URI 渲染，不依赖运行时网络。
- 图片底部固定说明“AI 生成，仅供研究交流，不构成投资建议”。
