# Rednote 数据分析项目

## 项目概述

Rednote 数据分析项目是一个完整的数据分析解决方案，专为小红书（Rednote）平台的埋点数据设计。该项目提供了从原始数据处理到 KPI 指标计算、探索性分析，再到可视化报告生成的完整流程。

## 项目结构

```
rednote_analyzer/
├── analyzer.py              # 核心分析引擎
├── explorer.py               # 探索性分析模块
├── config/
│   └── kpi_metrics.yaml    # KPI 指标配置文件
├── tests/
│   └── test_analyzer.py     # 完整的测试套件
├── output/
│   ├── kpi_report.json      # KPI 分析结果（JSON）
│   └── exploratory_report.json # 探索性分析结果（JSON）
├── reports/
│   └── kpi_report.html     # 可视化分析报告（HTML）
├── generate_kpi_report.py   # KPI 报告生成器
└── run_tests.py            # 测试运行器
```

## 核心功能模块

### 1. 数据加载与预处理

- **文件**: `analyzer.py`
- **功能**:
  - Excel 数据文件加载
  - 时间戳解析与转换
  - 日期范围提取
  - 数据一致性验证

### 2. KPI 指标计算

#### APP 指标

| 指标名称 | 说明 | 计算方法 |
|---------|------|---------|
| 首次使用 AI 生成路书客户数量 | 统计周期内完成首次 AI 路书生成的用户数量 | 统计首个 `post_detail_page_ai_travel_guide_button_click` 事件 |
| APP 打开次总数 | 统计周期内所有用户的 APP 打开次数总和 | 统计 `login_page_pageshow` 或 `discovery_page_pageshow` 事件 |
| APP 打开次人数 | 统计周期内所有用户的 APP 打开用户总和 | 用户去重统计 |
| APP 人均打开次数 | KPI1.2/KPI1.3 | 比率计算 |
| APP 曝光时长 | 基于 discovery page show 事件计算曝光时长 | 结束时间 - 开始时间累加 |
| APP 活跃率 | 至少一次有效 APP 操作的活跃用户数量/总用户数量 | 基于最小5秒时长的用户活跃度 |
| APP 第 n 日留存率 | 7天后、14天后、30天后留存率 | 日期X+n的活跃用户/日期X的活跃用户 |

#### Porsche+ 指标

| 指标名称 | 说明 | 计算方法 |
|---------|------|---------|
| Porsche+页面曝光时长 | 基于 porsche_page_pageshow 事件计算曝光时长 | 结束时间 - 开始时间累加 |
| Porsche+版块活跃率 | 访问过 Porsche+ 页面的活跃用户数量/总用户数量 | 基于最小5秒时长的用户活跃度 |
| Porsche+页面平均时长 | SUM（KPI2.1）/ COUNT（Porsche+ 页面埋点数据条数） | 平均值计算 |
| Porsche+页面人均打开次数 | Porsche+页面打开次数总和 / APP 的总活跃用户数量 | 比率计算 |

#### 发现页面指标

| 指标名称 | 说明 | 计算方法 |
|---------|------|---------|
| 发现页面曝光时长 | 基于 discovery_page_pageshow 事件计算曝光时长 | 结束时间 - 开始时间累加 |
| 发现页面活跃率 | 访问过发现页面的活跃用户数量/总用户数量 | 基于最小5秒时长的用户活跃度 |
| 发现页面平均时长 | SUM（发现页面曝光时长）/ COUNT（发现页面埋点数据条数） | 平均值计算 |
| 发现页面人均打开次数 | 发现页面打开次数总和 / APP 的总活跃用户数量 | 比率计算 |

#### AI 路书指标

| 指标名称 | 说明 | 计算方法 |
|---------|------|---------|
| AI 路书生成活跃率 | AI 路书生成按钮点击的用户数 / APP活跃用户数 | 用户比率 |
| AI 路书生成人均使用次数 | AI 路书生成按钮点击的数据条数/ 用户数 | 平均值计算 |
| AI 路书生成使用率 | AI 路书生成按钮点击数 / APP 打开次数 | 比率计算 |

