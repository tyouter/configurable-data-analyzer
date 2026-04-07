# Trigger信号与数据字段深度关联分析报告

**生成时间**: 2026-04-07

---

## 一、事件匹配分析

### 统计概况

- **实际数据中的事件数**: 93
- **定义文件中的事件数**: 88
- **完全匹配的事件数**: 54
- **未匹配的事件数**: 39

### 完全匹配的事件

以下是同时在定义文件和实际数据中出现的事件:

- **discovery_page_post_card_cardshow** (212 条)

- **discovery_page_post_card_click** (11 条)

- **login_page_QRCode_Authentication** (18 条)

- **login_page_pageshow** (10 条)

- **other_profile_page_follow_button_click** (1 条)

- **poi_detail_page_navigation_button_click** (21 条)

- **poi_detail_page_navigation_popup_cancel_click** (1 条)

- **poi_detail_page_navigation_popup_confirm_click** (20 条)

- **poi_detail_page_post_card_cardshow** (108 条)

- **poi_detail_page_tel_btn_click** (1 条)

- **porsche_page_Map_POI_Category_cardshow** (20 条)

- **porsche_page_Map_POI_Category_click** (25 条)

- **porsche_page_Map_poi_Category_entry_click** (17 条)

- **porsche_page_Map_poi_card_cardshow** (2466 条)

- **porsche_page_Map_poi_card_click** (30 条)

- **porsche_page_recommend_post_card_cardshow** (272 条)

- **porsche_page_recommend_post_card_click** (22 条)

- **post_detail_page_POI_button_show** (58 条)

- **post_detail_page_Profile_Picture_Click** (3 条)

- **post_detail_page_ai_travel_guide_button_click** (15 条)

- **post_detail_page_ai_travel_guide_button_show** (31 条)

- **post_detail_page_back_button_click** (101 条)

- **post_detail_page_body_image_click** (5 条)

- **post_detail_page_body_image_swipe_for_next** (13 条)

- **post_detail_page_follow_button_click** (1 条)

- **post_detail_page_generated_travel_guide_button_click** (20 条)

- **post_detail_page_generated_travel_guide_button_show** (21 条)

- **post_detail_page_nickname_click** (1 条)

- **post_detail_page_pageshow** (216 条)

- **post_detail_page_post_like_click** (3 条)

- **post_detail_page_save_button_click** (2 条)

- **profile_page_like_tab_post_card_carshow** (12 条)

- **profile_page_like_tab_post_card_click** (1 条)

- **profile_page_liked_tab_click** (3 条)

- **profile_page_pageshow** (52 条)

- **profile_page_post_tab_click** (15 条)

- **profile_page_post_tab_post_card_carshow** (40 条)

- **profile_page_post_tab_post_card_click** (1 条)

- **profile_page_save_tab_click** (7 条)

- **profile_page_save_tab_post_card_carshow** (12 条)

- **profile_page_travel_guide_tab_trip_card_cardshow** (68 条)

- **profile_page_travel_guide_tab_trip_card_click** (3 条)

- **search_results_page_post_card_carshow** (448 条)

- **search_results_page_post_card_click** (54 条)

- **trival_guide_page_back_button_click** (29 条)

- **trival_guide_page_back_to_original_post_click** (3 条)

- **trival_guide_page_detail_tab_click** (12 条)

- **trival_guide_page_detail_tab_date_switch_click** (2 条)

- **trival_guide_page_detail_tab_poi_navigation_button_click** (13 条)

- **trival_guide_page_detail_tab_poi_navigation_popup_confirm_click** (18 条)

- **trival_guide_page_overview_tab_click** (2 条)

- **trival_guide_page_overview_tab_complete_trip_click** (5 条)

- **trival_guide_page_pageshow** (69 条)

- **trival_guide_page_share_icon_click** (5 条)

## 二、关键事件字段使用分析

### 📍 POI相关事件字段使用

POI相关事件总数: 2879 条

| 字段名 | 使用率 | 唯一值数 | 描述 |
|--------|--------|----------|------|
| rednote_poi_map_fullscreen | 88.9% | 2 | POI地图是否全屏显示 |
| rednote_poi_title | 97.8% | 614 | POI标题/名称 |
| rednote_poi_typ | 8.0% | 18 | POI类型代码 |
| rednote_poi_typ_nm | 67.2% | 182 | POI类型名称 |

### 📝 帖子相关事件字段使用

帖子相关事件总数: 1701 条

| 字段名 | 使用率 | 唯一值数 | 描述 |
|--------|--------|----------|------|
| rednote_post_num | 30.2% | 131 | 帖子编号 |
| rednote_post_title | 91.2% | 728 | 帖子标题 |
| rednote_post_typ | 98.9% | 2 | 帖子类型 |
| rednote_post_is_like | 0.2% | 1 | 帖子是否被点赞 |
| rednote_post_follow | 0.1% | 1 | 帖子关注状态 |
| rednote_post_is_save | 0.1% | 1 | 帖子是否被收藏 |
| rednote_post_is_op_rec | 17.3% | 1 | 帖子是否为运营推荐 |
| rednote_post_is_recuser | 17.3% | 1 | 帖子是否推荐用户 |

