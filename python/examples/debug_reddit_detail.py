"""Reddit 帖子详情页结构诊断"""
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright


async def diagnose_detail_page():
    """诊断帖子详情页的实际结构"""
    # 使用一个已知的帖子 URL
    test_url = "https://www.reddit.com/r/ClaudeAI/comments/1s9e5e4/claude_code_mcp_server_for_claude_code/"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        print(f"[*] 正在访问: {test_url}")
        await page.goto(test_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        print("\n" + "=" * 60)
        print(" 帖子详情页诊断")
        print("=" * 60)

        # 检查 shreddit-post
        posts = await page.query_selector_all("shreddit-post")
        print(f"\n1. shreddit-post 数量: {len(posts)}")

        if posts:
            post = posts[0]
            attrs = await post.evaluate("""
                el => {
                    const shadow = el.shadowRoot;
                    if (!shadow) return { hasShadow: false };
                    
                    return {
                        hasShadow: true,
                        innerHTML: shadow.innerHTML.substring(0, 3000),
                        innerText: shadow.innerText.substring(0, 1000),
                        slots: Array.from(shadow.querySelectorAll('slot')).map(s => ({
                            name: s.name,
                            assignedNodes: Array.from(s.assignedNodes()).map(n => ({
                                tagName: n.tagName || 'TEXT',
                                text: (n.textContent || '').substring(0, 200)
                            }))
                        }))
                    };
                }
            """)
            print(f"\n2. shreddit-post shadowRoot 内容:")
            print(f"   hasShadow: {attrs.get('hasShadow')}")
            print(f"   innerText (前500字符): {attrs.get('innerText', '')[:500]}")
            print(f"   slots 数量: {len(attrs.get('slots', []))}")

            for i, slot in enumerate(attrs.get('slots', [])[:3]):
                print(f"\n   Slot {i}: name={slot['name']}")
                for node in slot.get('assignedNodes', [])[:2]:
                    print(f"      - {node['tagName']}: {node['text'][:100]}...")

        # 检查 document.body.innerText
        body_text = await page.evaluate("document.body.innerText.substring(0, 2000)")
        print(f"\n3. document.body.innerText (前1000字符):")
        print(body_text[:1000])

        # 检查 article 元素
        articles = await page.query_selector_all("article")
        print(f"\n4. article 元素数量: {len(articles)}")

        # 检查 main 内容
        main_content = await page.evaluate("""
            () => {
                const main = document.querySelector('main');
                if (!main) return 'no main';
                return main.innerText.substring(0, 2000);
            }
        """)
        print(f"\n5. main.innerText (前1000字符):")
        print(main_content[:1000])

        # 截图
        await page.screenshot(path="reddit_detail_debug.png", full_page=True)
        print("\n[+] 截图已保存到 reddit_detail_debug.png")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(diagnose_detail_page())
