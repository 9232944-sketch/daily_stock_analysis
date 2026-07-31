# 内建选股引擎说明（实现参考 AlphaSift）

DSA 的选股能力现在由主仓库中的 `src/services/screening/` 直接提供，不再安装、导入或运行外部 `alphasift` Python 包，也没有运行时修复安装入口。

这不是对来源的隐去。内建实现衍生自 [AlphaSift](https://github.com/ZhuLinsen/alphasift) 的提交 [`9f522747caafd3c0b1ddb7e14d5cf44c8580b6cf`](https://github.com/ZhuLinsen/alphasift/commit/9f522747caafd3c0b1ddb7e14d5cf44c8580b6cf)，按 Apache License 2.0 使用和修改。源文件保留显著归因头，完整许可证位于 `src/services/screening/LICENSE`，第三方声明见根目录 `THIRD_PARTY_NOTICES.md`。

## 当前边界

- 默认仍关闭：`ALPHASIFT_ENABLED=false`。该变量名为兼容已有部署而保留，不表示还依赖 AlphaSift 插件。
- 主 API 前缀为 `/api/v1/screening`。
- 旧 `/api/v1/alphasift` 前缀暂时保留为不出现在 OpenAPI 文档中的兼容别名，避免已有 Web 缓存或调用方立即中断。
- `/api/v1/alphasift/install` 已删除；`ALPHASIFT_INSTALL_SPEC`、受信任 pip pin 和运行时 `pip install` 逻辑也已删除。
- 策略、快照、日 K、硬过滤、因子评分、风险叠加、LLM 重排、热点和稳定适配契约均由仓库内代码负责。
- DSA 继续负责开关、任务队列、API、行情/基本面/新闻上下文、缓存、错误映射和 Web 展示。
- `ALPHASIFT_DATA_DIR` 等已有缓存配置与 `data/alphasift/` 路径暂时保留，避免升级后丢失 last-good、热点和日线缓存。它们是兼容名称，不是外部依赖。

## 代码与契约

内建代码位于：

- `src/services/screening/`：选股核心和 Apache-2.0 许可证；
- `src/services/screening/strategies/`：随 DSA 发布的策略 YAML；
- `src/services/screening/dsa_adapter.py`：供 DSA 服务层调用的稳定边界；
- `src/services/alphasift_service.py`：现有 API 和 DSA 增强逻辑的兼容门面。

适配层继续提供三个稳定函数：

```python
def get_status(context: dict | None = None) -> dict: ...
def list_strategies(context: dict | None = None) -> list[dict]: ...
def screen(
    strategy: str,
    *,
    market: str = "cn",
    max_results: int = 20,
    use_llm: bool = True,
    context: dict | None = None,
) -> dict: ...
```

`get_status()` 会公开非敏感来源信息：

```json
{
  "available": true,
  "engine": "builtin",
  "contract_version": "1",
  "reference_project": "https://github.com/ZhuLinsen/alphasift",
  "reference_revision": "9f522747caafd3c0b1ddb7e14d5cf44c8580b6cf"
}
```

这些字段用于可追溯性，不会触发联网、版本检查或安装。

## API

| 主路径 | 方法 | 行为 |
| --- | --- | --- |
| `/api/v1/screening/status` | GET | 返回开关、内建引擎状态、契约版本、参考项目和数据源健康信息 |
| `/api/v1/screening/strategies` | GET | 返回随 DSA 发布的内建策略 |
| `/api/v1/screening/hotspots` | GET | 读取缓存或显式刷新热点题材 |
| `/api/v1/screening/hotspots/{topic}` | GET | 返回题材路线和相关股票 |
| `/api/v1/screening/screen` | POST | 同步执行选股，主要用于 API 调试和兼容 |
| `/api/v1/screening/screen/tasks` | POST | 提交可恢复的后台选股任务 |
| `/api/v1/screening/screen/tasks/{task_id}` | GET | 查询进度、错误或最终候选 |

除已删除的安装接口外，旧 `/api/v1/alphasift/*` 路径在迁移期与上表对应。新代码和 Web 只使用 `/api/v1/screening/*`。

## 数据与 LLM 行为

- 全市场快照按配置的数据源优先级尝试，单一数据源失败后继续降级，并保留 source health 和 last-good 缓存。
- 有 `TUSHARE_TOKEN` 时，默认快照顺序以 Tushare 开始；没有 token 时从 Sina 开始。显式 `SNAPSHOT_SOURCE_PRIORITY` 仍优先。
- 日 K 增强优先复用 DSA 的历史行情链路；无可用结果时才使用内建引擎自身的数据源 fallback。
- 候选在 LLM 重排前只补充有限的轻量 DSA 上下文；最终 Top 候选再补行情、基本面、新闻和摘要，避免初筛阶段成倍扩大网络请求。
- DSA 的模型、渠道、base URL、额外 headers、fallback、timeout 和 token 上限只在单次调用期间注入；不会改写 `.env`。
- 数据源 wrapper 继续保留 caller-side timeout、重试、降级和缓存。移除外部包依赖不会消除行情源、新闻源或 LLM 本身的网络风险。

## 收益

1. 部署可复现：`pip install -r requirements.txt` 不再需要 Git、GitHub 可达性或 VCS 包构建能力，Docker 与桌面产物使用同一份源码。
2. 启动链路更简单：业务请求不会执行安装或修改 Python 环境，权限、代理、证书和并发安装问题从运行路径移除。
3. 版本一致：服务层、策略和 Web 契约在同一个 PR 中演进，不再因外部仓库 pin、用户 `.env` 覆盖或本地残留包而漂移。
4. 审查更完整：数据源 fallback、评分、策略、API、测试和文档可以在一个 diff 中做端到端审查。
5. 供应链面缩小：删除运行时任意 pip 来源与修复安装接口，减少凭证泄露、来源劫持和不可追溯代码替换风险。
6. 离线和桌面体验更稳定：冻结产物直接收集 `src.services.screening` 及策略资源，不依赖用户现场安装插件。

## 风险与代价

1. 主仓库体积和维护面增加。选股代码、策略及测试由 DSA 维护者直接负责，不能再把问题简单归为外部插件。
2. 上游更新不会自动获得。AlphaSift 后续修复必须经过选择、审查和回归后人工移植；这能降低意外升级风险，但会产生同步成本。
3. 衍生实现可能分叉。DSA 特有的数据 provider、任务和 API 约束会逐渐与上游不同，因此不能把上游新提交直接整包覆盖。
4. 许可证合规成为发布要求。删除归因头、许可证或第三方声明会破坏来源可追溯性；打包时也必须包含 `src/services/screening/LICENSE`。
5. 内建不等于无故障。行情、热点、新闻和 LLM 仍依赖第三方网络服务，timeout、限流、字段变化和降级路径仍需持续监控。
6. 存在迁移期技术债。`AlphaSiftService`、`ALPHASIFT_ENABLED`、缓存目录和旧路由名暂时保留以换取兼容；未来删除前需要发布弃用通知和使用量证据。
7. 选股结果仍是实验性研究输出。内建只改变代码所有权和部署方式，不提升为交易建议，也不保证收益或数据完整性。

## 风险控制

- 运行层只允许导入 `src.services.screening.*`；依赖清单、Docker 和桌面脚本均有静态回归，防止重新引入外部包。
- 策略目录随包发布，状态探针会检查策略数量；冻结产物会探测适配模块并校验打包前后的策略数量。
- `/install` 删除后不可由远程请求修改 Python 环境。
- 新主路由与旧兼容路由共用同一个 router，避免两套业务实现漂移。
- `engine=builtin` 和参考 commit 出现在状态响应中，便于问题报告确认实际实现来源。
- 数据源失败继续 fail-soft；模块、策略或契约错误则返回带诊断的 `424`，不使用静默空结果掩盖实现故障。

## 更新参考实现的流程

AlphaSift 仅作为参考来源，不是自动同步源。维护者需要：

1. 记录计划参考的上游 commit 和许可证变化；
2. 比较与 `src/services/screening/` 的语义差异，按模块选择性移植；
3. 保留每个衍生文件的归因头，更新 `REFERENCE_REVISION` 和 `THIRD_PARTY_NOTICES.md`；
4. 检查 DSA runtime bridge、API/Web 字段、数据源降级、策略资源和冻结打包；
5. 更新本文档和 `docs/CHANGELOG.md`，并执行后端、Web、Docker/桌面相关验证。

禁止以覆盖整个目录的方式“升级”，因为这会覆盖 DSA 特有路径和兼容修复。

## 升级与回滚

升级时正常拉取 DSA 代码、安装 `requirements.txt` 并重建服务即可；不再需要清理或更新 `ALPHASIFT_INSTALL_SPEC`。历史 `.env` 中遗留的该变量会被忽略，可以在确认无需回滚旧版本后删除。

回滚有两层：

- 快速业务回滚：设置 `ALPHASIFT_ENABLED=false` 并重启。普通个股分析、报告、通知和问股链路不受影响。
- 代码回滚：revert 引入内建引擎的提交并按目标版本重装依赖、重建 Docker/桌面产物。若回滚到仍使用外部包的旧版本，再按该旧版本文档恢复对应依赖。

缓存格式没有在本次迁移中主动重置。回滚前如要保留 `data/alphasift/`，应先备份；不要直接删除用户缓存目录。
