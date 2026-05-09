# ChatBI 重构规划

> 创建日期：2026-05-09
> 状态：讨论完成，待实施

---

## 一、背景：为什么需要重构

ChatBI MCP 是 Hermes 的嵌入式数据分析工具，负责数据导入、语义层管理、查询、可视化四大功能。在 Rednote BI 项目的实战中，暴露了一系列结构性问题，根源在于 **MCP 在错误的层面做错误的事**。

### 痛点汇总

| # | 问题 | 严重程度 | 影响 |
|---|------|----------|------|
| 1 | MCP 试图理解参考文档，但 rule-based 分类准确率仅 ~60% | P0 | 文件分类错误 → 语义层生成偏差 |
| 2 | 管线流程 6 阶段（INGEST→ALIGN→MAP→VERIFY→BUILD→SERVE）形式大于内容 | P0 | ALIGN 阶段只发现 14 个"事件"，实际有 132 个 span_name |
| 3 | 缺乏"需求→指标→事件"的显式映射层 | P0 | KPI 口径定义与代码实现脱节 |
| 4 | 缺乏可持久化的中间产物 | P1 | dashboard_spec 只有内存态，不可版本控制 |
| 5 | `regenerate_semantic_layer` 是全量核武器 | P1 | 触发一次就抹掉所有手动定义的指标 |
| 6 | MCP tool 粒度过粗 | P1 | 缺少 define_metric / define_chart / validate_metric 等细粒度工具 |
| 7 | 可视化层依赖 CDN + Playwright 截图 | P2 | 网络不稳定时图表空白，调试困难 |

---

## 二、讨论过程

### 阶段 1：发现问题（2026-05-07 架构评审）

首次 Rednote BI 项目测试暴露了管线流程中的断层：

- **ALIGN 阶段**：MCP 说"发现 14 个事件"，但 `explore_column_values(span_name)` 返回 132 个
- **MAP 阶段**：MCP 自动生成 3 个通用指标（total_events, dau, events_per_user），但用户实际需要 31 个业务 KPI
- **VERIFY 阶段**：缺少对口径正确性的验证——SQL 能跑通不等于结果对

评审结论：**MCP 不应该做参考文档理解**。Agent 有完整的 LLM 上下文，能理解合并单元格、布局语义、注释等复杂结构；MCP 的 `reference_parser` 只是 `pandas.to_string()` + 关键词匹配，会丢失大量上下文。

### 阶段 2：明确职责边界（2026-05-07 架构边界讨论）

确定了 MCP 与 Agent 的分工：

| MCP 该做 | 不该做 |
|----------|--------|
| DuckDB 数据存储/查询 | 读参考文档 |
| 语义层管理（指标注册、SQL 验证） | 理解文档语义 |
| 数据质量审计 | 文档分类 |
| SQL 安全执行（只读） | KPI 口径推导 |
| 图表渲染 | 需求→指标映射 |

### 阶段 3：加速模式（2026-05-08 实战验证）

在 Rednote 第二期（Porsche 指标）中，验证了 **Split-Workflow 模式**：

```
Agent 读参考文档 → Agent 推导 31 个 KPI 口径 → 注入 SQL 到 MCP 语义层 → MCP 查询 + 渲染
```

这个模式将管线从 6 阶段加速到 3 阶段，且质量更高（31 个 KPI 全部通过验证）。

### 阶段 4：协作模型升级（2026-05-08）

确定了 Hermes + DeepSeek-TUI 的三层协作：

```
用户飞书 → Hermes（架构讨论，出意图级 brief）
         → DeepSeek-TUI（explore → plan → implement → review → verify）
```

Hermes 负责架构设计和需求拆解（几百字方向+约束），DeepSeek-TUI 负责代码实现。

**协作成功六要素**（用户总结）：
1. 用户给清晰靶子（精确指标+公式+风格+输出链）
2. 确认节奏紧凑（一问一答，不展开不悬空）
3. 用户纠正精准（页面级别质疑，非笼统"再看看"）
4. 遇到工具不可用时果断绕行
5. 积累的参考文件兑现价值
6. 审计报告收束产物（方法+口径+边界全写清）

---

## 三、最终建议

### P0 — 必须改

**1. MCP 归还参考文档读取职责**

删除 MCP 的 `reference_parser` 和文件分类逻辑。参考文档由 Agent 直接读取（openpyxl / 标准文件读取），Agent 基于完整 LLM 上下文推导 KPI 口径和事件定义。

**2. 增加 dashboard_spec 持久化层**

引入 `dashboard_spec.json` 作为中间产物，存储每个图表的完整定义：

```json
{
  "charts": [
    {
      "id": "chart_01",
      "title": "DAU 趋势",
      "metric": "dau",
      "dimension": "event_date",
      "chart_type": "line",
      "business_domain": "用户活跃",
      "kpi_source": "rednote KPI definition_20260323.xlsx",
      "sql": "SELECT event_date, COUNT(DISTINCT reduser_id) as dau FROM events GROUP BY event_date"
    }
  ]
}
```

这个文件可版本控制、可审计、可复用。

**3. 建立需求→指标→事件映射层**

参考文档 → Agent 推导 KPI 口径 → Agent 注入 MCP 语义层 → MCP 验证 SQL。每一步都产生可审查的中间产物。

### P1 — 需要改

**4. 细粒度工具替换全量生成**

| 当前（全量） | 目标（细粒度） |
|-------------|---------------|
| `regenerate_semantic_layer` | `define_metric(name, sql)` |
| `create_project` 全流程 | `register_events(list)` |
| ~ | `validate_metric(id)` |

**5. 事件注册改为 Agent 驱动**

Agent 通过 `explore_column_values(span_name)` 发现全部事件 → Agent 筛选业务相关事件 → `register_events(list)` 注入语义层。不再依赖 MCP 的自动发现。

### P2 — 可优化

**6. 可视化层 inline ECharts 标准化**

放弃 CDN 依赖的 Playwright 截图方案，标准化为 inline ECharts + set_content() 模式。已在实际项目中验证可行。

**7. 配置路径持久化**

MCP server 路径从 `/workspace/`（D: 盘挂载，重启会丢）改为 `/opt/data/`（持久卷）。

---

## 四、实施路线

```
Phase 0: Agent 接管参考文档读取（P0）
  → 删 MCP reference_parser
  → Agent 直接 openpyxl 读文件
  → Agent 推导 KPI → update_metric 注入

Phase 1: dashboard_spec 持久化（P0）
  → 定义 spec JSON schema
  → generate_dashboard_from_spec 支持 spec 文件
  → 建立 spec 版本管理

Phase 2: 细粒度工具（P1）
  → 新增 define_metric / register_events / validate_metric
  → 保留 regenerate_semantic_layer 作为全量回退

Phase 3: 协作流程固化（P0-P2）
  → 更新 chatbi skill 的 Pipeline Protocol
  → 补充 Split-Workflow 作为标准模式
  → 积累参考文件库
```

## 五、当前状态

| 项目 | 状态 |
|------|------|
| Rednote-BI-Analysis-2 | 28 指标通过验证 |
| 协作模式（Hermes→TUI） | 已验证 |
| Split-Workflow | 已验证 |
| inline ECharts 截图 | 已验证（替代 CDN） |
| DeepSeek-TUI 安装 | v0.8.16 完成 |
| MCP 架构边界文档 | 已归档至此 |
