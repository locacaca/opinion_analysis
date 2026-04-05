# 技术文档

## 1. 平台内容采集策略

### 1.1 主流程入口与接口边界

主流程后端入口位于 `python/backend/app.py`，主流程实际对外暴露的分析接口为：

- `GET /health`
- `POST /api/analyze`

其中，`POST /api/analyze` 的请求模型为 `AnalyzeKeywordRequest`，核心字段包括：

- `keyword`
- `language`
- `output_language`
- `limit_per_source`
- `total_limit`
- `sources`
- `source_weights`
- `youtube_mode`

接口进入后，会直接调用 `python/opinion_engine/pipeline.py` 中的 `analyze_keyword(...)`。这意味着采集策略不是散落在多个接口里，而是集中在一个主流程编排函数中统一控制。

主流程调用链可以概括为：

1. `app.py` 中的 `analyze(...)`
2. `pipeline.py` 中的 `analyze_keyword(...)`
3. `_normalize_sources(...)`
4. `_normalize_youtube_mode(...)`
5. `_resolve_source_limits(...)`
6. `_build_spiders(...)`
7. `_collect_from_spider(...)`
8. `clean_opinion_records(...)`
9. `OpinionStorage.save_cleaned_records(...)`
10. `OpinionAnalyzer.analyze_records(...)`

这一组织方式的价值在于：

- 接口层只负责参数校验和异常转换
- 主流程编排统一决定平台选择、抓取配额、清洗、入库和分析顺序
- 平台采集实现与主流程解耦，后续扩展新平台时不需要改动接口协议

### 1.2 主流程中的采集顺序

`analyze_keyword(...)` 是整条链路的总控函数，当前执行顺序如下：

1. `_create_monitor(...)`
   - 创建一次分析任务的监控对象
   - 初始化 `started_at`、`status`、`stages`

2. `OpinionStorage.initialize()`
   - 初始化数据库表结构
   - 必要时补齐 `cleaned_records` 的新增列

3. `OpinionStorage.create_run(...)`
   - 在 `collection_runs` 表中创建本轮任务
   - 生成 `run_id`

4. `_normalize_sources(...)`
   - 将传入的平台列表统一规整为 `youtube`、`reddit`、`x`
   - 去重并过滤非法值

5. `_normalize_youtube_mode(...)`
   - 统一为 `official_api` 或 `headless_browser`

6. `_resolve_source_limits(...)`
   - 根据 `total_limit` 和 `source_weights` 计算每个平台的抓取上限

7. `_build_spiders(...)`
   - 实例化各个平台 Spider

8. `_collect_from_spider(...)`
   - 并发执行每个平台的 `fetch(...)`
   - 单个平台失败不会直接中断整轮流程

9. `clean_opinion_records(...)`
   - 对抓取结果做统一清洗
   - 当前只过滤空内容和明显乱码

10. `OpinionStorage.save_cleaned_records(...)`
    - 将清洗后内容写入 `cleaned_records`

11. `OpinionStorage.load_run_records(...)`
    - 按 `run_id` 读出当前轮次记录

12. `OpinionAnalyzer.analyze_records(...)`
    - 将整轮数据送入大模型

13. `_compute_heat_score(...)`
    - 计算热度分数

14. `OpinionStorage.complete_run(...)`
    - 回写摘要、分数、来源统计和错误信息

15. 返回响应 JSON
    - 供前端渲染统计、观点、摘要、进度与思维导图

该顺序体现了一个关键原则：先固定任务轮次，再采集、清洗、入库，最后分析。这样无论主流程成功还是失败，都能围绕 `run_id` 回溯整轮过程。

### 1.3 平台选择与实例化策略

平台选择与实例化都收敛在 `pipeline.py` 中。

平台标准化函数：

- `_normalize_sources(...)`

平台实例化函数：

- `_build_spiders(...)`

当前映射关系如下：

- `youtube -> YouTubeTranscriptSpider`
- `reddit -> RedditSearchSpider`
- `x -> XSearchSpider`

