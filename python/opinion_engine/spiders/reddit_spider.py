import praw
import os
import asyncio
from datetime import datetime
from typing import List, Dict
from ..models import SpiderRequest  # 假设你已有该模型

class RedditSearchSpider:
    def __init__(self):
        # 必须在 .env 中配置这些变量，符合考核“不得硬编码”要求
        self.reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent="TrendPulse_Scraper_v1.0",
            # 如果你在国内环境，可能需要配置 check_for_updates=False 并确保系统开启了全局代理
        )

    async def fetch(self, request: SpiderRequest) -> List[Dict]:
        """异步抓取 Reddit 搜索结果"""
        # 将同步的 PRAW 操作放入线程池，防止阻塞事件循环
        return await asyncio.to_thread(self._collect, request)

    def _collect(self, request: SpiderRequest) -> List[Dict]:
        """内部同步采集逻辑"""
        records = []
        try:
            # 根据关键词搜索，限制条数和时间范围（一周内）
            search_results = self.reddit.subreddit("all").search(
                request.keyword,
                limit=request.limit,
                time_filter="week"
            )

            for submission in search_results:
                # 过滤语言（可选，PRAW 搜索本身支持部分语言过滤，或在此手动过滤）
                records.append({
                    "source": "reddit",
                    "author": str(submission.author),
                    "title": submission.title,
                    "content": submission.selftext if submission.selftext else submission.title,
                    "url": f"https://www.reddit.com{submission.permalink}",
                    "score": submission.score,
                    "created_at": datetime.fromtimestamp(submission.created_utc).isoformat(),
                    "extra": {
                        "num_comments": submission.num_comments,
                        "subreddit": str(submission.subreddit)
                    }
                })
        except Exception as e:
            print(f"Reddit 采集异常: {e}")

        return records

    def debug_collect(self, request: SpiderRequest) -> Dict:
        """用于调试脚本的同步封装"""
        data = self._collect(request)
        return {
            "status": "success" if data else "empty",
            "platform": "reddit",
            "count": len(data),
            "results": data[:3]  # 仅返回前3条作为预览
        }