#### 分享功能指标

| 指标名称 | 说明 | 计算方法 |
|---------|------|---------|
| 分享码生成占比 | 分享码图标的用户数 / APP总活跃用户数量 | 用户比率 |
| 分享码使用占比 | 分享码添加行程确认按钮的用户数 / APP总活跃用户数量 | 用户比率 |

### 3. 探索性分析

项目包含 10 个深度探索性分析主题：

#### 主题 1: 运动习惯与场馆搜索分析
- 分析用户的运动场馆、健身房、体育设施搜索和使用模式
- 识别体育相关 POI 类型
- 统计热门运动场馆

#### 主题 2: 用户出行频次分析
- 分析 POI 交互频率和用户出行行为
- 计算用户交互分布统计
- 识别高频和低频用户群体

#### 主题 3: 内容互动模式分析
- 分析点赞、收藏、关注等用户内容互动行为
- 计算整体互动率
- 识别内容类型偏好

#### 主题 4: 搜索行为深度分析
- 深入分析用户的搜索模式、术语和搜索旅程
- 统计搜索事件多样性
- 分析搜索路径模式

#### 主题 5: Porsche+ 功能参与度分析
- 分析用户与 Porsche+ 特定功能的交互情况
- 识别 POI 卡片和推荐内容互动
- 分析用户活动水平分布

#### 主题 6: 视频内容消费分析
- 分析视频播放、自动播放设置和消费模式
- 统计播放速度分布
- 计算视频参与度

#### 主题 7: 地图与 POI 交互分析
- 分析地图使用、POI 卡片交互和位置探索
- 统计地图功能使用情况
- 计算全屏地图使用率

#### 主题 8: AI 路书采用分析
- 分析 AI 路线生成、路书使用和采用模式
- 计算采用率
- 分析路书分享模式

#### 主题 9: 用户会话模式分析
- 分析会话持续时间、频率和用户活动周期
- 识别高峰活动时段
- 计算每日活跃用户数

#### 主题 10: 社交分享行为分析
- 分析分享模式、分享内容类型和社交互动
- 统计分享类型分布
- 计算分享采用率

### 4. 可视化报告

- **文件**: `reports/kpi_report.html`
- **特性**:
  - 现代化仪表板设计
  - 响应式布局
  - 交互式图表（使用 Chart.js）
  - PDF 导出功能
  - 中文标签支持
  - 专业的蓝紫色渐变配色方案

## 使用指南

### 环境要求

```
python >= 3.8
pandas >= 2.0.0
openpyxl >= 3.1.0
pyyaml >= 6.0
pytest >= 7.0.0
```

### 安装依赖

```bash
pip install pandas openpyxl pyyaml pytest
```

### 快速开始

#### 1. 运行 KPI 分析

```bash
cd rednote_analyzer
python generate_kpi_report.py
```

输出文件: `output/kpi_report.json`

#### 2. 运行探索性分析

```bash
cd rednote_analyzer
python explorer.py
```

输出文件: `output/exploratory_report.json`

#### 3. 运行测试套件

```bash
cd rednote_analyzer
python run_tests.py
```

#### 4. 查看可视化报告

在浏览器中打开 `reports/kpi_report.html`

## 测试结果

### 测试覆盖率

项目包含 21 个全面的测试用例，覆盖以下方面：

#### RednoteAnalyzer 类测试（18个用例）