实例化阶段还会注入平台运行参数。例如 `RedditSearchSpider` 会读取代理、无头模式和慢速模式相关环境变量；`YouTubeTranscriptSpider` 会读取接口重试次数、字幕抓取重试次数、是否启用 `pytube` 兜底等参数。

这种设计的优点包括：

- 平台扩展点明确
- 平台差异隐藏在 Spider 内部
- 主流程只关心“需要哪些平台”和“每个平台抓多少”

### 1.4 平台配额分配策略

平台配额分配由 `pipeline.py` 中的两个函数负责：

- `_resolve_source_limits(...)`
- `_normalize_source_weight_value(...)`

当前权重映射规则如下：

- `low = 1`
- `medium = 2`
- `high = 3`

当 `total_limit` 为空时：

- 每个平台直接使用 `limit_per_source`

当 `total_limit` 有值时：

1. 将平台权重转换为数值
2. 计算每个平台的理论比例
3. 先取整数部分形成基础分配
4. 再按余数从大到小补齐剩余额度
5. 尽量保证每个启用平台至少获得一个名额

例如：

- 平台：`youtube`、`reddit`
- 总量：`20`
- 权重：`youtube=high`、`reddit=medium`

则后端会得到接近 `12 : 8` 的分配结果。

这一策略解决的是“总抓取量固定但希望重点平台多拿配额”的问题。前端传的是抽象权重，后端落地为可执行抓取上限，避免了前端直接控制每个平台精确数量所带来的配置复杂度。

### 1.5 YouTube 平台采集策略

YouTube 平台实现位于 `python/opinion_engine/spiders/youtube.py`，核心类为 `YouTubeTranscriptSpider`。

核心函数包括：

- `fetch(...)`
- `_collect_video_details_and_transcripts(...)`
- `_search_videos(...)`
- `_fetch_video_metadata_batch(...)`
- `_enrich_video_details(...)`
- `_fetch_transcripts(...)`
- `_fetch_transcript_payload(...)`
- `_build_opinion_records_from_youtube_items(...)`
- `_build_single_opinion_record_from_youtube_video(...)`

#### 1.5.1 搜索入口策略

`_search_videos(...)` 使用 YouTube 官方搜索接口：

- `https://www.googleapis.com/youtube/v3/search`

主要请求参数包括：

- `q`
- `type=video`
- `order=relevance`
- `maxResults`
- `publishedAfter`
- `relevanceLanguage`
- `videoCaption`

当前策略特点如下：

- 采用关键词检索，而不是按频道固定抓取
- 结果按相关度排序
- 最多翻页 5 次
- 通过 `seen_video_ids` 去重
- 可根据 `publishedAfter` 限制最近时间窗口
- 可通过 `strict_captions_only` 强制要求有字幕

这说明 YouTube 采集不是单纯“搜一页就结束”，而是一个带翻页、去重、时间过滤和字幕过滤的分层检索过程。

#### 1.5.2 元数据补全策略

搜索接口返回的视频信息并不总是足够，因此 `_search_videos(...)` 在拿到搜索结果后，会继续调用：

- `_fetch_video_metadata_batch(...)`

该函数访问：

- `https://www.googleapis.com/youtube/v3/videos`

批量补全以下字段：

- `title`
- `channel_title`
- `description`
- `publish_date`
- `views`
- `length_seconds`
- `thumbnail_url`

如果官方接口返回的元数据仍不完整，`_enrich_video_details(...)` 会尝试使用 `pytube` 做兜底补全。也就是说，YouTube 平台的元数据策略是“双层补全”：

1. 官方搜索接口给出初始结果
2. 官方视频详情接口补全核心元数据
3. 必要时再用 `pytube` 做补充

#### 1.5.3 字幕与转写策略

字幕抓取由 `_fetch_transcripts(...)` 调用 `_fetch_transcript_payload(...)` 完成。真正的字幕接口调用为：

- `YouTubeTranscriptApi.get_transcript(...)`

字幕语言优先级由 `_preferred_transcript_languages(...)` 控制：

