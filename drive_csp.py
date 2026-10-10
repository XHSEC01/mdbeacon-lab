#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""drive_csp.py - CSP 防御版演示：跑 Turn1/Turn2，截图被拦截的页面 + 空日志。"""
import os, time, shutil, tempfile, subprocess, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("drive_demo", os.path.join(HERE, "drive_demo.py"))
dd = importlib.util.module_from_spec(spec); spec.loader.exec_module(dd)

ASSETS = dd.ASSETS
CHROME = dd.CHROME
PORT = 9222
USER_DATA = os.path.join(tempfile.gettempdir(), "mdbeacon_chrome_profile_csp")
UI_URL = "http://127.0.0.1:8091/index_csp.html"


def main():
    if os.path.exists(USER_DATA):
        shutil.rmtree(USER_DATA, ignore_errors=True)
    print(f"[launch] chrome -> {UI_URL}")
    proc = subprocess.Popen([
        CHROME, f"--remote-debugging-port={PORT}", f"--user-data-dir={USER_DATA}",
        "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
        "--remote-allow-origins=*", "--window-size=1240,860", UI_URL,
    ])
    try:
        dd.wait_devtools()
        tab = None
        for _ in range(40):
            for t in dd.http_json(f"http://127.0.0.1:{PORT}/json"):
                if t.get("type") == "page" and "127.0.0.1:8091" in t.get("url", ""):
                    tab = t; break
            if tab: break
            time.sleep(0.4)
        if not tab:
            print("[err] no tab"); proc.kill(); return
        cdp = dd.CDP(tab["webSocketDebuggerUrl"])
        cdp.call("Page.enable"); cdp.call("Runtime.enable")
        cdp.call("Page.navigate", {"url": UI_URL})
        time.sleep(2.0)

        # Turn 1
        cdp.eval("window.send('我的邮箱是 victim@example.com，帮我记一下')")
        r1 = dd.wait_reply  # reuse? no, wait_reply is module-level function in drive_demo
        # wait_reply signature: wait_reply(cdp, prev, timeout)
        prev = cdp.eval("document.getElementById('rawmd').textContent") or ""
        r1 = dd.wait_reply(cdp, prev)
        print(f"[turn1] {(r1 or '')[:120]!r}")

        # Turn 2
        cdp.eval("document.getElementById('inject').click()")
        time.sleep(0.3)
        cdp.eval("document.getElementById('send').click()")
        r2 = dd.wait_reply(cdp, r1 or "")
        print(f"[turn2] {(r2 or '')[:200]!r}")
        time.sleep(3.0)
        cdp.eval("document.querySelector('details.raw').open = true")
        time.sleep(1.5)
        cdp.shot(os.path.join(ASSETS, "mdbeacon-csp-blocked.png"))

        # 截图 exfil.log（应只有 server start，无 exfil hit）
        cdp.call("Page.navigate", {"url": "http://127.0.0.1:8091/show_log.html"})
        time.sleep(1.5)
        cdp.shot(os.path.join(ASSETS, "mdbeacon-csp-server-log.png"))
        cdp.close()
    finally:
        try: proc.terminate(); proc.wait(timeout=5)
        except Exception: proc.kill()
    print("[done]")


if __name__ == "__main__":
    main()
