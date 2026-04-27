# Rednote Data Analyzer

小红书车载数据分析BI系统，支持对话式查询、Dashboard管理、业务指标计算。

## 项目结构

```
.
├── bi/                         # BI系统核心
│   ├── agent.py               # LLM Agent (DeepSeek V4)
│   ├── app.py                 # FastAPI后端 (端口8501)
│   ├── static/index.html      # 前端界面 (ECharts图表)
│   ├── semantic.yaml          # 语义层定义 (事件、字段、指标)
│   ├── dashboard_store.py     # Dashboard持久化 (JSON)
│   ├── data_layer.py          # 数据加载与预处理
│   └── dashboards/            # Dashboard存储目录
│       └── *.json             # Dashboard配置文件
│
├── tools/                     # 分析工具
│   ├── calculate_metrics.py   # 业务指标计算脚本 (30个指标)
│   ├── generate_dashboard_via_api.py  # 通过API生成Dashboard
│   ├── analyzer.py            # 数据分析器
│   ├── kpi_replica_analysis*.py  # KPI复刻分析
│   ├── full_deep_analysis*.py     # 深度分析
│   └── ...                    # 其他分析工具
│
├── data/                      # 数据目录
│   └── rednote/               # Rednote数据
│       └── rednote20260319-20260412.xlsx  # 主数据文件
│
├── skills/                    # Claude Agent技能
└── requirements.txt           # Python依赖
```

## 核心功能

### 1. 对话式数据查询 (BI Chat)

基于DeepSeek V4推理模型的LLM Agent，支持：
- 自然语言查询转SQL
- 交互式澄清（对模糊问题提问）
- 流式输出（推理过程实时显示）
- SQL执行与结果渲染

**示例查询**：
- "发现页每天的帖子点击率趋势"
- "导航用户POI类型分布"
- "使用AI路书和不使用用户的导航率对比"

### 2. Dashboard管理

多Dashboard系统支持：
- Dashboard创建/切换/删除
- 图表持久化保存
- 右键菜单：复制图表、下载PNG
- 配色方案选择（Ferrari、Porsche、Dark等）

### 3. Business指标计算 (`tools/calculate_metrics.py`)

直接计算30个业务指标，包含完整审计信息：

**Discovery页指标 (7个)**：
- CTR趋势、顺位分布、类型分布
- POI帖子比例、导航转化、AI路书转化
- 漏斗分析

**Porsche+页指标 (13个)**：
- 活跃率、人均打开次数、CTR
- 顺位分布、运营位对比、类型分布
- POI转化、地图用户、漏斗分析

**O2O指标 (10个)**：
- 搜索用户趋势、活跃率、人均次数
- POI类型分布、时间分布、周末vs工作日
- AI路书对比、运营位视频占比

### 4. 审计追踪

每个图表包含完整审计信息：
- `data_source`: 文件、表、扫描行数、日期范围
- `calculation_logic`: 计算逻辑说明
- `sql_explanation`: SQL步骤说明
- `columns_used`: 字段列表（含义、角色、样本）
- `filters_applied`: 筛选条件

### 5. 前端特性

- ECharts图表渲染（line、bar、pie、funnel、table）
- 深色主题配色方案
- X轴标签旋转、日期格式化
- 漏斗图顺序保持
- 图表布局防重叠

## 快速启动

```bash
# 启动BI服务器
python bi/app.py
# 访问 http://localhost:8501

# 计算业务指标（生成Dashboard）
python tools/calculate_metrics.py
```

## 数据说明

**主数据文件**: `data/rednote/rednote20260319-20260412.xlsx`
- 时间范围: 2026-03-19 ~ 2026-04-12
- 事件数: 65,722
- 用户数: 297

**数据清洗规则**:
- 过滤 `rednote_poi_title = 'akimbo(西丽店)'` (测试事件)

**关键事件**:
- `discovery_page_post_card_cardshow/click` - 发现页帖子展示/点击
- `porsche_page_recommend_post_card_cardshow/click` - Porsche+页帖子展示/点击
- `post_detail_page_POI_button_show` - POI按钮显示（识别带POI帖子）
- `poi_detail_page_navigation_button_click` - 导航按钮点击
- `post_detail_page_ai_travel_guide_button_click` - AI路书按钮点击

**关键字段**:
- `rednote_post_type`: 帖子类型 (normal图文, video视频)
- `rednote_post_num`: 帖子顺位
- `rednote_post_is_operational_rec`: 是否运营位
- `rednote_poi_type`: POI分类
- `rednote_poi_title`: POI名称

## 依赖

```
pandas>=2.0.0
openpyxl>=3.1.0
pyyaml>=6.0
duckdb
fastapi
uvicorn
requests
```

## 开发历史

| Commit | 功能 |
|--------|------|
| eb4975e | Business指标计算工具 + 完整审计信息 |
| ea186d4 | Business/Strategy看板生成器工具 |
| af2f40e | 右键菜单复制/下载图表 |
| 6ed3984 | Ferrari品牌配色方案 |
| 2029b7c | 完整主题配置 |
| 64b5526 | 配色方案选择器 |
| d8c94dd | LLM生成专业BI图表标题 |
| aebb7e0 | DeepSeek V4推理模型 + 流式输出 + 交互式澄清 |
| cb1a6ab | Rednote BI Agent系统 |

## API端点

| 端点 | 功能 |
|------|------|
| `POST /api/query/stream` | 流式查询（SSE） |
| `GET /api/dashboards` | Dashboard列表 |
| `POST /api/dashboards` | 保存图表到Dashboard |
| `POST /api/dashboards/create` | 创建新Dashboard |
| `DELETE /api/dashboards/{id}` | 删除Dashboard |
| `GET /api/schema` | 获取数据Schema |
| `GET /api/metrics` | 获取指标定义 |

# currentDate
Today's date is 2026-04-28.