- 中文场景优先：`zh-Hans`、`zh-Hant`、`zh`、`en`
- 英文场景优先：`en`、`en-US`、`en-GB`、`zh`、`zh-Hans`

该策略的目标不是只取单语言，而是先按项目设定语言取首选字幕，再允许退回到其它可用语言，减少“搜到视频但无可用文本”的情况。

字幕阶段还包含两个关键保护：

- `_sleep_before_transcript_request()`：在字幕请求前插入随机停顿，降低高频访问风险
- `_call_with_retries(...)`：对可重试错误进行有限重试

#### 1.5.4 记录构造策略

YouTube 单条记录由 `_build_single_opinion_record_from_youtube_video(...)` 构造。当前记录正文并不是只保留标题，而是会拼接：

- 标题
- 字幕文本
- 评论摘要
- 视频描述

拼接后的内容进入统一字段 `content`，同时在 `metadata` 中保留：

- `publish_date`
- `video_id`
- `video_url`
- `has_transcript`
- `title`
- `description_text`
- `transcript_text`
- `comments_text`
- `fetch_error`
- `views`
- `length_seconds`
- `thumbnail_url`

这种设计的工程价值是：

- 前端展示可以直接使用 `content`
- 大模型分析时可以使用更完整的上下文
- 数据库存储时仍保留细颗粒度字段，便于后续调试和扩展

#### 1.5.5 YouTube 平台的现实约束

YouTube 当前的主要现实约束包括：

- 官方接口存在配额与频率限制
- 高频搜索和元数据拉取容易触发 `429`
- 字幕接口成功率并不恒定
- 无字幕视频只能退化为元数据分析
- 时间窗口过窄时，低热度关键词可能抓不满配额

对应的工程应对方式包括：

- 提供 `official_api` 与 `headless_browser` 双模式
- 对接口错误做有限重试
- 使用元数据兜底而不是直接整条丢弃
- 在响应中回传 `source_errors` 与各平台统计

### 1.6 Reddit 平台采集策略

Reddit 平台实现位于 `python/opinion_engine/spiders/reddit_spider.py`，核心类为 `RedditSearchSpider`。

核心函数包括：

- `fetch(...)`
- `_collect_search_results(...)`
- `_build_search_url(...)`
- `_extract_page_error(...)`
- `_extract_result_page(...)`
- `_fetch_post_detail(...)`
- `_extract_comment_snippets(...)`
- `_normalize_reddit_url(...)`

#### 1.6.1 搜索入口选择

当前 Reddit 抓取使用的是：

- `old.reddit.com/search`

而不是新版站点。

搜索地址由 `_build_search_url(...)` 构造，默认参数为：

- `q=关键词`
- `sort=hot`
- `t=all`

选择旧站的核心原因不是界面偏好，而是结构更稳定、元素更容易定位、静态内容比例更高，更适合 Playwright 自动化提取。

#### 1.6.2 结果页采集策略

`_collect_search_results(...)` 负责遍历结果页，主要流程为：

1. 启动 Playwright 浏览器
2. 打开旧版搜索页
3. 检查页面是否处于错误态
4. 提取当前页结果
5. 跟随 `next-button` 进入下一页
6. 达到抓取上限或出错后结束

该函数内部包含多个保护点：

- `seen_links`：避免同一帖子重复入选
- `collection_deadline_epoch`：在共享截止时间到达后及时停止
- `max_page_error_retries = 3`：页面错误时允许有限重试
- `raise_on_page_error`：调试与主流程下使用不同错误策略

#### 1.6.3 结果过滤与正文补全

`_extract_result_page(...)` 会先从搜索结果页提取：

- 标题
- 摘要
- 原帖链接
- 子版块
- 作者
- 发布时间
- 分数
- 评论数

然后通过 `_fetch_post_detail(...)` 再访问帖子详情页，补全：

- 正文内容
- 评论片段

在进入结果集前，会做多层过滤：

- `_looks_like_promoted_result(...)`
  - 过滤明显广告与推广结果

