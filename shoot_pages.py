#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""shoot_pages.py - 用 CDP 截图 show_log.html / show_decode.html 到 assets/。"""
import os, time, shutil, tempfile, subprocess, json, urllib.request
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("drive_demo", os.path.join(HERE, "drive_demo.py"))
dd = importlib.util.module_from_spec(spec); spec.loader.exec_module(dd)

ASSETS = dd.ASSETS
CHROME = dd.CHROME
PORT = 9222
USER_DATA = os.path.join(tempfile.gettempdir(), "mdbeacon_chrome_profile2")


def main():
    if os.path.exists(USER_DATA):
        shutil.rmtree(USER_DATA, ignore_errors=True)
    proc = subprocess.Popen([
        CHROME, f"--remote-debugging-port={PORT}", f"--user-data-dir={USER_DATA}",
        "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
        "--remote-allow-origins=*", "--window-size=1240,760",
        "http://127.0.0.1:8091/show_log.html",
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
        time.sleep(1.5)
        cdp.shot(os.path.join(ASSETS, "mdbeacon-server-log.png"))
        cdp.call("Page.navigate", {"url": "http://127.0.0.1:8091/show_decode.html"})
        time.sleep(1.5)
        cdp.shot(os.path.join(ASSETS, "mdbeacon-decode.png"))
        cdp.close()
    finally:
        try: proc.terminate(); proc.wait(timeout=5)
        except Exception: proc.kill()
    print("[done]")


if __name__ == "__main__":
    main()
