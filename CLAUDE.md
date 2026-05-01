# ChatBI MCP Server

项目无关的对话式数据分析平台，通过 MCP 协议暴露数据分析能力给 AI Agent。

## 项目结构

```
.
├── mcp_server/                 # MCP Server 核心
│   ├── server.py               # MCP 工具入口（19个工具）
│   ├── project_model.py        # 项目 CRUD + DuckDB 数据层
│   ├── semantic_generator.py   # LLM 语义层生成
│   ├── semantic_query.py       # L1/L2/L3 查询引擎
│   ├── analysis_templates.py   # L2 分析模板（留存/漏斗/同环比）
│   ├── chart_renderer.py       # ECharts 图表生成
│   ├── dashboard_store.py      # Dashboard 持久化
│   ├── file_classifier.py      # 文件自动分类（原始数据/参考文档）
│   ├── data_auditor.py         # 数据质量审计引擎
│   ├── reference_parser.py     # 参考文档解析 + KPI 校验
│   └── cli.py                  # CLI 接口
├── projects/                   # 运行时项目数据（不入库）
│   └── {project_id}/
│       ├── project.yaml        # 项目配置 + 语义层
│       ├── data/               # 原始数据文件
│       └── {id}.duckdb         # DuckDB 数据库
├── examples/                   # 示例配置模板
├── tests/                      # 测试套件
├── docs/                       # 文档
├── .mcp.json                   # Trae/VS Code MCP 配置
└── requirements.txt            # Python 依赖
```

## 核心能力

### 项目管理

- **多项目隔离**：每个项目独立的数据文件、语义层和 DuckDB 实例
- **交互式创建**：4 阶段流程（文件分类 → 认知对齐 → 确认 → 构建）
- **参考文档识别**：自动区分原始数据、KPI 定义、数据字典、需求文档

### 三级查询协议

| 级别 | 方式 | 说明 |
|------|------|------|
| L1 | `semantic_query(level="L1")` | 指标 + 维度 + 筛选，自动生成 SQL |
| L2 | `semantic_query(level="L2")` | 留存/漏斗/同环比分析模板 |
| L3 | `raw_sql()` | 原始 SQL 兜底查询 |

### 可视化与 Dashboard

- ECharts 图表生成（line/bar/pie/funnel/scatter/table）
- Dashboard CRUD：创建/保存/删除图表

## MCP 工具一览

| 工具 | 功能 |
|------|------|
| `create_project` | 创建项目（4阶段交互） |
| `list_projects` | 列出所有项目 |
| `switch_project` | 切换当前项目 |
| `get_current_project` | 获取当前项目信息 |
| `delete_project` | 删除项目 |
| `regenerate_semantic_layer` | 重新生成语义层 |
| `semantic_query` | 结构化语义查询（L1/L2） |
| `raw_sql` | 原始 SQL 查询（L3） |
| `get_semantic_context` | 获取语义层元数据 |
| `render_chart` | 生成 ECharts 图表 |
| `list_dashboards` | 列出 Dashboard |
| `create_dashboard` | 创建 Dashboard |
| `save_chart_to_dashboard` | 保存图表到 Dashboard |
| `delete_chart` | 删除图表 |
| `delete_dashboard` | 删除 Dashboard |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CHATBI_PROJECTS_DIR` | 项目数据存储目录 | `./projects` |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | 无 |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 | `https://api.deepseek.com` |
| `BI_MODEL` | LLM 模型名 | `deepseek-chat` |

## MCP Server 配置

ChatBI MCP Server 通过 MCP 协议暴露数据分析能力，支持多种 Agent/IDE 接入：

### Trae / VS Code

项目根目录 `.mcp.json` 已配置，开箱即用。

### Claude Desktop

将以下配置复制到 Claude Desktop 配置目录：
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/.claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "chatbi": {
      "command": "<你的Python绝对路径>",
      "args": ["<项目绝对路径>/mcp_server/server.py"],
      "env": {
        "DEEPSEEK_API_KEY": "<你的API Key>",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "BI_MODEL": "deepseek-v4-pro",
        "CHATBI_PROJECTS_DIR": "<数据存储绝对路径>"
      }
    }
  }
}
```

### Hermes Agent

```bash
hermes mcp add chatbi --command python --args "mcp_server/server.py" \
  --env DEEPSEEK_API_KEY=<key> --env BI_MODEL=deepseek-v4-pro
```

## 依赖

```
pandas>=2.0.0
openpyxl>=3.1.0
pyyaml>=6.0
duckdb>=0.9.0
mcp[cli]>=1.0.0
fastapi>=0.100.0
uvicorn>=0.24.0
requests>=2.31.0
```

## 开发指南

### 运行测试

```bash
# 单元测试
python tests/test_classifier.py
python tests/test_auditor.py
python tests/test_parser.py
python tests/test_kpi_validator.py
python tests/test_report_persist.py

# 集成测试
python tests/test_phase1.py
python tests/test_phase2.py
python tests/test_autoresearch_p3.py

# 真实数据测试（需要 CHATBI_TEST_DATA_DIR 指向数据目录）
python tests/test_real_data.py
```

### 创建新项目

通过 MCP 工具 `create_project` 的 4 阶段交互流程：

1. **start** — 提交数据文件，自动分类 + 审计 + 参考文档解析
2. **classify** — 用户修正文件分类，回答认知对齐问题（可多轮）
3. **confirm** — 确认要导入的原始数据、参考文档和分析目标
4. **build** — 导入确认的文件，生成语义层

# currentDate
Today's date: 2026-05-01.