- `_matches_keyword_on_search_result(...)`
  - 要求标题、摘要或子版块先满足关键词命中

- `_matches_keyword_strict(...)`
  - 在详情页内容补全后，再执行更严格的关键词命中判断

这意味着 Reddit 采集不是“搜到就收”，而是“搜索页初筛 + 详情页复筛”的双重门控模式。

#### 1.6.4 评论摘要策略

评论提取由 `_extract_comment_snippets(...)` 完成。当前策略包括：

- 只截取有限数量的高优先评论
- 控制字符预算
- 控制行数预算
- 过滤 `[deleted]`、`[removed]`
- 跳过噪声文本

返回结果会写入 `comments_text`，后续参与大模型分析。

#### 1.6.5 Reddit 平台的现实约束

当前 Reddit 平台的主要局限包括：

- 新版页面结构复杂且动态加载较多
- 反爬与封锁信号更频繁
- 搜索页、详情页、评论区都可能在不同阶段失败
- 分页结果并不保证足量命中关键词

因此当前工程选择的是“旧站优先、稳定优先、结构优先”的策略，而不是追求新版页面更丰富的视觉信息。

### 1.7 X 平台策略

X 平台位于 `python/opinion_engine/spiders/x_stub.py`。当前状态为：

- 已对齐统一 Spider 接口
- 已能纳入平台选择与配额分配
- 但稳定采集链路仍未达到与 YouTube、Reddit 同等级别

因此在主流程中，当前实际可依赖的平台仍然是：

- `YouTube`
- `Reddit`

X 的存在更多是为了保留统一扩展位，避免后续新增平台时破坏主流程结构。

### 1.8 时间窗口策略

近期窗口构造位于 `pipeline.py` 中：

- `_build_recent_window_params(...)`
- `_safe_recent_window_days(...)`

当主流程为分析模式时：

- `recent_only=True`
- 默认读取 `YOUTUBE_LOOKBACK_DAYS`
- 默认回看窗口为近 `7` 天

随后会将该时间窗口转换为：

- `published_after`
- `time_filter`

并传给 YouTube 采集器。

该策略的作用是让分析结果更贴近当前舆情，而不是被历史高热视频长期占据。代价是对于讨论量较低的关键词，近期窗口可能会明显降低可采集数量。

### 1.9 清洗与入库前处理策略

统一清洗位于 `python/opinion_engine/cleaning.py`，核心函数包括：

- `clean_comment_text(...)`
- `looks_like_noise(...)`
- `_looks_like_mojibake(...)`
- `clean_opinion_records(...)`

当前入库前的处理规则已经收敛为两类：

- 过滤空内容
- 过滤明显乱码

当前不会因为以下原因直接丢弃记录：

- 广告风格
- 口语化评论
- 文本较短
- 重复文本

其中，`_looks_like_mojibake(...)` 主要检测的是典型乱码片段，例如：

- `Ã`
- `Â`
- `â€`
- `ðŸ`
- `ï¿½`

这样做的原因是此前的清洗规则过强，导致有效样本被误删，最终表现为“前端设置抓取 20 条，但最终只剩几条”。当前版本优先保证样本保留，再将进一步清洗交给后续可配置策略。

### 1.10 数据库存储与任务轮次策略

存储实现位于 `python/opinion_engine/storage.py`，核心类为 `OpinionStorage`。

关键函数包括：

- `initialize()`
- `create_run(...)`
- `save_cleaned_records(...)`
- `load_run_records(...)`
- `complete_run(...)`
- `mark_run_collected(...)`
- `fail_run(...)`

数据库中的核心表包括：

- `collection_runs`
- `cleaned_records`

两张表的职责分工如下：

- `collection_runs`
  - 记录一轮任务的开始时间、结束时间、状态、摘要、情绪分数、热度分数、保留数、丢弃数、来源统计、错误信息

- `cleaned_records`
  - 记录本轮清洗后的每条内容，包括平台、作者、原链接、正文、发布时间、标题、描述、字幕、评论摘要、抓取错误信息等