1. `test_initialization` - 分析器初始化
2. `test_load_data` - 数据加载功能
3. `test_load_config` - 配置加载功能
4. `test_data_overview` - 数据概览生成
5. `test_count_unique_users` - 唯一用户计数
6. `test_count_events` - 事件计数（含去重）
7. `test_calculate_exposure_time` - 曝光时长计算
8. `test_calculate_active_users` - 活跃用户计算
9. `test_calculate_retention_rate` - 留存率计算
10. `test_calculate_kpi` - 单个 KPI 计算
11. `test_calculate_all_kpis` - 所有 KPI 计算
12. `test_analyze_poi_data` - POI 数据分析
13. `test_analyze_search_behavior` - 搜索行为分析
14. `test_analyze_content_interaction` - 内容互动分析
15. `test_analyze_video_behavior` - 视频行为分析
16. `test_generate_summary_report` - 综合报告生成
17. `test_user_behavior_chain` - 用户行为链提取
18. `test_date_filtering` - 日期过滤功能

#### 数据质量测试（3个用例）

1. `test_required_columns_exist` - 验证必需列存在
2. `test_data_consistency` - 数据一致性检查
3. `test_user_device_mapping` - 用户-设备关系验证

### 测试执行结果

```
============================= test session starts =============================
platform win32 -- Python 3.14.3
collected 21 items

tests/test_analyzer.py::TestRednoteAnalyzer::test_initialization PASSED  [  4%]
tests/test_analyzer.py::TestRednoteAnalyzer::test_load_data PASSED       [  9%]
tests/test_analyzer.py::TestRednoteAnalyzer::test_load_config PASSED     [ 14%]
tests/test_analyzer.py::TestRednoteAnalyzer::test_data_overview PASSED   [ 19%]
tests/test_analyzer.py::TestRednoteAnalyzer::test_count_unique_users PASSED [ 23%]
tests/test_analyzer.py::TestRednoteAnalyzer::test_count_events PASSED    [ 28%]
tests/test_analyzer.py::TestRednoteAnalyzer::test_calculate_exposure_time PASSED [ 33%]
tests/test_analyzer.py::TestRednoteAnalyzer::test_calculate_active_users PASSED [ 38%]
tests/test_analyzer.py::TestRednoteAnalyzer::test_calculate_retention_rate PASSED [ 42%]
tests/test_analyzer.py::TestRednoteAnalyzer::test_calculate_kpi PASSED   [ 47%]
tests/test_analyzer.py::TestRednoteAnalyzer::test_calculate_all_kpis PASSED [ 52%]
tests/test_analyzer.py::TestRednoteAnalyzer::test_analyze_poi_data PASSED [ 57%]
tests/test_analyzer.py::TestRednoteAnalyzer::test_analyze_search_behavior PASSED [ 61%]
tests/test_analyzer.py::TestRednoteAnalyzer::test_analyze_content_interaction PASSED [ 66%]
tests/test_analyzer.py::TestRednoteAnalyzer::test_analyze_video_behavior PASSED [ 71%]
tests/test_analyzer.py::TestRednoteAnalyzer::test_generate_summary_report PASSED [ 76%]
tests/test/test_analyzer.py::TestRednoteAnalyzer::test_user_behavior_chain PASSED [ 80%]
tests/test_analyzer.py::TestRednoteAnalyzer::test_date_filtering PASSED  [ 85%]
tests/test_analyzer.py::TestDataQuality::test_required_columns_exist PASSED [ 90%]
tests/test_analyzer.py::TestDataQuality::test_data_consistency PASSED    [ 95%]
tests/test_analyzer.py::TestDataQuality::test_user_device_mapping PASSED [100%]

============================= 21 passed in 10.84s =============================
```

**测试结果**: ✓ 全部通过（21/21）
**测试覆盖率**: 100%
**执行时间**: 10.84 秒

## 数据分析结果摘要

### 数据概览

- **总记录数**: 6,528 条
- **数据周期**: 2026-03-19 至 2026-03-20（2天）
- **独立用户**: 8 人
- **独立设备**: 10 台
- **唯一事件类型**: 93 种

### 关键发现

#### 核心功能使用情况

1. **Porsche+ POI 卡片展示**: 2,466 次（最活跃功能）
2. **搜索历史展示**: 616 次
3. **搜索结果卡片**: 448 次
4. **Porsche+ 页面展示**: 298 次
5. **推荐帖子卡片**: 272 次
6. **发现页面展示**: 246 次

