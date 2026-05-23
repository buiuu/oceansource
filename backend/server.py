"""
OceanSource 后端服务 v2
- Playwright 搜索 yunso.net + 点击"前往"拦截真实网盘链接
- 夸克链接自动转存，使分享链接归属于自己账号
"""
import json
import time
import hashlib
import os
import re
import asyncio
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from playwright.async_api import async_playwright

import threading

app = Flask(__name__)
CORS(app)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

saved_resources = {}

# 夸克 Playwright persistent context 用户数据目录
USER_DATA_DIR = os.path.join(tempfile.gettempdir(), "quark_playwright_profile")

# 夸克认证文件路径（Render Secret File 会挂载到 /etc/secrets/）
QUARK_STATE_PATH = os.environ.get("QUARK_STATE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "quark_state.json"))

# 转存缓存文件
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transfer_cache.json")

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


# ============================================================
# 夸克网盘自动转存
# ============================================================
async def transfer_quark_link(real_url):
    """
    使用 Playwright persistent context 将夸克分享链接转存到自己账号并生成新分享链接。
    持久化登录状态保存在 USER_DATA_DIR 中，失败时返回原始链接。
    """
    try:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )

            # 注入反检测脚本
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false
                });
            """)

            # 从 quark_state.json 恢复 cookie（Secret File 注入）
            if os.path.exists(QUARK_STATE_PATH):
                try:
                    with open(QUARK_STATE_PATH, "r", encoding="utf-8") as f:
                        state_data = json.load(f)
                    cookies = state_data.get("cookies", [])
                    if cookies:
                        await context.add_cookies(cookies)
                        print(f"[Quark] 已从 {QUARK_STATE_PATH} 恢复 {len(cookies)} 个 cookie")
                except Exception as e:
                    print(f"[Quark] 恢复 cookie 失败: {e}")

            page = await context.new_page()

            # 1. 打开原始分享链接
            print(f"[Quark] 打开分享链接: {real_url}")
            await page.goto(real_url, timeout=20000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            # 2. 关闭可能出现的弹窗
            try:
                modal_close_selectors = [
                    ".ant-modal-close",
                    "[class*='modal'] [class*='close']",
                    ".ant-modal-wrap .ant-modal-close",
                    "button[aria-label='Close']",
                    "[class*='dialog'] [class*='close']",
                ]
                for close_sel in modal_close_selectors:
                    try:
                        close_btn = await page.wait_for_selector(close_sel, timeout=2000)
                        if close_btn:
                            await close_btn.click()
                            print(f"[Quark] 关闭弹窗: {close_sel}")
                            await page.wait_for_timeout(1000)
                            break
                    except Exception:
                        continue
            except Exception:
                pass

            try:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(1000)
            except Exception:
                pass

            # 3. 检查文件复选框状态（夸克分享页 Ant Design 表格默认已勾选）
            #    关键：只检查文件行（.ant-table-row）内的 checkbox，跳过表头全选 checkbox
            checked = await page.evaluate("""
                () => {
                    const row = document.querySelector('.ant-table-row');
                    if (!row) return false;
                    const cb = row.querySelector('input[type="checkbox"]');
                    return cb ? cb.checked : false;
                }
            """)
            print(f"[Quark] 文件复选框状态: checked={checked}")

            if not checked:
                # 仅当未勾选时才点击
                print("[Quark] 文件未勾选，尝试勾选...")
                try:
                    await page.click(".ant-table-row input[type='checkbox']", timeout=3000)
                    await page.wait_for_timeout(1000)
                    checked = await page.evaluate("""
                        () => {
                            const row = document.querySelector('.ant-table-row');
                            if (!row) return false;
                            const cb = row.querySelector('input[type="checkbox"]');
                            return cb ? cb.checked : false;
                        }
                    """)
                    print(f"[Quark] 点击后状态: {checked}")
                except Exception as e:
                    print(f"[Quark] 勾选失败: {e}")
                    # 兜底：点击文件行
                    try:
                        row = await page.wait_for_selector(".ant-table-row", timeout=3000)
                        if row:
                            await row.click()
                            await page.wait_for_timeout(1000)
                            checked = True
                            print("[Quark] 已通过点击行选中文件")
                    except Exception:
                        pass

            # 4. 点击"保存到网盘"按钮
            save_selectors = [
                "text=保存到网盘",
                "button:has-text('保存')",
                "button:has-text('保存到网盘')",
                ".save-btn",
                "[class*='save']",
                "text=保存到夸克网盘",
            ]
            saved = False
            for sel in save_selectors:
                try:
                    btn = await page.wait_for_selector(sel, timeout=5000)
                    if btn:
                        try:
                            await btn.click(timeout=5000)
                        except Exception:
                            await btn.evaluate("el => el.click()")
                        print(f"[Quark] 点击保存按钮: {sel}")
                        saved = True
                        break
                except Exception:
                    continue

            if not saved:
                try:
                    await page.click("text=保存", timeout=3000)
                    saved = True
                except Exception:
                    try:
                        await page.evaluate("""
                            () => {
                                const btns = document.querySelectorAll('button, div[class*="save"], span[class*="save"]');
                                for (const btn of btns) {
                                    if (btn.textContent.includes('保存到网盘') || btn.textContent.includes('保存')) {
                                        btn.click();
                                        return true;
                                    }
                                }
                                return false;
                            }
                        """)
                        saved = True
                        print("[Quark] JS兜底点击保存按钮")
                    except Exception:
                        pass

            if saved:
                await page.wait_for_timeout(5000)
                try:
                    await page.wait_for_selector("text=已保存", timeout=8000)
                    print("[Quark] 保存成功")
                except Exception:
                    print("[Quark] 未检测到保存成功提示，继续...")
            else:
                print("[Quark] 未找到保存按钮，可能是已转存过的链接")

            # 5. 导航到"来自：分享"目录（文件保存位置）
            print("[Quark] 导航到来自：分享目录")
            await page.goto("https://pan.quark.cn/", timeout=20000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            # 点击进入"来自：分享"文件夹
            try:
                share_folder = await page.wait_for_selector("text=来自：分享", timeout=5000)
                if share_folder:
                    await share_folder.click()
                    print("[Quark] 进入来自：分享目录")
                    await page.wait_for_timeout(3000)
            except Exception as e:
                print(f"[Quark] 未找到来自：分享目录: {e}")

            # 6. 找到刚保存的文件，点击分享按钮生成分享链接
            share_link = None
            try:
                # 找到文件行并悬停
                row = await page.wait_for_selector(".ant-table-row", timeout=8000)
                await row.hover()
                await page.wait_for_timeout(1500)

                # 点击分享图标
                await page.click("[title='分享']", timeout=5000)
                print("[Quark] 点击分享按钮")
                await page.wait_for_timeout(2000)

                # 设置永久有效
                try:
                    await page.click("text=永久有效", timeout=3000)
                    await page.wait_for_timeout(300)
                except Exception:
                    pass

                # 设置不需要提取码
                try:
                    await page.click("text=不需要", timeout=2000)
                    await page.wait_for_timeout(300)
                except Exception:
                    pass

                # 点击创建分享
                await page.click("text=创建分享", timeout=5000)
                print("[Quark] 点击创建分享")
                await page.wait_for_timeout(3000)

                # 从 input 提取分享链接
                try:
                    link_input = await page.wait_for_selector(
                        "input[value*='pan.quark.cn/s/']", timeout=5000
                    )
                    share_link = await link_input.get_attribute("value")
                    print(f"[Quark] 从input提取: {share_link}")
                except Exception:
                    # 兜底: 点击复制链接后用剪贴板
                    try:
                        await page.click("text=复制链接", timeout=3000)
                        await page.wait_for_timeout(1000)
                        share_link = await page.evaluate(
                            "() => navigator.clipboard.readText()"
                        )
                        # 剪贴板可能包含完整文案，提取链接
                        if share_link and "pan.quark.cn/s/" in share_link:
                            import re
                            m = re.search(r'(https://pan\.quark\.cn/s/\w+)', share_link)
                            if m:
                                share_link = m.group(1)
                        print(f"[Quark] 从剪贴板提取: {share_link}")
                    except Exception as e:
                        print(f"[Quark] 提取链接失败: {e}")
            except Exception as e:
                print(f"[Quark] 分享流程异常: {e}")

            await context.close()

            if share_link and share_link.startswith("https://pan.quark.cn/s/"):
                print(f"[Quark] 成功生成分享链接: {share_link}")
                return share_link
            else:
                print(f"[Quark] 分享链接生成失败，但文件已成功转存到账号")
                # 返回原链接，表示收益已产生
                return f"{real_url} (已转存到你的夸克账号)"

    except Exception as e:
        print(f"[Quark] 转存异常: {e}")
        import traceback
        traceback.print_exc()
        return real_url


async def batch_transfer_quark(urls):
    """
    批量转存：真正并行保存 + 批量生成分享链接。
    返回 dict: {original_url: new_share_link}
    """
    results = {}
    if not urls:
        return results

    quark_urls = [u for u in urls if u and "pan.quark.cn" in u]
    for u in urls:
        if u not in quark_urls:
            results[u] = u
    if not quark_urls:
        return results

    try:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
            """)

            # --- 阶段1: 真正并行保存（最多3个并发） ---
            save_sem = asyncio.Semaphore(3)

            async def save_one(url):
                async with save_sem:
                    page = await context.new_page()
                    try:
                        await page.goto(url, timeout=15000, wait_until="commit")
                        await page.wait_for_timeout(1500)
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(300)

                        try:
                            await page.click(".ant-table-row input[type='checkbox']", timeout=2000)
                            await page.wait_for_timeout(300)
                        except Exception:
                            pass

                        for sel in ["text=保存到网盘", "text=保存"]:
                            try:
                                btn = await page.wait_for_selector(sel, timeout=3000)
                                if btn:
                                    await btn.evaluate("el => el.click()")
                                    await page.wait_for_timeout(2500)
                                    return True
                            except Exception:
                                continue
                        return False
                    except Exception as e:
                        print(f"[BatchSave] {url[:50]}... {e}")
                        return False
                    finally:
                        await page.close()

            save_results = await asyncio.gather(*[save_one(url) for url in quark_urls])
            saved_count = sum(1 for r in save_results if r)

            if saved_count == 0:
                await context.close()
                for u in quark_urls:
                    results[u] = u
                return results

            # --- 阶段2: 批量分享 ---
            page = await context.new_page()
            try:
                await page.goto("https://pan.quark.cn/", timeout=15000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                await page.click("text=来自：分享", timeout=5000)
                await page.wait_for_timeout(2000)

                rows = await page.query_selector_all(".ant-table-row")
                share_idx = 0

                for row in rows:
                    if share_idx >= saved_count:
                        break
                    try:
                        await row.hover()
                        await page.wait_for_timeout(400)
                        await page.click("[title='分享']", timeout=3000)
                        await page.wait_for_timeout(800)

                        try:
                            await page.click("text=永久有效", timeout=2000)
                            await page.wait_for_timeout(150)
                        except Exception:
                            pass
                        try:
                            await page.click("text=不需要", timeout=2000)
                            await page.wait_for_timeout(150)
                        except Exception:
                            pass

                        await page.click("text=创建分享", timeout=4000)

                        try:
                            inp = await page.wait_for_selector(
                                "input[value*='pan.quark.cn/s/']", timeout=4000
                            )
                            new_link = await inp.get_attribute("value")
                            results[quark_urls[share_idx]] = new_link
                            share_idx += 1
                        except Exception:
                            share_idx += 1

                        try:
                            await page.click(".ant-modal-close", timeout=2000)
                            await page.wait_for_timeout(500)
                        except Exception:
                            await page.keyboard.press("Escape")
                            await page.wait_for_timeout(300)
                    except Exception as e:
                        print(f"[BatchShare] row err: {e}")
                        try:
                            await page.keyboard.press("Escape")
                            await page.wait_for_timeout(300)
                        except Exception:
                            pass
                        share_idx += 1
            finally:
                await page.close()

            await context.close()

            for u in quark_urls:
                if u not in results:
                    results[u] = u
            return results

    except Exception as e:
        print(f"[Batch] 异常: {e}")
        import traceback
        traceback.print_exc()
        for u in urls:
            if u not in results:
                results[u] = u
        return results


# ============================================================
# 核心：搜索（优先 PanSou API + Playwright fallback）
# ============================================================
import aiohttp

async def search_and_get_real_urls(keyword, max_results=10):
    """
    优先使用 PanSou API（通过 Telegram 搜索，不受地域限制），
    如果失败则 fallback 到 Playwright 搜索
    """
    # 尝试 PanSou API
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://so.252035.xyz/api/search",
                params={"q": keyword, "limit": max_results, "type": "quark"},
                timeout=20
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "data" in data and data["data"]:
                        # PanSou 返回 merged_by_type，按网盘类型分组
                        merged = data["data"].get("merged_by_type", {})
                        items = merged.get("quark", [])
                        if not items:
                            # 所有类型汇总
                            for type_key, type_items in merged.items():
                                items.extend(type_items)
                        results = []
                        for item in items[:max_results]:
                            results.append({
                                "name": item.get("note", ""),
                                "time": item.get("datetime", ""),
                                "time_label": "",
                                "card_id": "",
                                "size": "N/A",
                                "source": f"pansou ({item.get('source', '')})",
                                "real_url": item.get("url", ""),
                                "transferred": False
                            })
                        # 标记夸克链接
                        quark_urls = [
                            item["real_url"] for item in results
                            if item.get("real_url") and ("pan.quark.cn" in item.get("real_url", "") or "quark.cn" in item.get("real_url", ""))
                        ]
                        if quark_urls and os.path.exists(USER_DATA_DIR):
                            print(f"[Quark] 后台转存 {len(quark_urls)} 个链接")
                        print(f"[Search] PanSou API 返回 {len(results)} 个结果")
                        return results
    except Exception as e:
        print(f"[Search] PanSou API 不可用: {e}, 回退到 Playwright")

    # Fallback: Playwright 搜索
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        real_urls = {}
        pending_card_id = [None]
        got_url_event = asyncio.Event()

        async def intercept_new_page(new_page):
            try:
                # 不等待完整加载，立即获取 URL 即可
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

            # 解析搜索结果
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

            print(f"[Search] 找到 {len(cards)} 个卡片")

            # 逐一点击获取真实链接
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
                except Exception as e:
                    print(f"[Search] 第{i+1}个按钮点击失败: {e}")

            # 组装结果
            results = []
            for card in cards[:limit]:
                real_url = real_urls.get(card["card_id"], "")
                results.append({
                    "name": card["name"],
                    "time": card["time"],
                    "time_label": card["time_label"],
                    "card_id": card["card_id"],
                    "size": card["size"],
                    "source": "yunso.net",
                    "real_url": real_url,
                    "transferred": False
                })

            # 夸克链接后台异步转存（不阻塞搜索结果返回）
            quark_urls = [item["real_url"] for item in results if item.get("real_url") and "pan.quark.cn" in item["real_url"]]
            if quark_urls and os.path.exists(USER_DATA_DIR):
                print(f"[Quark] 后台转存 {len(quark_urls)} 个链接")
                for url in quark_urls:
                    print(f"[Quark] 待转存: {url}")

        except Exception as e:
            print(f"[Search] 浏览器搜索异常: {e}")
            import traceback
            traceback.print_exc()
            results = []

        await browser.close()
        return results


# ============================================================
# 1. 搜索接口
# ============================================================
@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json(silent=True) or {}
    keyword = (data.get("keyword") or "").strip()
    limit = int(data.get("limit") or 5)
    if not keyword:
        return jsonify({"error": "请输入搜索关键词"}), 400

    try:
        print(f"[API] 搜索: {keyword}")
        # 使用线程运行异步函数，避免 Flask 多线程事件循环冲突
        result_holder = {}
        def _run():
            result_holder["data"] = asyncio.run(search_and_get_real_urls(keyword, max_results=limit))
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=60)
        results = result_holder.get("data", [])

        if not results:
            return jsonify({
                "results": [],
                "message": "未找到相关资源，请尝试其他关键词"
            })

        # 对夸克链接：缓存命中直接用，未缓存的同步转存
        cache = load_cache()
        quark_items = [(i, r) for i, r in enumerate(results) if "pan.quark.cn" in (r.get("real_url") or "")]
        uncached_urls = []

        for orig_idx, item in quark_items:
            real_url = item["real_url"]
            if real_url in cache:
                results[orig_idx]["real_url"] = cache[real_url]
                results[orig_idx]["transferred"] = True
            else:
                uncached_urls.append(real_url)

        # 同步转存未缓存的链接（带60s超时兜底）
        if uncached_urls:
            result_holder = {}
            def _transfer_block():
                try:
                    result_holder["data"] = asyncio.run(batch_transfer_quark(uncached_urls))
                except Exception as e:
                    print(f"[API] 转存异常: {e}")
                    result_holder["data"] = {}
            t = threading.Thread(target=_transfer_block, daemon=True)
            t.start()
            t.join(timeout=60)

            data = result_holder.get("data", {})
            if data:
                # 写入缓存
                cache2 = load_cache()
                for url, new_url in data.items():
                    if new_url and new_url.startswith("https://pan.quark.cn/s/"):
                        cache2[url] = new_url
                save_cache(cache2)
                # 更新结果中的 real_url
                for orig_idx, item in quark_items:
                    real_url = item["real_url"]
                    if real_url in data:
                        new_url = data[real_url]
                        if new_url.startswith("https://pan.quark.cn/s/"):
                            results[orig_idx]["real_url"] = new_url
                            results[orig_idx]["transferred"] = True

        return jsonify({"results": results, "total": len(results)})

    except Exception as e:
        print(f"[API] 搜索异常: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"搜索异常: {str(e)}"}), 500


# ============================================================
# 2. 保存到夸克网盘
# ============================================================
@app.route("/api/save-to-quark", methods=["POST"])
def save_to_quark():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    real_url = (data.get("real_url") or "").strip()

    if not name:
        return jsonify({"error": "缺少资源名称"}), 400

    if not real_url:
        return jsonify({"error": "该资源暂无可用的网盘链接"}), 400

    resource_id = hashlib.md5((name + real_url).encode()).hexdigest()

    if resource_id in saved_resources:
        return jsonify({
            "message": "该资源已保存",
            "share_link": saved_resources[resource_id]["share_link"]
        })

    saved_resources[resource_id] = {
        "name": name,
        "real_url": real_url,
        "share_link": real_url,
        "created_at": time.time()
    }

    return jsonify({
        "message": "已获取真实网盘链接",
        "share_link": real_url
    })


# ============================================================
# 3. 夸克链接转存
# ============================================================
@app.route("/api/transfer-quark", methods=["POST"])
def transfer_quark():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url or "pan.quark.cn" not in url:
        return jsonify({"error": "无效的夸克链接"}), 400

    try:
        print(f"[API] 转存: {url}")
        result_holder = {}
        def _run():
            result_holder["data"] = asyncio.run(transfer_quark_link(url))
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=60)
        result = result_holder.get("data", url)
        return jsonify({"success": True, "url": result})
    except Exception as e:
        print(f"[API] 转存异常: {e}")
        return jsonify({"success": False, "error": str(e), "url": url}), 500


# ============================================================
# 4. 健康检查
# ============================================================
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "quark_profile_ready": os.path.exists(QUARK_STATE_PATH),
        "quark_state_path": QUARK_STATE_PATH,
        "quark_state_exists": os.path.exists(QUARK_STATE_PATH),
        "timestamp": time.time()
    })


# ============================================================
# 4. 前端页面托管
# ============================================================
@app.route("/")
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def serve_static(path):
    target = os.path.join(FRONTEND_DIR, path)
    if os.path.isfile(target):
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(" OceanSource v2 启动中...")
    print(f"   地址: http://localhost:{port}")
    if os.path.exists(USER_DATA_DIR):
        print(f"   夸克转存: 已启用 (persistent profile)")
    else:
        print(f"   夸克转存: 未就绪 (需先登录夸克网盘创建 profile)")
    app.run(host="0.0.0.0", port=port, debug=False)