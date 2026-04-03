---
name: data-analysis
description: 数据分析SKILL - 支持自然语言对话式数据分析，可读取Excel数据，调用本地分析工具完成各类分析任务
trigger:
  - 分析数据
  - 数据分析
  - 统计分析
  - 用户分析
  - 查询数据
  - 分析报告
---

# 数据分析 SKILL

## 概述

本SKILL用于对脱敏后的Excel数据进行自然语言对话式分析。支持：
- 数据概览与探索
- 用户行为分析
- 自定义指标计算
- 多维度聚合分析
- 分析报告生成
- **多项目配置支持**：按业务项目组织配置，智能匹配数据文件

## 工作流程

### 1. 数据加载阶段

首先获取用户提供的Excel文件路径，然后：

```
步骤：
1. 请用户提供脱敏后的Excel文件路径
2. 使用 pandas 读取文件内容
3. 使用 ProjectMatcher 自动检测数据文件属于哪个项目：
   - 文件名模式匹配
   - 列名特征匹配
   - 列名相似度匹配
4. 如果检测到项目：
   - 加载项目配置（schema, metrics, mapping）
   - 展示项目名称和配置信息
5. 如果未检测到项目：
   - 询问用户是否创建新项目
   - 如果是：
     a. 询问项目名称和显示名称
     b. 询问是否有表头说明文档
     c. 如果有，使用 SchemaGenerator 从表头说明文档生成 schema
     d. 如果没有，从数据样本自动推断类型生成 schema
     e. 创建项目配置文件
   - 如果否，使用默认配置
6. 展示数据概览（行数、列数、字段列表）
7. 验证数据是否符合 schema 定义
```

### 2. 需求理解与指标匹配

分析用户的需求，提取关键词，并匹配预定义指标：

```
步骤：
1. 从当前项目加载 metrics 配置
2. 分析用户的自然语言需求
3. 提取相关关键词（如"用户数"、"日活"、"活跃度"等）
4. 调用 tools.analyzer.match_metric_by_keywords() 匹配预定义指标
5. 如果匹配到候选指标：
   - 使用 AskUserQuestion 展示候选指标供用户选择
   - 用户选择后确定要计算的指标
6. 如果没有匹配到指标：
   - 询问用户具体需要计算什么指标
   - 尝试理解用户的具体需求
```

### 3. 分析执行阶段

根据用户选择的指标，调用本地分析工具进行计算：

```python
# 加载数据
from tools.analyzer import DataAnalyzer
analyzer = DataAnalyzer()
analyzer.load_data("用户提供的数据文件路径")

# 获取数据概览
summary = analyzer.get_summary()
print(f"数据包含 {summary['rows']} 行，{summary['columns']} 列")
print(f"字段: {', '.join(summary['column_names'])}")

# 验证数据结构
is_valid = analyzer.validate_data_schema()
if not is_valid:
    print("数据结构验证失败，请检查必需字段")

# 根据用户选择的指标计算
for metric_name in selected_metrics:
    try:
        result = analyzer.calculate_metric(metric_name)
        print(f"{result['name']}: {result['value']}")
    except Exception as e:
        # 捕获并转化为友好的错误信息
        print(f"计算指标 {metric_name} 时出错: {str(e)}")
        print(f"请检查数据中是否包含必需的字段")
```

### 4. 结果输出阶段

根据用户需求输出分析结果：

```
输出格式：
- 文字报告：以清晰易读的格式展示分析结果
- 数据表格：如果用户需要详细数据
- 进一步分析选项：询问用户是否需要其他分析
```

## 可用工具

### ConfigManager 类

多项目配置管理器，提供以下方法：

|方法|功能|参数|
|------|------|------|
|`create_project(name, display_name)`|创建新项目|项目名称、显示名称|
|`list_projects()`|列出所有项目|无|
|`load_project_config(name)`|加载项目完整配置|项目名称|
|`save_schema(project, name, data)`|保存schema配置|项目名、schema名、数据|
|`load_schema(project, name)`|加载schema配置|项目名、schema名|
|`save_metrics(project, data)`|保存metrics配置|项目名、数据|
|`load_metrics(project)`|加载metrics配置|项目名|
|`save_mapping(project, data)`|保存mapping配置|项目名、数据|
|`load_mapping(project)`|加载mapping配置|项目名|

