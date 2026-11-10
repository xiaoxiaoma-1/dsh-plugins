# -*- coding: utf-8 -*-
"""查证 DSH Web 里 dsh-podcast 客户端有没有加载：读 window.__DSH_WORKBENCHES__ 并截图侧栏"""
import asyncio, os, sys, json

URL = os.environ.get('DSH_URL', 'http://127.0.0.1:64652')
OUT = r'E:\desktop\media\_dsh_check.png'
PROFILE = r'E:\desktop\media\_probe_dsh_profile'

sys.path.insert(0, r'E:\tools\DouyinLiveRecorder')
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            PROFILE, channel='msedge', headless=True,
            args=['--lang=zh-CN', '--mute-audio'],
            viewport={'width': 1400, 'height': 900},
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        print('打开', URL, flush=True)
        await page.goto(URL, wait_until='domcontentloaded', timeout=45000)
        await page.wait_for_timeout(9000)

        title = await page.title()
        print('页面标题:', title, flush=True)

        info = await page.evaluate("""() => {
            const reg = window.__DSH_WORKBENCHES__ || null;
            return {
                hasModuleLoader: !!window.__ModuleLoader__,
                registryIsArray: Array.isArray(reg),
                registry: reg ? reg.map(x => ({ id: x.id, title: x.title, desc: x.desc })) : null,
                styleInjected: !!document.getElementById('dsh-podcast-style'),
                bodyText: (document.body.innerText || '').slice(0, 400),
            };
        }""")
        print('--- 运行时状态 ---', flush=True)
        print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)

        await page.screenshot(path=OUT, full_page=False)
        print('截图:', OUT, flush=True)
        await ctx.close()


asyncio.run(main())
