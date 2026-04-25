# Rednote Data Analyzer

数据分析工具，基于对话与SKILL加载，LLM 进行云端策略分析，然后调用本地分析进行本地数据分析。

## 项目结构

```
.
├── .trae/
│   └── skills/
│       └── data-analysis/      # Trae SKILL
│           └── SKILL.md
├── skills/                     # Claude Agent skill
├── config/
│   └── metrics.yaml            # 待创建，指标配置（可增量添加）
├── data/
│   └── *.xlsx                  # 数据文件
├── tools/
│   └── generate_sample.py      # 示例数据生成器
├── requirements.txt
└── CLAUDE.md
```

## 核心组件

### 1. 数据分析 SKILL

位置：`skills/data-analysis/SKILL.md`

功能：
- 数据概览与探索
- 用户行为分析
- 自定义指标计算
- 多维度聚合分析

触发关键词：`分析数据`、`数据分析`、`统计分析`、`用户分析`、`查询数据`、`分析报告`

### 2. 分析工具 (tools/analyzer.py)


### 3. 指标配置 (config/metrics.yaml)

支持增量添加新指标：

```yaml
metrics:
  metric_name:
    name: "指标显示名称"
    type: "count|unique_count|average"
    column: "计算列名"
    description: "指标说明"
```

## 使用方式

### 分析数据

1. 将脱敏后的 Excel 文件放入 `data/` 目录
2. 调用 data-analysis SKILL 进行分析

示例命令：
- "分析 data/sample_data.xlsx，一共有多少个用户？"
- "帮我看看这份数据的基本情况"
- "分析用户 user_0001 的行为链"

### 生成示例数据

```bash
python tools/generate_sample.py
```

## 数据格式要求

Excel 文件应包含以下类型字段：
- 用户标识列（如 `user_id`）
- 时间戳列（如 `timestamp`）
- 事件类型列（如 `event_type`）
- 其他属性列（如 `page_name`、`action` 等）

## 增量开发

### 添加新指标

编辑 `config/metrics.yaml`，添加新的指标定义。

### 添加新工具函数

在 `tools/analyzer.py` 中扩展 DataAnalyzer 类或添加独立函数。

### 更新 SKILL

编辑 `.trae/skills/data-analysis/SKILL.md`，添加新的分析场景和示例。

## 依赖

- pandas >= 2.0.0
- openpyxl >= 3.1.0
- pyyaml >= 6.0

## 数据清洗规则

- **过滤测试事件**：加载数据时，过滤掉 `rednote_poi_title` 为 `akimbo(西丽店)` 的行（疑似测试事件）