### ProjectMatcher 类

项目自动匹配器，提供以下方法：

|方法|功能|参数|
|------|------|------|
|`detect_project(file_path, df)`|自动检测项目|文件路径、Dataframe|
|`match_by_filename(filename)`|文件名匹配|文件名|
|`match_by_columns(columns)`|列名匹配|列名列表|
|`calculate_similarity(cols1, cols2)`|相似度计算|列名集合|

### SchemaGenerator 类

Schema配置生成器，提供以下方法：

|方法|功能|参数|
|------|------|------|
|`generate_from_template(template, data_file)`|从模板生成schema|模板文件、数据文件|
|`infer_column_types(df)`|推断列类型|Dataframe|
|`parse_template_document(template_file)`|解析模板文档|模板文件|
|`create_schema_dict(template, types)`|创建schema配置|模板数据、推断类型|
|`generate_schema_from_dataframe(df, name, desc)`|从数据框生成schema|Dataframe、名称、描述|

### DataAnalyzer 类

核心分析器，提供以下方法：

| 方法 | 功能 | 参数 |
|------|------|------|
| `load_data(file_path, project_name)` | 加载Excel数据 | 文件路径、项目名（可选） |
| `get_summary()` | 获取数据概览 | 无 |
| `get_columns()` | 获取所有列名 | 无 |
| `validate_data_schema()` | 验证数据schema | 无 |
| `get_current_project()` | 获取当前项目 | 无 |
| `set_current_project(project_name)` | 设置当前项目 | 项目名称 |
| `group_by_user(column)` | 按用户分组 | 用户ID列名 |
| `get_user_timeline(user_id)` | 获取用户行为时序 | 用户ID |
| `query(filters)` | 条件查询 | 过滤条件字典 |
| `calculate_metric(name)` | 计算指标|指标名称 |
| `export_to_json(path)` | 导出JSON | 输出路径 |

### 独立函数

| 函数 | 功能 |
|------|------|
| `load_excel(path)` | 快速加载Excel返回分析器 |
| `query_data(analyzer, filters)` | 查询数据 |
| `aggregate_by_user(analyzer, column)` | 用户聚合 |
| `calculate_metrics(analyzer, names)` | 批量计算指标 |
| `match_metric_by_keywords(keywords)` | 通过关键词匹配指标 |
| `load_metrics_config()` | 加载指标配置 |

## 错误处理

### xlsx SKILL 错误
- 文件不存在：提示用户提供正确的文件路径
- 文件格式错误：提示文件必须是Excel格式
- 文件损坏：提示重新获取数据文件

### 数据验证错误
- 缺少必需列：根据schema定义，提示数据中缺少哪些字段
- 数据格式不符：提示数据格式问题，如时间戳格式

### 项目配置错误
- 项目不存在：提示检查项目名称或创建新项目
- Schema验证失败：提示缺失的必需字段
- 配置文件损坏：提示检查配置文件格式

### 业务计算错误
- 指标计算失败：提示可能的解决方案
- 数据为空：提示筛选条件过于严格

### 用户交互错误
- 用户输入无效：提示重新输入
- 没有匹配指标：询问用户具体需求

## 配置文件结构

### 项目目录结构

```
config/
├──<project_name>/
│   ├── schemas/
│   │   └──<schema_name>.yaml
│   ├── metrics.yaml
│   └── mapping.yaml
```

### mapping配置（项目识别与映射）

```yaml
project:
  name: "项目名称"
  display_name: "项目显示名称"
  version: "1.0"

file_patterns:
  - "rednote_.*"         # 文件名匹配模式
  - "sample_data.xlsx"

data_signatures:           # 数据特征识别
  - required_columns: ["user_id", "event_type", "timestamp"]
    confidence: 0.9

default_schema: "user_behavior"
priority: 10              # 匹配优先级（数字越大优先级越高）
```

### Schema配置（数据结构定义）

