# Python Opinion Collection Engine

This directory contains a Python 3.10 foundation for TrendPulse's multi-source collection, storage, and opinion-analysis pipeline.

## Included modules

- `BaseSpider`: abstract spider contract with `fetch()` and `clean_data()`
- `RedditSpider`: Reddit collection via `praw`
- `YouTubeTranscriptSpider`: keyword-based video discovery plus transcript collection
- `XSearchSpider`: source interface stub for future X/Twitter support
- `OpinionStorage`: cleaned-record persistence for SQLite or PostgreSQL
- `OpinionAnalyzer`: LLM-based opinion analysis with map-reduce aggregation
- `analyze_keyword()`: end-to-end orchestration for collect -> clean -> store -> analyze

## Processing flow

```text
keyword
  -> source spiders collect raw records
  -> cleaning layer normalizes and filters noise
  -> cleaned records are stored in SQLite/PostgreSQL
  -> stored records are loaded from the database
  -> LLM map-reduce analysis generates sentiment, controversies, and summary
```

## Directory structure

```text
python/
  backend/
    app.py
  opinion_engine/
    analysis/
      analyzer.py
      llm_client.py
      models.py
    spiders/
      base.py
      reddit.py
      x_stub.py
      youtube.py
    cleaning.py
    config.py
    engine.py
    pipeline.py
    storage.py
  examples/
    check_reddit_auth.py
    keyword_pipeline_example.py
    opinion_analysis_example.py
    reddit_example.py
    run_api.py
  requirements.txt
```

## Installation

```bash
pip install -r python/requirements.txt
```

## Environment variables

Copy the example file first:

```bash
copy python/.env.example python/.env
```

LLM analysis requires:

- `LLM_API_KEY`
- `LLM_API_BASE_URL`
- `LLM_MODEL`
- `LLM_TIMEOUT_SECONDS`

Database storage requires:

- `DATABASE_URL`

Examples:

- SQLite: `sqlite:///./data/trendpulse.db`
- PostgreSQL: `postgresql+psycopg://username:password@localhost:5432/trendpulse`

Reddit collection requires:

- `REDDIT_APP_TYPE`
- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USER_AGENT`

YouTube discovery requires:

- `YOUTUBE_DATA_API_KEY`

## Backend API

Run the FastAPI server:

```bash
python python/examples/run_api.py
```

Available endpoints:

- `GET /health`
- `POST /api/analyze`
- `POST /api/debug/collect`

## Keyword pipeline example

```bash
python python/examples/keyword_pipeline_example.py "DeepSeek" --limit 10
```

The response is dashboard-ready JSON and includes:

- `run_id`
- `keyword`
- `sentiment_score`
- `heat_score`
- `summary`
- `controversy_points`
- `posts`
- `source_breakdown`
- `source_errors`

## Collection-only debug

Run the collection pipeline without LLM analysis:

```bash
python python/examples/debug_collect_store.py "iPhone 16" --language en --limit 50 --sources youtube
```

Inputs:

- `keyword`
- `language`: `en` or `zh`
- `limit`
- `sources`: `reddit`, `youtube`, `x`

This flow:

- collects raw data
- cleans the raw data
- stores cleaned records into SQLite/PostgreSQL
- returns storage counts and the stored records

## Reddit auth check

```bash
python python/examples/check_reddit_auth.py
```
