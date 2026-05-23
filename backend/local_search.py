"""
本地网盘搜索服务 (运行在用户电脑上)
因为 yunso.net 从美国被屏蔽，搜索必须在本地执行
"""
import json
import asyncio
from flask import Flask, request, jsonify
from flask_cors import CORS
from playwright.async_api import async_playwright

app = Flask(__name__)
CORS(app)


async def search_yunso(keyword, max_results=5):
    """用 Playwright 从 yunso.net 搜索"""
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        real_urls = {}
        pending_card_id = [None]
        got_url_event = asyncio.Event()

        async def intercept_new_page(new_page):
            try:
                await new_page.wait_for_load_state("domcontentloaded", timeout=5000)
                url = new_page.url
                cid = pending_card_id[0]
                if cid and url and not url.startswith("https://www.yunso.net/"):
                    real_urls[cid] = url
                    got_url_event.set()
                await new_page.close()
            except Exception:
                pass

        context.on("page", intercept_new_page)

        try:
            await page.goto(
                f"https://www.yunso.net/index/user/s?wd={keyword}",
                timeout=30000,
                wait_until="domcontentloaded"
            )
            await page.wait_for_timeout(3000)

            cards = await page.evaluate("""() => {
                const items = document.querySelectorAll('#Searchshow .layui-card');
                const results = [];
                items.forEach((item, idx) => {
                    if (idx >= 20) return;
                    const link = item.querySelector('a[url]');
                    if (!link) return;
                    const text = item.textContent;
                    const lines = text.split('\\n').map(l => l.trim()).filter(l => l);
                    let name = '';
                    for (const line of lines) {
                        const cc = (line.match(/[\\u4e00-\\u9fff]/g) || []).length;
                        if (cc > 2 && line.length > 5 &&
                            !line.includes('前') && !line.includes('分') &&
                            !line.includes('合') && !line.match(/^\\d+、$/) &&
                            !line.match(/^\\d{4}-\\d{2}-\\d{2}/)) {
                            name = line.replace(/^(\\d+小时内|\\d+天内)\\s*/, '').trim();
                            break;
                        }
                    }
                    let time = '';
                    const tm = text.match(/\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}/);
                    if (tm) time = tm[0];
                    let tl = '';
                    const lm = text.match(/(\\d+小时内|\\d+天内)/);
                    if (lm) tl = lm[0];
                    let size = 'N/A';
                    const sm = text.match(/合计\\s*:([^\\s]+)/);
                    if (sm) size = sm[1].trim();
                    results.push({ name, time, time_label: tl, card_id: link.id, size });
                });
                return results;
            }""")

            print(f"[LocalSearch] 找到 {len(cards)} 个卡片")

            buttons = await page.query_selector_all("button.gosid")
            limit = min(len(buttons), len(cards), max_results)

            for i in range(limit):
                got_url_event.clear()
                pending_card_id[0] = cards[i]["card_id"]
                try:
                    btns = await page.query_selector_all("button.gosid")
                    await btns[i].click()
                    await asyncio.wait_for(got_url_event.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    pass

            for card in cards[:limit]:
                real_url = real_urls.get(card["card_id"], "")
                results.append({
                    "name": card["name"],
                    "time": card["time"],
                    "time_label": card["time_label"],
                    "size": card["size"],
                    "card_id": card["card_id"],
                    "real_url": real_url
                })

        except Exception as e:
            print(f"[LocalSearch] 异常: {e}")
            import traceback
            traceback.print_exc()

        await browser.close()
        return results


@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json(silent=True) or {}
    keyword = (data.get("keyword") or "").strip()
    limit = int(data.get("limit") or 5)
    if not keyword:
        return jsonify({"error": "请输入搜索关键词"}), 400

    try:
        print(f"[LocalSearch] 搜索: {keyword}")
        results = asyncio.run(search_yunso(keyword, max_results=limit))
        return jsonify({"results": results, "total": len(results)})
    except Exception as e:
        print(f"[LocalSearch] 异常: {e}")
        return jsonify({"error": f"搜索异常: {str(e)}"}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "local-search"})


if __name__ == "__main__":
    print(" OceanSource 本地搜索服务启动")
    print("   地址: http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=False)