```yaml
schema:
  name: "用户行为数据"
  version: "1.0"
  description: "用户行为埋点数据结构"

columns:
  user_id:
    type: "string"
    required: true
    description: "用户唯一标识"

  event_type:
    type: "categorical"
    required: true
    description: "事件类型"
    enum: ["page_view", "click", "scroll", "submit_form"]

  timestamp:
    type: "datetime"
    required: true
    format: "%Y-%m-%d %H:%M:%S"
    description: "事件发生时间"
```

### Metrics配置（指标定义）

```yaml
metrics:
  total_users:
    name: "总用户数"
    type: "unique_count"
    column: "user_id"
    description: "数据中唯一的用户数量"
    keywords: ["用户数", "总用户", "用户总量"]
```

## 指标配置

指标定义在项目目录下的 `metrics.yaml` 中，支持增量添加：

```yaml
metrics:
  metric_name:
    name: "指标显示名称"
    type: "count|unique_count|average|custom|derived"
    column: "计算列名"
    description: "指标说明"
    keywords: ["关键词1", "关键词2"]
```

### 当前支持的指标

1. **total_users** - 总用户数（唯一计数）
   - 关键词：用户数、总用户、用户总量

2. **total_events** - 总事件数
   - 关键词：事件数、总事件、事件总量

3. **avg_duration** - 平均停留时长
   - 关键词：平均时长、停留时间、平均停留

4. **daily_active_users** - 日活跃用户数
   - 关键词：日活、日活跃用户、DAU

5. **user_activity_rate** - 用户活跃度
   - 关键词：活跃度、用户活跃率

6. **high_value_users** - 高价值用户
   - 关键词：高价值用户、重要用户、VIP用户

## 分析示例

### 示例1：数据概览

用户：帮我看看这份数据的基本情况

执行：
1. 询问数据文件路径
2. 使用 pandas 加载数据
3. 使用 ProjectMatcher 检测项目
4. 调用 DataAnalyzer.load_data() 和 get_summary()
5. 展示行数、列数、字段列表

### 示例2：指标计算

用户：分析 data/sample_data.xlsx，一共有多少个用户？

执行：
1. 使用 pandas 加载数据
2. 自动检测项目（匹配到 rednote_project）
3. 加载项目配置
4. 提取关键词：["用户"]
5. 调用 match_metric_by_keywords(["用户"]) 匹配指标
5a. 匹配到 "total_users" 和可能的其他用户相关指标
5b. 使用 AskUserQuestion 展示候选指标
6. 用户选择 "total_users"
7. 调用 analyzer.calculate_metric("total_users")
8. 输出结果：总用户数: 50

### 示例3：用户行为分析

用户：分析用户 user_0001 的行为链

执行：
1. 加载数据
2. 调用 analyzer.get_user_timeline("user_0001")
3. 按时间排序展示事件序列
4. 总结用户行为特征

### 示例4：多指标分析

用户：我想看看数据的活跃情况

执行：
1. 加载数据
2. 提取关键词：["活跃"]
3. 匹配到 "daily_active_users" 和 "user_activity_rate"
4. 用户选择要计算的指标
5. 计算并展示结果

### 示例5：创建新项目

用户：分析 new_business_data.xlsx

执行：
1. 加载数据
2. ProjectMatcher 未匹配到项目
3. 询问用户是否创建新项目
4. 用户确认
5. 询问项目名称和显示名称
6. 询问是否有表头说明文档
7. 使用 SchemaGenerator 生成配置
8. 创建项目配置文件
9. 加载新项目配置并进行分析

## 注意事项

1. **数据安全**：仅处理已脱敏的数据文件，不上传数据到云端
2. **性能考虑**：大数据量时建议先筛选再分析
3. **增量开发**：新的分析需求可以添加新的工具函数和指标配置
4. **用户交互**：对于模糊的需求，使用 AskUserQuestion 让用户选择
5. **多项目隔离**：每个项目有独立的配置文件，互不干扰
6. **自动匹配**：支持通过文件名和列特征自动识别项目
7. **Schema验证**：加载配置后自动验证数据结构是否符合定义