该设计让整个主流程都围绕 `run_id` 运转，带来三个直接收益：

1. 主流程任意阶段失败时，仍可回溯到本轮上下文
2. 前端可以展示每个平台的分配数、抓取数、清理数、保留数
3. 大模型分析输入与最终前端展示都来自同一轮入库结果，避免内存态和展示态不一致

### 1.11 大模型分析输入构造策略

大模型分析位于 `python/opinion_engine/analysis/analyzer.py`，核心函数包括：

- `analyze_records(...)`
- `_prepare_record_inputs(...)`
- `_build_compact_record_content(...)`
- `_build_transcript_input(...)`
- `_analyze_all_records(...)`
- `_normalize_record_sentiments(...)`
- `_normalize_controversy_points(...)`

大模型输入不是直接把数据库原始行完整透传，而是先经 `_prepare_record_inputs(...)` 做结构化整理。每条记录最终会被整理为：

- `keyword`
- `source`
- `title`
- `description`
- `transcript_text`
- `comments_text`
- `content`
- `original_link`
- `publish_date`

其中：

- `YouTube` 记录会重点保留标题、描述、字幕和评论摘要
- `Reddit` 记录会重点保留正文与评论片段

随后 `_analyze_all_records(...)` 会构造严格 JSON 输出要求，要求模型返回：

- `summary`
- `controversy_points`
- `record_sentiments`

大模型输出回到后端后，还会继续做结构化规范：

- `_normalize_record_sentiments(...)`
- `_normalize_controversy_points(...)`
- `_ensure_summary(...)`
- `_ensure_controversy_points(...)`

这说明本项目的大模型策略并不是“直接相信模型文本”，而是“先约束输出结构，再做二次归一化和兜底补全”。

### 1.12 监控与三阶段前端映射策略

主流程监控由 `pipeline.py` 中的以下函数维护：

- `_create_monitor(...)`
- `_append_monitor_stage(...)`
- `_finalize_monitor(...)`
- `_public_monitor_snapshot(...)`

每个阶段都会写入 `monitor.stages`，典型阶段包括：

- `request_received`
- `records_cleaned`
- `llm_analysis_started`
- `response_ready`

前端并不会把全部后端阶段逐条显示，而是会在 `lib/providers/sentiment_provider.dart` 中根据阶段集合做三段式归并：

- 出现 `request_received` 后，进入“主程序开始”
- 出现 `llm_analysis_started` 后，进入“数据送入大模型”
- 出现 `response_ready` 后，进入“模型返回并刷新结果”

再由 `lib/screens/dashboard_page.dart` 渲染为固定三阶段流程展示。这样既保留了真实的后端阶段依据，又避免将过长的后端时间线直接暴露给界面。

---

## 2. 提示词设计方法

### 2.1 设计原则

在本项目的代码改造过程中，提示词设计遵循以下原则：

1. 先建立上下文，再进入修改
2. 先描述现象，再描述目标
3. 需求按功能块拆分，不将多个改造点混成一句话
4. 当出现偏差时，明确回退边界，而不是笼统要求“恢复”
5. 对显示类问题和流程类问题分别描述，避免把界面误差和后端逻辑混为一谈

这些原则的核心目的，是让代码代理能够把自然语言需求准确映射到真实文件、真实函数和真实流程节点。

### 2.2 提示词的组织顺序

在整个改造过程中，提示词的有效组织顺序大致如下：

1. 先要求完整理解项目代码
2. 先搭建全流程功能框架，再进入局部细化
3. 再下达单个功能改造指令
4. 出现偏差后，按模块拆分调试与定位
5. 需要保留已有成果时，明确“只回退某一部分”
6. 文档整理阶段，再单独提出 README 与技术文档要求

这种顺序的优势在于：

- 避免代理在缺少上下文时直接修改核心文件
- 先把主链路搭起来，再逐步补强局部能力
- 降低一次修改多个模块时的误伤概率
- 能够逐步锁定“是主流程框架问题、局部模块问题、前端展示问题，还是回退边界问题”

