# 舆情分析系统

## 项目介绍

本项目是一个面向多平台内容采集与舆情分析的完整工程，覆盖“关键词输入、平台采集、数据清洗、结果入库、大模型分析、前端展示”全流程。

项目分为两部分：

- `lib/`：Flutter 前端，负责参数配置、监控模式、流程进度展示、统计展示、观点展示、思维导图展示
- `python/`：FastAPI 后端与 Python 舆情引擎，负责采集调度、清洗、存储、分析与结果返回

当前主流程重点支持的平台包括：

- `YouTube`：关键词检索、视频元数据采集、字幕与转写采集
- `Reddit`：关键词检索、帖子正文与评论片段采集
- `X`：统一接口已预留，当前仍以占位实现为主

当前版本的主流程能力包括：

- 按关键词执行多平台内容采集
- 根据总抓取量与平台权重分配平台配额
- 对采集内容进行基础清洗，仅过滤空内容和明显乱码
- 将清洗后的内容写入数据库并绑定到同一轮分析任务
- 调用大模型输出摘要、三个核心观点、逐条记录分析结果
- 前端展示三阶段流程、平台统计、原始内容和思维导图

## 架构图

```mermaid
flowchart TD
    A[前端界面] --> B[接口服务层]
    B --> C[后端主接口]

    C --> D[主流程编排]
    D --> E[平台配额分配]
    D --> F[平台采集器]
    D --> G[清洗模块]
    D --> H[存储模块]
    D --> I[大模型分析模块]
    D --> J[统一结果响应]

    F --> F1[YouTube 采集器]
    F --> F2[Reddit 采集器]
    F --> F3[X 采集器]

    H --> K[(SQLite 或 PostgreSQL)]
    I --> L[大模型服务]

    J --> A
```

## 本地运行步骤

### 1. 环境准备

建议准备以下运行环境：

- `Flutter SDK`
- `Python 3.10+`
- `PowerShell`
- 可选数据库
  - 默认可直接使用 `SQLite`
  - 需要独立数据库时可切换为 `PostgreSQL`

### 2. 安装前端依赖

```bash
flutter pub get
```

### 3. 安装后端依赖

```bash
pip install -r python/requirements.txt
```

### 4. 配置环境变量

先复制示例配置：

```bash
copy python/.env.example python/.env
```

主流程常用环境变量如下：

- `LLM_API_KEY`：大模型接口密钥
- `LLM_API_BASE_URL`：大模型接口基地址
- `LLM_MODEL`：大模型名称
- `LLM_TIMEOUT_SECONDS`：大模型超时时间，当前默认值为 `570`
- `DATABASE_URL`：数据库连接串
- `YOUTUBE_DATA_API_KEY`：YouTube 官方接口密钥
- `REDDIT_PROXY`：Reddit 抓取代理
- `HTTPS_PROXY`
- `HTTP_PROXY`

数据库配置示例：

```text
sqlite:///./data/trendpulse.db
```

```text
postgresql+psycopg://username:password@localhost:5432/trendpulse
```

### 5. 一键启动脚本

项目内置一键启动脚本：

```powershell
.\scripts\start_trendpulse.ps1
```

脚本行为如下：

1. 解析项目根目录与环境变量来源
2. 在新窗口中启动后端
3. 轮询 `GET /health`，确认后端已就绪
4. 后端健康检查通过后，再启动前端
5. 自动向前后端注入环境变量

脚本读取环境变量的优先级如下：

1. 当前进程环境变量
2. 当前账户环境变量
3. 系统环境变量
4. `python/.env`
5. `python/.env.example`

常用启动示例：

```powershell
.\scripts\start_trendpulse.ps1 -BackendOnly
.\scripts\start_trendpulse.ps1 -FlutterDevice windows
.\scripts\start_trendpulse.ps1 -ApiBaseUrl http://127.0.0.1:8000
.\scripts\start_trendpulse.ps1 -CondaEnvName android
.\scripts\start_trendpulse.ps1 -HealthTimeoutSeconds 120
```

