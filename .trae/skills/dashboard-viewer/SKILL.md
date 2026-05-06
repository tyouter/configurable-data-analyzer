---
name: dashboard-viewer
description: |
  将 ChatBI 项目的 Dashboard JSON 渲染为精美的自包含 HTML 看板页面。
  支持多种 ECharts 主题（ggplot2_minimal / ggplot2_dark），KPI 卡片、图表网格布局、
  暗色模式切换，双击即可在浏览器中打开交互式看板。
  当用户要求查看/展示/导出/分享 Dashboard 时使用此 Skill。
triggers:
  - 查看.*看板
  - 展示.*dashboard
  - 导出.*dashboard
  - 生成.*HTML.*看板
  - dashboard.*viewer
  - 可视化.*报表
---

# Dashboard Viewer Skill

将 ChatBI 项目中存储的 Dashboard JSON 渲染为精美的自包含 HTML 页面。

## 使用场景

- 用户想**在浏览器中查看**已创建的 Dashboard
- 用户想**导出/分享** Dashboard 为独立 HTML 文件
- 用户想**切换主题**（亮色/暗色）
- 用户想**从 spec JSON 一键生成**完整 Dashboard

## 核心工具

### MCP 工具

```
# 导出 Dashboard 为 HTML
export_dashboard(
  dashboard_name="KPI看板",
  theme="ggplot2_minimal"
)

# 从 spec JSON 一键生成完整 Dashboard
generate_dashboard_from_spec(
  spec_path="dashboard_spec.json",
  dashboard_name="KPI看板",
  theme="ggplot2_minimal"
)

# 列出已有 Dashboard
list_dashboards()
```

### CLI

```bash
# 导出 Dashboard 为 HTML
python mcp_server/cli.py dashboard-export -d "KPI看板" --theme ggplot2_minimal

# 导出后自动打开浏览器
python mcp_server/cli.py dashboard-export -d "KPI看板" --open
```

## 可用主题

| 主题名 | 风格 | 说明 |
|--------|------|------|
| `ggplot2_minimal` | 亮色极简 | ggplot2 theme_minimal 风格，Tableau 经典配色 |
| `ggplot2_dark` | 暗色极简 | ggplot2 暗色主题，适合大屏展示 |

## 支持的图表类型

支持所有 ECharts 图表类型。内置模板（自动数据绑定）：

| 类型 | 说明 |
|------|------|
| `line` | 折线图 |
| `bar` | 柱状图 |
| `pie` | 饼图 |
| `funnel` | 漏斗图（自动计算转化率） |
| `scatter` | 散点图 |
| `bar_line` | 柱线混合图 |
| `boxplot` | 箱线图 |
| `ranking_bar` | 排行榜横向柱状图 |

通用类型（自动构造 option）：

| 类型 | 说明 |
|------|------|
| `area` | 面积图 |
| `ring` / `doughnut` | 环形图 |
| `radar` | 雷达图 |
| `gauge` | 仪表盘 |
| `stackedBar` / `stackedLine` | 堆叠图 |
| `candlestick` | K线图 |
| `heatmap` | 热力图 |
| `treemap` | 矩形树图 |
| `sankey` | 桑基图 |
| 其他 | 任意 ECharts series type 均可传入 |

## 输出格式

生成**单个自包含 HTML 文件**，特性：
- 内嵌 ECharts CDN（需联网加载）
- 内嵌主题配置（无需额外文件）
- 响应式布局（桌面/平板自适应）
- KPI 卡片 + 图表网格 + 业务域分组
- 图表交互（hover tooltip、缩放、图例筛选）
- 主题切换下拉框
- 双击 HTML 文件即可在浏览器中打开

## 设计原则

1. **ggplot2 审美**：极简网格、学术配色、出版级排版
2. **数据驱动**：直接消费 dashboard JSON 中的 ECharts option
3. **零依赖**：双击 HTML 文件即可打开，无需服务器
4. **Spec 驱动**：通过 `generate_dashboard_from_spec` 从 JSON 规格自动生成
