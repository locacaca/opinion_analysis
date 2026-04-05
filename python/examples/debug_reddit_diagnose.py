"""Reddit 页面结构诊断脚本"""
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright


async def diagnose_page():
    keyword = "chatgpt"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        search_url = f"https://www.reddit.com/search/?q={keyword}&type=link&sort=new"

        print(f"[*] 正在访问: {search_url}")
        await page.goto(search_url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(5)  # 等待更长时间

        print("\n" + "=" * 60)
        print(" 诊断结果")
        print("=" * 60)

        # 检查 shreddit-post
        posts = await page.query_selector_all("shreddit-post")
        print(f"\n1. shreddit-post 元素数量: {len(posts)}")

        # 检查其他可能的选择器
        selectors_to_check = [
            "div[data-testid='post-container']",
            "div[data-testid='search-post']",
            "article",
            "div.thing",
            "div[data-click-id='body']",
            "a[href*='/r/']",
            "div[slot='post-title']",
            "[data-ad放开-preview='true']",
        ]

        print("\n2. 其他选择器检查:")
        for sel in selectors_to_check:
            elements = await page.query_selector_all(sel)
            print(f"   {sel}: {len(elements)} 个")

        # 获取页面 HTML 片段
        print("\n3. 页面 HTML 结构 (body 前 2000 字符):")
        body_html = await page.evaluate("document.body ? document.body.innerHTML.substring(0, 2000) : 'no body'")
        print(body_html)

        # 检查是否有登录墙或限制
        print("\n4. 检查页面内容:")
        title = await page.title()
        print(f"   页面标题: {title}")

        # 检查是否有 "login" 或 "sign up" 相关内容
        login_elements = await page.query_selector_all("text=/login|sign up|subscribe/i")
        print(f"   登录/注册提示数量: {len(login_elements)}")

        # 截图保存
        await page.screenshot(path="reddit_debug.png", full_page=True)
        print("\n[+] 截图已保存到 reddit_debug.png")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(diagnose_page())