参数说明：

- `-BackendOnly`：只启动后端，不启动前端
- `-FlutterDevice`：指定 `flutter run -d` 的设备名或设备标识
- `-ApiBaseUrl`：向前端注入 `API_BASE_URL`
- `-CondaEnvName`：前后端启动时使用的 Conda 环境名
- `-BackendHealthUrl`：健康检查地址，默认值为 `http://127.0.0.1:8000/health`
- `-HealthTimeoutSeconds`：等待后端健康检查通过的超时时间

使用前提：

- PowerShell 中可正常调用 `conda`
- 对应 Conda 环境中已经安装前后端依赖
- `python/.env` 或系统环境变量配置正确

### 6. 手动启动后端

```bash
python python/examples/run_api.py
```

默认监听地址：

- `http://127.0.0.1:8000`

### 7. 手动启动前端

```bash
flutter run
```

前端默认后端地址规则如下：

- `Windows / macOS / Linux / Web`：`http://127.0.0.1:8000`
- `Android` 模拟器：`http://10.0.2.2:8000`

如需显式指定：

```bash
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

## 主流程接口文档

本节只描述前端主流程实际依赖的接口，不包含调试与诊断接口。

### 1. 健康检查接口

#### 接口地址

`GET /health`

#### 作用

- 判断后端服务是否启动成功
- 供一键启动脚本轮询
- 供本地开发、部署验收、反向代理检查使用

#### 请求参数

无

#### 成功响应示例

```json
{
  "status": "ok"
}
```

#### 响应字段说明

- `status`
  - 类型：`string`
  - 含义：健康状态
  - 当前固定值：`ok`

#### 返回码说明

- `200 OK`：服务可用

---

### 2. 舆情分析主接口

#### 接口地址

`POST /api/analyze`

#### 作用

该接口对应完整主流程，执行顺序如下：

1. 校验请求参数
2. 创建分析任务与数据库轮次记录
3. 规范化平台列表和 YouTube 抓取模式
4. 根据总抓取量与平台权重分配平台配额
5. 并发调用各平台采集器抓取原始内容
6. 统一执行清洗，仅过滤空内容和明显乱码
7. 将清洗结果写入数据库
8. 从数据库回读本轮记录
9. 将整轮记录送入大模型分析
10. 计算热度分数、来源统计等指标
11. 返回前端展示所需完整结果

#### 请求头

- `Content-Type: application/json`

#### 请求体示例

```json
{
  "keyword": "DeepSeek",
  "language": "en",
  "output_language": "zh",
  "limit_per_source": 30,
  "total_limit": 20,
  "sources": ["youtube", "reddit"],
  "source_weights": {
    "youtube": "high",
    "reddit": "medium"
  },
  "youtube_mode": "official_api"
}
```

#### 请求字段说明

- `keyword`
  - 类型：`string`
  - 是否必填：必填
  - 约束：长度 `1~100`
  - 含义：本轮分析关键词

- `language`
  - 类型：`string`
  - 是否必填：否
  - 默认值：`en`
  - 可选值：`en`、`zh`
  - 含义：采集语言，也是部分平台筛选条件的一部分

- `output_language`
  - 类型：`string`
  - 是否必填：否
  - 默认值：`en`
  - 可选值：`en`、`zh`
  - 含义：要求大模型以哪种语言输出摘要和观点

- `limit_per_source`
  - 类型：`integer`
  - 是否必填：否
  - 默认值：`30`
  - 范围：`1~50`
  - 含义：当 `total_limit` 为空时，每个平台的默认抓取上限

- `total_limit`
  - 类型：`integer | null`
  - 是否必填：否
  - 范围：`1~50`
  - 含义：本轮总抓取预算
  - 说明：一旦传入，会优先使用该值并按平台权重重新分配

- `sources`
  - 类型：`string[]`
  - 是否必填：否
  - 默认值：`["youtube"]`
  - 可选值：`youtube`、`reddit`、`x`
  - 含义：本轮启用的平台列表
  - 说明：若传入无效平台，后端会过滤；若过滤后为空，则返回 `400`

- `source_weights`
  - 类型：`object`
  - 是否必填：否
  - 默认值：空对象
  - 键：平台名
  - 值：`low`、`medium`、`high`
  - 含义：平台权重，用于总抓取预算分配
  - 权重映射：
    - `low = 1`
    - `medium = 2`
    - `high = 3`

- `youtube_mode`
  - 类型：`string`
  - 是否必填：否
  - 默认值：`official_api`
  - 可选值：`official_api`、`headless_browser`
  - 含义：YouTube 平台的采集模式
  - 说明：
    - `official_api`：速度更快，依赖官方接口与配额
    - `headless_browser`：更偏向浏览器模拟抓取，适合补充某些字幕缺失场景

#### 平台配额分配规则

- 当 `total_limit` 为空时：
  - 每个平台直接使用 `limit_per_source`

- 当 `total_limit` 有值时：
  - 后端先将平台权重转换为数值
  - 再按比例分配到各平台
  - 若有余数，则按剩余比例补齐
  - 会尽量保证每个启用平台至少分到 `1`

示例：

- `sources = ["youtube", "reddit"]`
- `total_limit = 20`
- `source_weights = {"youtube": "high", "reddit": "medium"}`

分配结果通常为：

- `youtube = 12`
- `reddit = 8`

#### 成功响应示例

```json
{
  "run_id": 12,
  "keyword": "DeepSeek",
  "language": "en",
  "output_language": "zh",
  "selected_sources": ["youtube", "reddit"],
  "youtube_mode": "official_api",
  "llm_model": "deepseek-chat",
  "requested_total_limit": 20,
  "source_limits": {
    "youtube": 12,
    "reddit": 8
  },
  "raw_count_by_source": {
    "youtube": 9,
    "reddit": 3
  },
  "retained_count_by_source": {
    "youtube": 9,
    "reddit": 3
  },
  "discarded_count_by_source": {
    "youtube": 0,
    "reddit": 0
  },
  "sentiment_score": 63,
  "heat_score": 71,
  "summary": "......",
  "controversy_points": [
    {
      "title": "......",
      "summary": "......"
    }
  ],
  "posts": [
    {
      "source": "youtube",
      "title": "......",
      "content": "......",
      "author": "......",
      "original_link": "......"
    }
  ],
  "retained_comment_count": 12,
  "discarded_comment_count": 0,
  "source_breakdown": {
    "youtube": 9,
    "reddit": 3
  },
  "source_errors": {},
  "chunk_summaries": [],
  "record_sentiments": [],
  "monitor": {
    "mode": "analyze",
    "keyword": "DeepSeek",
    "status": "completed",
    "stages": []
  }
}
```

#### 响应字段说明

- `run_id`
  - 类型：`integer`
  - 含义：本轮任务在数据库中的唯一编号

- `keyword`
  - 类型：`string`
  - 含义：本轮分析关键词

- `language`
  - 类型：`string`
  - 含义：本轮采集语言

- `output_language`
  - 类型：`string`
  - 含义：本轮大模型输出语言

- `selected_sources`
  - 类型：`string[]`
  - 含义：本轮实际启用的平台

- `youtube_mode`
  - 类型：`string`
  - 含义：本轮 YouTube 采集模式

- `llm_model`
  - 类型：`string`
  - 含义：本轮使用的大模型名称

- `requested_total_limit`
  - 类型：`integer`
  - 含义：本轮最终采用的总抓取预算
  - 说明：该值等于 `source_limits` 的和

- `source_limits`
  - 类型：`object`
  - 含义：每个平台被分配到的目标抓取量

- `raw_count_by_source`
  - 类型：`object`
  - 含义：每个平台实际抓取到的原始记录数
  - 说明：该值可能小于分配值，原因通常是平台搜索结果不足、时间窗口过窄、接口限流或抓取失败

- `retained_count_by_source`
  - 类型：`object`
  - 含义：每个平台清洗后保留的记录数

- `discarded_count_by_source`
  - 类型：`object`
  - 含义：每个平台在清洗阶段被过滤的记录数

- `sentiment_score`
  - 类型：`integer`
  - 范围：`0~100`
  - 含义：整轮舆情的加权情绪分数

- `heat_score`
  - 类型：`integer`
  - 范围：`0~100`
  - 含义：基于相关性与时效性计算得到的热度分数

- `summary`
  - 类型：`string`
  - 含义：整轮分析摘要

- `controversy_points`
  - 类型：`array`
  - 含义：三个核心观点或争议点
  - 字段：
    - `title`：观点标题
    - `summary`：观点说明

- `posts`
  - 类型：`array`
  - 含义：前端展示用的源内容列表
  - 字段：
    - `source`：来源平台
    - `title`：展示标题
    - `content`：截断后的正文
    - `author`：作者
    - `original_link`：原始链接

- `retained_comment_count`
  - 类型：`integer`
  - 含义：本轮最终进入分析的总记录数

- `discarded_comment_count`
  - 类型：`integer`
  - 含义：本轮在清洗阶段被丢弃的总记录数

- `source_breakdown`
  - 类型：`object`
  - 含义：最终保留记录按平台汇总后的数量

- `source_errors`
  - 类型：`object`
  - 含义：各平台抓取阶段出现的错误信息
  - 说明：某个平台失败不会必然导致整轮失败，后端会尽量返回其它平台的结果

- `chunk_summaries`
  - 类型：`array`
  - 含义：兼容旧结构保留的字段，当前主要承载逐条记录分析映射结果

- `record_sentiments`
  - 类型：`array`
  - 含义：逐条记录的情绪判断与相关性判断
  - 字段：
    - `record_index`
    - `source`
    - `title`
    - `original_link`
    - `sentiment_score`
    - `relevance_score`
    - `sentiment_label`
    - `reasoning`

- `monitor`
  - 类型：`object`
  - 含义：后端主流程监控数据
  - 关键字段：
    - `mode`：当前模式，主流程为 `analyze`
    - `status`：执行状态
    - `started_at`：开始时间
    - `finished_at`：结束时间
    - `duration_ms`：耗时
    - `stages`：阶段数组
  - 说明：前端三阶段进度条会依据 `stages` 进行映射

#### `monitor.stages` 典型阶段

主流程中常见的阶段名包括：

- `request_received`
- `storage_initialized`
- `run_created`
- `sources_selected`
- `source_limits_resolved`
- `collector_plan_ready`
- `collection_completed`
- `records_collected`
- `records_cleaned`
- `records_stored`
- `llm_analysis_started`
- `llm_analysis_completed`
- `score_computation_completed`
- `response_ready`

前端会将这些阶段进一步归并为三个展示阶段：

1. 主程序开始执行
2. 数据送入大模型
3. 大模型返回并更新结果

#### 失败响应示例

```json
{
  "detail": "language must be either 'en' or 'zh'."
}
```

#### 返回码说明

- `200 OK`
  - 主流程执行成功

- `400 Bad Request`
  - 请求参数不合法
  - 常见场景：
    - `language` 非 `en` 或 `zh`
    - `youtube_mode` 非法
    - `sources` 为空或过滤后没有有效平台

- `500 Internal Server Error`
  - 后端执行失败
  - 常见场景：
    - 平台采集异常
    - 数据处理异常
    - 大模型返回结构异常

- `504 Gateway Timeout`
  - 主流程或大模型调用超时

## 目录说明

```text
lib/                    Flutter 前端
python/backend/         FastAPI 接口层
python/opinion_engine/  采集、清洗、存储、分析核心逻辑
python/examples/        本地启动与调试脚本
scripts/                一键启动脚本
data/                   本地数据库与运行数据
```