### 2.3 关键提示词样式

本项目中使用过的高价值提示词可以归纳为以下几类。

#### 2.3.1 上下文建立型

示例：

- “先完全了解一下我的项目代码”

设计意图：

- 强制先读代码，再动手
- 让修改建立在真实项目结构之上

解决的问题：

- 降低凭经验误判项目结构的风险
- 帮助快速识别前端、后端、Spider、清洗、分析、存储之间的边界

#### 2.3.2 全流程框架型

示例：

- “1.代码中我写了一个监控模式，将其逻辑改进：开起监控模式后，增加一个开启监控时间、监控触发倒计时、累计触发监控次数。并且监控模式开启时，不能修改所有的配置，包括平台权重。2.前端的进度显示还是不真实，应该显示三个阶段，第一个在主程序开始时显示，第二个在爬取数据送入大模型显示，第三个在大模型显示完返回此程序显示”
- “将大模型最后输出的三个观点和总结等回答，生成为mermaid格式的思维导图并渲染，思维导图设计可以尽量丰富一点，最后将导图输出到前端。”
- “在将平台爬取到的消息保存到数据库之前，需要处理脏数据（广告、垃圾评论、乱码）。添加这一步骤”

设计意图：

- 先定义主流程中要新增的完整能力链路
- 让后端、前端、数据库、展示层围绕同一目标同步改造

解决的问题：

- 将监控模式、三阶段进度、思维导图、清洗入库这些能力纳入统一主流程
- 避免只改某一个界面或某一个函数，导致功能链路不闭环

#### 2.3.3 功能增强型

示例：

- “将大模型最后输出的三个观点和总结等回答，生成为mermaid格式的思维导图并渲染，思维导图设计可以尽量丰富一点，最后将导图输出到前端。”
- “在前端显示每个平台分配了多少，爬取到多少，清理了多少”
- “360秒的超时对于最大数据50还是太短了，将超时设置到九分半”

设计意图：

- 直接给出目标结果
- 明确影响的功能边界

解决的问题：

- 驱动后端补充统计字段
- 驱动前端增加可视化结果
- 驱动大模型与前端结果链路联动

#### 2.3.4 模块化调试型

示例：

- “现在主流程已经构建好了，我想单独调试YouTube平台的爬取入库流程，给我一个单独调试的debug代码，尽量复用主流程接口与数据库键”
- “现在我调试好了YouTube平台后端爬取入库流程，将其整合到现在的主流程中”
- “为什么现在控制台输出很多行：INFO: 127.0.0.1:58764 - "GET /api/analyze/9232e2e5df904d61b80149c9b2e25fde HTTP/1.1" 200 OK”
- “为什么我现在设置的总数为20，最后只能爬取到几个？”
- “在’当前进度‘那一栏，主程序完成之后，不再显示详细信息。并且思维导图不要把源码显示出来”
- “我重复进行操作的适合，后端流程（三阶段）为什么不显示了？你可能是误解了我的任务，我的意思是不再展示后端时间线，但是三阶段每次分析都得显示”

设计意图：

- 不一次性重写全部功能，而是按单个模块逐点排查
- 把问题拆分到日志、抓取分配、前端阶段展示、导图展示等具体子链路

解决的问题：

- 将复杂系统中的问题缩小到某一个模块或某一层状态流
- 便于判断问题是在接口模式、平台抓取、状态管理还是展示组件中产生

#### 2.3.5 现象纠偏型

示例：

- “前端的进度显示还是不真实，应该显示三个阶段，第一个在主程序开始时显示，第二个在爬取数据送入大模型显示，第三个在大模型显示完返回此程序显示”
- “为什么我现在设置的总数为20，最后只能爬取到几个？”
- “我发现过滤掉的太多了，先把过滤逻辑修改成只过滤乱码”

设计意图：

- 先描述看到的现象，再逼近问题根因

解决的问题：