### 🧭 旅行指南相关事件字段使用

旅行指南相关事件总数: 327 条

| 字段名 | 使用率 | 唯一值数 | 描述 |
|--------|--------|----------|------|
| rednote_travel_guide_id | 70.0% | 25 | 旅行指南ID |
| rednote_travel_guide_title | 70.0% | 24 | 旅行指南标题 |
| rednote_travel_post_is_succ | 0.0% | 0 | 旅行帖子是否成功生成 |

## 三、数据价值分析

### 高价值字段识别

基于字段使用频率和业务价值，识别出以下高价值字段:

| 排名 | 字段名 | 使用率 | 唯一值数 | 业务价值 |
|------|--------|--------|----------|----------|
| 1 | rednote_poi_title | 43.1% | 614 | 🌟高 - POI名称，核心内容标识 |
| 2 | rednote_poi_map_fullscreen | 39.2% | 2 | 🌟高 - 地图全屏状态，影响用户体验 |
| 3 | rednote_poi_typ_nm | 29.6% | 182 | 🌟高 - POI类型，用于分类分析 |
| 4 | rednote_post_typ | 25.8% | 2 | 🌟高 - 帖子类型，内容分类 |
| 5 | rednote_post_title | 23.8% | 728 | 🌟高 - 帖子标题，内容分析基础 |
| 6 | rednote_post_num | 7.9% | 131 | 📊低 - 其他字段 |
| 7 | rednote_search_result_tab_title | 7.7% | 2 | ⭐中 - 搜索标签，搜索体验分析 |
| 8 | rednote_post_is_op_rec | 4.5% | 1 | ⭐中 - 运营推荐标识 |
| 9 | rednote_post_is_recuser | 4.5% | 1 | 📊低 - 其他字段 |
| 10 | rednote_poi_typ | 3.5% | 18 | 📊低 - 其他字段 |
| 11 | rednote_travel_guide_id | 3.5% | 25 | ⭐中 - AI旅行指南标识 |
| 12 | rednote_travel_guide_title | 3.5% | 24 | ⭐中 - 旅行指南标题 |
| 13 | rednote_prfl_typ | 2.2% | 2 | 📊低 - 其他字段 |
| 14 | rednote_user_logging_status | 0.3% | 4 | 📊低 - 其他字段 |
| 15 | rednote_post_is_like | 0.0% | 1 | 📊低 - 其他字段 |

## 四、业务洞察与建议

### 📍 地图全屏使用分析

POI地图全屏状态分布:

- **全屏模式**: 1775 次 (69.4%)
- **普通模式**: 783 次 (30.6%)

💡 **洞察**: 全屏模式使用率不高，可能存在使用障碍或用户习惯问题
💡 **建议**: 分析用户为什么更倾向于普通模式，优化全屏模式的引导和体验

### 🎯 POI类型分布

最热门的POI类型:

- **超市便利**: 113 次 (5.8%)
- **台球**: 80 次 (4.1%)
- **休闲娱乐**: 71 次 (3.7%)
- **棋牌室**: 70 次 (3.6%)
- **采摘园**: 64 次 (3.3%)
- **商场**: 57 次 (2.9%)
- **健身中心**: 43 次 (2.2%)
- **儿童乐园**: 42 次 (2.2%)
- **羽毛球**: 41 次 (2.1%)
- **露营地**: 39 次 (2.0%)

💡 **洞察**: POI类型分布反映了用户的主要兴趣点，可用于个性化推荐
💡 **建议**: 基于用户POI类型偏好，优化内容推荐算法

### 📝 帖子类型分布

帖子类型分布:

- **normal**: 1407 次 (83.6%)
- **video**: 276 次 (16.4%)

### 🧭 AI旅行指南使用分析

AI旅行指南相关事件: 229 次 (3.5%)

💡 **洞察**: 用户对AI旅行指南功能有使用，说明AI功能获得用户认可
💡 **建议**: 进一步优化AI旅行指南的生成质量和用户体验

## 五、总结

通过本次深度关联分析，我们发现:

1. **数据完整性高**: 核心业务字段的使用率普遍较高，数据采集质量良好
2. **POI功能核心化**: POI相关字段使用率最高，印证了POI是核心功能
3. **内容消费活跃**: 帖子相关字段使用率高，用户内容消费需求强烈
4. **AI功能有待提升**: 旅行指南使用率较低，有优化空间

建议重点关注POI地图体验优化和AI旅行指南功能增强。