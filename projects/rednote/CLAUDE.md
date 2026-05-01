# 小红书车载应用分析 (Rednote Analysis)

小红书车载数据分析项目，基于 ChatBI MCP Server 构建。

## 项目信息

- **project_id**: `rednote`
- **project_type**: `behavior_analysis`
- **数据源**: 小红书车载应用埋点数据

## 数据说明

**主数据文件**: `data/rednote20260319-20260412.xlsx`
- 时间范围: 2026-03-19 ~ 2026-04-12
- 事件数: 65,722
- 用户数: 297

**参考文档**:
- `data/rednote KPI definition_20260323.xlsx` — KPI 定义（15 个指标）
- `data/Rednote tracking data stracture_20260331.xlsx` — 数据字典（48 个字段）
- `data/Rednote dashboard V1.0 5-30 requirements.xlsx` — Dashboard 需求文档

**数据清洗规则**:
- 过滤 `rednote_poi_title = 'akimbo(西丽店)'` (测试事件)

## 业务上下文

### 产品形态

小红书车载应用集成在保时捷车机系统中，提供本地生活内容推荐和 POI 导航功能。用户通过发现页浏览笔记、通过 Porsche+ 页查看保时捷专属内容、通过 POI 详情页发起导航。

### 核心用户路径

```
发现页/Porsche+页 → 笔记详情页 → POI详情页 → 发起导航
                                 ↘ AI旅行指南
```

### 关键事件

| 事件 | 说明 | 分析用途 |
|------|------|----------|
| `discovery_page_post_card_cardshow/click` | 发现页帖子曝光/点击 | CTR 分析 |
| `porsche_page_recommend_post_card_cardshow/click` | Porsche+推荐帖子曝光/点击 | CTR 分析 |
| `post_detail_page_POI_button_show` | POI 按钮展示 | 识别带 POI 帖子 |
| `poi_detail_page_navigation_button_click` | 导航按钮点击 | O2O 转化核心指标 |
| `post_detail_page_ai_travel_guide_button_click` | AI路书按钮点击 | AI 功能使用率 |

### 关键字段

| 字段 | 说明 | 值域 |
|------|------|------|
| `rednote_post_type` | 帖子类型 | normal(图文), video(视频) |
| `rednote_post_num` | 帖子顺位 | 1, 2, 3, ... |
| `rednote_post_is_operational_rec` | 是否运营位 | true/false |
| `rednote_poi_type` | POI 分类 | 多种类型代码 |
| `rednote_poi_title` | POI 名称 | 地点名称字符串 |

## 预定义指标

### Discovery 页指标 (7个)
- CTR 趋势、顺位分布、类型分布
- POI 帖子比例、导航转化、AI 路书转化
- 漏斗分析

### Porsche+ 页指标 (13个)
- 活跃率、人均打开次数、CTR
- 顺位分布、运营位对比、类型分布
- POI 转化、地图用户、漏斗分析

### O2O 指标 (10个)
- 搜索用户趋势、活跃率、人均次数
- POI 类型分布、时间分布、周末 vs 工作日
- AI 路书对比、运营位视频占比

## 分析示例

### 示例查询
- "发现页每天的帖子点击率趋势"
- "导航用户 POI 类型分布"
- "使用 AI 路书和不使用用户的导航率对比"

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