- 将“抓取数量不足”拆解为分配、抓取、清洗、保留四个阶段
- 将“进度不真实”拆解为三阶段可视化与后端真实阶段映射
- 将“过滤过多”直接回收到清洗规则本身


### 2.4 提示词设计带来的工程收益

在本项目中，较好的提示词设计带来了以下工程收益：

- 让需求直接映射到真实代码位置
- 减少“看起来改了，实际改错层级”的情况
- 有利于多轮迭代中的精准回退
- 让前端问题、后端问题、数据问题、模型问题可以分层定位
- 最终能沉淀出可文档化、可复用的工程过程

---

## 3. 主要问题与解决方案

### 3.1 前端中英文切换问题

问题表现：

- 前端界面存在中文与英文两套文案
- 如果没有统一语言状态源，不同卡片、按钮、提示信息容易出现切换不一致

代码落点：

- `lib/providers/app_language_provider.dart`
- `lib/l10n/app_strings.dart`
- `lib/services/local_insight_translator.dart`
- `lib/main.dart`

解决方案：

- 以 `AppLanguage` 作为全局语言状态
- 通过 `AppLanguageProvider` 统一分发界面语言
- 将静态文案集中收敛到 `app_strings.dart`
- 对结果类文本使用 `local_insight_translator.dart` 做补充翻译

工程效果：

- 页面结构、按钮、提示、统计标题能够统一切换
- 减少局部硬编码造成的中英文混杂

### 3.2 前端运行流程期间的流程可视化问题

问题表现：

- 分析耗时较长
- 如果只显示普通加载动画，会被误判为卡住或无响应
- 如果直接展示后端全部阶段，则信息过多、噪声过大

代码落点：

- `python/opinion_engine/pipeline.py`
- `lib/providers/sentiment_provider.dart`
- `lib/screens/dashboard_page.dart`

解决方案：

- 后端继续维护完整 `monitor.stages`
- 前端只归并为三阶段展示
- 在 `SentimentProvider` 中根据阶段集合判断当前所处阶段
- 在 `dashboard_page.dart` 中将三阶段渲染为固定流程卡片
- 分析完成后保留三阶段完成态，而不继续展示冗长后端时间线

工程效果：

- 进度展示既基于真实后端阶段，又不会暴露过细实现细节
- 每次分析都能稳定看到三阶段流程

### 3.3 数据入库接入问题

问题表现：

- 平台采集、清洗、分析、展示涉及同一轮数据
- 如果只依赖内存对象串联，很难稳定保留任务状态和统计数据

代码落点：

- `python/opinion_engine/storage.py`
- `python/opinion_engine/pipeline.py`

解决方案：

- 引入 `OpinionStorage`
- 以 `collection_runs` 存任务级状态
- 以 `cleaned_records` 存记录级内容
- 主流程中执行“先建轮次、再入库、再回读、再分析”

工程效果：

- 每轮任务都有独立 `run_id`
- 采集数、清洗数、保留数、错误信息都可追踪
- 前端展示与大模型输入保持同一数据来源

### 3.4 YouTube 平台使用官方接口容易出现 429

问题表现：

- 搜索、视频详情、字幕阶段都可能触发限流
- 直接表现为抓取数偏少、搜索失败或字幕失败

代码落点：

- `python/opinion_engine/spiders/youtube.py`

解决方案：

- 保留 `official_api` 与 `headless_browser` 双模式
- 通过 `_request_json_with_retries(...)` 和 `_call_with_retries(...)` 做有限重试
- 使用 `_sleep_before_transcript_request()` 降低字幕接口请求频率
- 在结果中保留 `fetch_error` 与 `source_errors`

工程效果：

- 主流程对单次接口异常不再过于脆弱
- 前端可以看到抓取不足是“平台限制”还是“清洗丢弃”

### 3.5 Reddit 平台在新网站爬取的局限性

问题表现：

- 新版 Reddit 页面结构复杂，动态加载更多
- 更容易遇到阻断页、异常页和自动化识别问题

代码落点：