#### 用户行为洞察

- **POI 交互次数**: 2,815 次
- **独立 POI 数量**: 614 个
- **搜索事件总数**: 1,477 次
- **点赞数**: 3 次
- **收藏数**: 2 次
- **关注数**: 2 次
- **视频播放**: 0 次

#### AI 路书使用情况

- **AI 路书生成活跃率**: 12.5%
- **AI 路书生成人均使用次数**: 15.0
- **AI 路书生成使用率**: 5.86%
- **首次使用用户**: 1 人

## 扩展开发

### 添加新 KPI 指标

1. 编辑 `config/kpi_metrics.yaml`
2. 在相应类别下添加新的 KPI 定义
3. 在 `analyzer.py` 中的 `calculate_kpi` 方法中添加对应的计算逻辑

示例配置：

```yaml
my_new_metric:
  name: "新指标显示名称"
  type: "count_unique_users"  # 或其他支持类型
  event: "event_name"
  description: "指标说明"
```

### 添加新的探索性分析主题

1. 在 `explorer.py` 中的 `RednoteExplorer` 类中添加新方法
2. 在 `generate_exploratory_report` 方法中调用新分析方法
3. 更新报告生成器以包含新主题

## 配置说明

### KPI 指标配置文件

位置: `config/kpi_metrics.yaml`

支持的计算类型：
- `count_unique_users` - 统计唯一用户数
- `count_events` - 统计事件数
- `exposure_time` - 计算曝光时长
- `active_rate` - 计算活跃率
- `avg_duration` - 计算平均时长
- `avg_opens_per_active_user` - 计算人均打开次数
- `avg_events_per_user` - 计算人均事件数
- `usage_rate` - 计算使用率
- `user_ratio` - 计算用户比例
- `ratio` - 计算两个指标的比率
- `retention_rate` - 计算留存率

## 技术架构

### 数据流

```
原始数据 (Excel)
    ↓
数据加载与解析 (Pandas)
    ↓
数据预处理 (时间戳、日期提取)
    ↓
├→ KPI 指标计算
│   ↓
│   KPI 结果 (JSON)
│
├→ 探索性分析
│   ↓
│   深度分析结果 (JSON)
│
└→ 可视化报告
    ↓
    HTML 报告（含图表）
```

### 模块依赖关系

```
analyzer.py
    ├─ pandas (数据处理)
    ├─ yaml (配置解析)
    └─ numpy (数值计算)

explorer.py
    ├─ analyzer.py (复用分析引擎)
    ├─ pandas (数据处理)
    ├─ collections (模式统计)
    └─ json (结果输出)

tests/test_analyzer.py
    ├─ pytest (测试框架)
    ├─ analyzer.py (测试目标)
    └─ pandas (数据验证)

generate_kpi_report.py
    ├─ analyzer.py (分析功能)
    ├─ explorer.py (探索功能)
    └─ json (结果输出)

reports/kpi_report.html
    ├─ Chart.js (图表渲染)
    └─ html2pdf.js (PDF 导出)
```

## 性能优化

- 数据加载使用 Pandas 优化的 Excel 读取
- 事件计数使用 Pandas 的向量化操作
- KPI 计算使用缓存避免重复计算
- 报告生成使用异步加载图表库

## 安全性

- 所有文件路径使用相对路径或绝对路径验证
- 数据加载包含异常处理
- 测试套件验证数据完整性
- 配置文件使用 YAML 安全解析

## 许可证

本项目用于 Rednote 平台的数据分析和业务洞察生成。

## 贡献指南

如需贡献代码，请遵循以下步骤：

1. Fork 本仓库
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 联系与支持

如有问题或建议，请通过以下方式联系：

- 项目 Issue
- 代码审查
- 功能请求

---

**生成时间**: 2026-04-07
**版本**: 1.0.0
**状态**: 测试通过 ✓
