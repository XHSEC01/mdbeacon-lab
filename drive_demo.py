#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mdbeacon-lab / drive_demo.py
CDP 驱动自启动 Chrome 跑完 Turn1/Turn2，Page.captureScreenshot 保存真实 PNG。
用法: py -3 drive_demo.py   依赖: websocket-client
"""
import base64, json, os, shutil, subprocess, sys, tempfile, time, urllib.request
import websocket  # type: ignore

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9222
USER_DATA = os.path.join(tempfile.gettempdir(), "mdbeacon_chrome_profile")
HERE = os.path.dirname(os.path.abspath(__file__))
UI_URL = "http://127.0.0.1:8091/index.html"
ASSETS = r"C:\Users\humia\Desktop\blog\assets"
os.makedirs(ASSETS, exist_ok=True)


def http_json(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def wait_devtools(timeout=30):
    t = time.time()
    while time.time() - t < timeout:
        try:
            return http_json(f"http://127.0.0.1:{PORT}/json")
        except Exception:
            time.sleep(0.4)
    return None


def find_ui_tab():
    for t in http_json(f"http://127.0.0.1:{PORT}/json"):
        if t.get("type") == "page" and "127.0.0.1:8091" in t.get("url", ""):
            return t
    return None


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=15)
        self._id = 0

    def call(self, method, params=None, timeout=180):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method, "params": params or {}}))
        t = time.time()
        while time.time() - t < timeout:
            self.ws.settimeout(max(1, timeout - (time.time() - t)))
            try:
                msg = json.loads(self.ws.recv())
            except Exception as e:
                raise RuntimeError(f"recv failed: {e}")
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError(f"CDP error: {msg['error']}")
                return msg.get("result", {})
        raise TimeoutError(f"{method} timed out")

    def eval(self, expr, await_promise=False, timeout=180):
        r = self.call("Runtime.evaluate", {
            "expression": expr, "awaitPromise": await_promise,
            "returnByValue": True,
        }, timeout=timeout)
        res = r.get("result", {})
        if res.get("subtype") == "error":
            raise RuntimeError(f"JS error: {res.get('description')}")
        return res.get("value")

    def shot(self, path):
        data = self.call("Page.captureScreenshot", {
            "format": "png", "captureBeyondViewport": False,
        })["data"]
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        print(f"[shot] {path}  ({os.path.getsize(path)} bytes)")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def wait_reply(cdp, prev, timeout=300):
    t = time.time()
    while time.time() - t < timeout:
        time.sleep(1.2)
        try:
            cur = cdp.eval("document.getElementById('rawmd').textContent") or ""
            btn = cdp.eval("document.getElementById('send').disabled")
        except Exception:
            continue
        if cur and cur != prev and cur not in ("（尚无回复）", "（已清空）") and not btn:
            return cur
    return None


def main():
    if os.path.exists(USER_DATA):
        shutil.rmtree(USER_DATA, ignore_errors=True)
    print(f"[launch] chrome -> {UI_URL}")
    proc = subprocess.Popen([
        CHROME,
        f"--remote-debugging-port={PORT}",
        f"--user-data-dir={USER_DATA}",
        "--no-first-run", "--no-default-browser-check",
        "--disable-features=Translate",
        "--remote-allow-origins=*",
        "--window-size=1240,860", UI_URL,
    ])
    try:
        if not wait_devtools():
            print("[err] devtools not ready"); proc.kill(); sys.exit(1)
        tab = None
        for _ in range(40):
            tab = find_ui_tab()
            if tab:
                break
            time.sleep(0.5)
        if not tab:
            print("[err] no ui tab"); proc.kill(); sys.exit(1)
        cdp = CDP(tab["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        cdp.call("Page.navigate", {"url": UI_URL})
        time.sleep(2.0)
        cdp.shot(os.path.join(ASSETS, "mdbeacon-ui-ready.png"))

        # Turn 1
        cdp.eval("window.send('我的邮箱是 victim@example.com，帮我记一下')")
        r1 = wait_reply(cdp, "（尚无回复）")
        print(f"[turn1] reply head: {(r1 or '')[:160]!r}")
        cdp.shot(os.path.join(ASSETS, "mdbeacon-turn1.png"))

        # Turn 2: inject carrier then send
        cdp.eval("document.getElementById('inject').click()")
        time.sleep(0.3)
        cdp.eval("document.getElementById('send').click()")
        r2 = wait_reply(cdp, r1 or "")
        print(f"[turn2] reply head: {(r2 or '')[:300]!r}")
        time.sleep(4.0)  # 等像素信标图片加载
        # 展开 raw markdown 面板，让截图能同时看到渲染结果与原始 ![ref](...) 字符串
        cdp.eval("document.querySelector('details.raw').open = true")
        time.sleep(0.5)
        cdp.shot(os.path.join(ASSETS, "mdbeacon-turn2-output.png"))
        print("[turn2] RAW_MD:\n" + (r2 or ""))
        cdp.close()
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    print("[done]")


if __name__ == "__main__":
    main()