- `python/opinion_engine/spiders/reddit_spider.py`

解决方案：

- 采用 `old.reddit.com/search` 作为稳定入口
- 使用搜索页初筛 + 详情页复筛的双层策略
- 对错误页做检测和有限重试
- 对评论提取设置字符预算和数量预算

工程效果：

- 提高了结构稳定性和可维护性
- 接受一定的信息丰富度损失，换取更稳定的可抓取性

### 3.6 大模型输入输出的调试问题

问题表现：

- 当大模型返回异常时，难以快速判断是输入构造问题、提示词问题还是 JSON 解析问题
- 同时还需要确认模型是否真正看到了标题、正文、字幕和评论摘要

代码落点：

- `python/opinion_engine/analysis/analyzer.py`
- `python/opinion_engine/analysis/llm_client.py`

解决方案：

- 通过 `_prepare_record_inputs(...)` 固定输入结构
- 在 `_analyze_all_records(...)` 中要求模型返回严格 JSON
- 通过 `_normalize_record_sentiments(...)` 和 `_normalize_controversy_points(...)` 做二次规范化
- 通过 `_ensure_summary(...)`、`_ensure_controversy_points(...)` 做兜底
- 将模型、阶段、统计信息保留在响应中便于回看
- 将超时时间提升到 `570` 秒，降低大批量输入时的超时概率

工程效果：

- 模型调试从“只看自然语言回复”转为“看输入结构、看输出结构、看归一化结果”
- 大模型链路更容易定位问题发生点

### 3.7 抓取总数与最终保留数不一致

问题表现：

- 前端设置总抓取数后，最终返回量明显偏少

原因拆解：

1. `total_limit` 只是总预算，不是最终保留数承诺
2. 预算会先按平台权重分配
3. 平台不一定能抓满
4. 清洗阶段还会继续丢弃空内容和乱码

代码落点：

- `pipeline.py`
- `cleaning.py`
- `dashboard_page.dart`

解决方案：

- 后端返回 `source_limits`
- 后端返回 `raw_count_by_source`
- 后端返回 `discarded_count_by_source`
- 后端返回 `retained_count_by_source`
- 前端增加平台抓取统计卡片

工程效果：

- “为什么只剩几条”可以被拆解为具体阶段，而不是停留在结果层面的模糊感知

### 3.8 清洗规则过强导致误删过多

问题表现：

- 早期版本中过滤过多，最终有效样本明显偏少

代码落点：

- `python/opinion_engine/cleaning.py`

解决方案：

- 收缩 `looks_like_noise(...)` 的职责
- 当前只保留明显乱码识别
- 空内容仍继续过滤
- 暂不再因为广告风格、短文本、重复文本直接丢弃

工程效果：

- 当前版本更偏向保留样本，减少过度清洗造成的统计失真

### 3.9 异步轮询导致控制台出现大量访问日志

问题表现：

- 控制台反复出现 `GET /api/analyze/{job_id} 200 OK`

原因：

- 曾采用“异步任务 + 轮询查询结果”的方案

解决方案：

- 恢复为同步 `POST /api/analyze`
- 主流程直接返回完整结果
- 不再依赖前端持续轮询分析结果

工程效果：

- 控制台日志显著简化
- 联调时更容易观察真实错误


---

## 4. 总结

当前项目已经形成一条较完整的工程闭环：

- 前端负责配置、监控、流程展示、统计展示、导图展示
- 后端负责采集编排、清洗、入库、分析与响应统一化
- 大模型负责整轮数据的结构化观点提炼与摘要生成

本阶段沉淀出的关键技术经验包括：

1. 平台采集策略必须与平台现实约束一起设计，不能只写理想流程
2. 大模型输入输出必须结构化，不能直接依赖自由文本
3. 平台统计必须前端可见，否则很难定位“少数据”问题发生在哪一层
4. 清洗规则必须与样本保留目标一致，过强过滤会直接扭曲结果
5. 提示词设计应能映射到真实代码模块，这样多轮迭代和精准回退才可控

----
