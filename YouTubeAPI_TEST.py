import re
import time
import random
from typing import List, Optional, Dict
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

class YouTubeDownloaderNoCookie:
    def __init__(self, proxies: Optional[Dict[str, str]] = None):
        self.proxies = proxies
        self.preferred_langs = ['zh-Hans', 'zh-Hant', 'en']

    def extract_video_id(self, url: str) -> Optional[str]:
        pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
        match = re.search(pattern, url)
        return match.group(1) if match else None

    def get_transcript(self, video_url: str, max_retries: int = 3) -> str:
        video_id = self.extract_video_id(video_url)
        if not video_id:
            return "Error: Invalid URL"

        for attempt in range(max_retries):
            try:
                # 引入随机延迟，模拟人类操作
                # 重试时增加延迟时间
                wait_time = random.uniform(5.0, 10.0) * (attempt + 1)
                print(f"[INFO] 等待 {wait_time:.1f} 秒后发起请求 (尝试 {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)

                # 不传 cookies 参数，仅依赖代理
                data = YouTubeTranscriptApi.get_transcript(
                    video_id,
                    languages=self.preferred_langs,
                    proxies=self.proxies,
                    preserve_formatting=False
                )

                return " ".join([item['text'] for item in data])

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg:
                    if attempt < max_retries - 1:
                        print(f"[WARNING] 触发 429 限流，准备重试...")
                        continue
                    else:
                        return "Error: 触发 429 限流。建议更换代理 IP 或增加延迟。"
                return f"Error: {error_msg}"

        return "Error: 未知错误"

# --- 运行示例 ---
if __name__ == "__main__":
    # 建议使用多个代理进行轮询 (Proxy Rotation)
    proxy_list = [
        {"https": "http://127.0.0.1:7890"},
        # {"https": "http://username:password@other-proxy:port"},
    ]

    downloader = YouTubeDownloaderNoCookie(proxies=random.choice(proxy_list))

    url = "https://www.youtube.com/watch?v=dJJb1WvlD8E"
    print(downloader.get_transcript(url))