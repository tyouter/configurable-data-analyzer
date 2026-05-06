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

## 核心工具

### Python 库层面

```python
from mcp_server.dashboard_html import export_dashboard_html, render_dashboard_html

# 导出为 HTML 文件
html_path = export_dashboard_html(
    projects_dir="projects",
    project_id="<project_id>",
    dashboard_name="Rednote Dashboard",
    theme="ggplot2_minimal",  # 或 "ggplot2_dark"
)

# 或直接获取 HTML 字符串
from mcp_server.dashboard_store import load_dashboard_by_name
from mcp_server.project_model import ProjectStore

dashboard = load_dashboard_by_name("projects", "<project_id>", "Rednote Dashboard")
html = render_dashboard_html(dashboard, project_name="小红书分析", theme="ggplot2_minimal")
```

### CLI 层面

```bash
# 导出 Dashboard 为 HTML
python mcp_server/cli.py dashboard-export -d "Rednote Dashboard" --theme ggplot2_minimal

# 导出后自动打开浏览器
python mcp_server/cli.py dashboard-export -d "Rednote Dashboard" --open
```

### MCP 工具层面

```
调用 export_dashboard 工具：
  project_id: <project_id>
  dashboard_name: "Rednote Dashboard"
  theme: "ggplot2_minimal"
```

## 可用主题

| 主题名 | 风格 | 说明 |
|--------|------|------|
| `ggplot2_minimal` | 亮色极简 | ggplot2 theme_minimal 风格，Tableau 经典配色 |
| `ggplot2_dark` | 暗色极简 | ggplot2 暗色主题，适合大屏展示 |

## 输出格式

生成**单个自包含 HTML 文件**，特性：
- 内嵌 ECharts CDN（需联网加载）
- 内嵌主题配置（无需额外文件）
- 响应式布局（桌面/平板自适应）
- KPI 卡片 + 图表网格
- 图表交互（hover tooltip、缩放、图例筛选）
- 主题切换下拉框

## 设计原则

1. **ggplot2 审美**：极简网格、学术配色、出版级排版
2. **数据驱动**：直接消费 dashboard JSON 中的 ECharts option
3. **零依赖**：双击 HTML 文件即可打开，无需服务器
4. **Tabler UI 风格**：卡片式布局、圆角、微妙阴影
