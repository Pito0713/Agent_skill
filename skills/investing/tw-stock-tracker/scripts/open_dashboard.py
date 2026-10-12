"""一鍵打開儀表板：沒在跑就在背景啟動，就緒後用預設瀏覽器開啟。可重複點擊，不會重複啟動。

給桌面懸浮視窗等外部按鈕呼叫：
  /usr/bin/python3 <本 skill>/scripts/open_dashboard.py [--port 8765]
失敗時跳 macOS 通知並以非零結束碼回報，按鈕端不需要解析輸出。
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

import dashboard

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.expanduser("~/.stock-tracker/logs/dashboard.log")
STARTUP_TIMEOUT_SEC = 10
POLL_INTERVAL_SEC = 0.25


def probe(port):
    """'ours'＝這個儀表板在回應；'other'＝埠被別的程式佔用；'down'＝沒有東西在聽。"""
    url = "http://127.0.0.1:%d%s" % (port, dashboard.HEALTH_PATH)
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            return "ours" if response.read() == dashboard.HEALTH_MARKER else "other"
    except urllib.error.HTTPError:
        return "other"
    except (urllib.error.URLError, OSError):
        return "down"


def start_server(port):
    """背景啟動，脫離呼叫端（按鈕程式結束不會連帶關掉儀表板），輸出寫 log。回傳子程序。"""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as log:
        return subprocess.Popen([sys.executable, os.path.join(SCRIPTS_DIR, "dashboard.py"), "--port", str(port)],
                         cwd=SCRIPTS_DIR, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                         start_new_session=True)


def wait_until_ready(port):
    deadline = time.monotonic() + STARTUP_TIMEOUT_SEC
    while time.monotonic() < deadline:
        if probe(port) == "ours":
            return True
        time.sleep(POLL_INTERVAL_SEC)
    return False


def notify(message):
    """macOS 通知；訊息經 json 編碼當成 AppleScript 字串，避免引號注入。"""
    subprocess.run(["osascript", "-e", "display notification %s with title %s"
                    % (json.dumps(message, ensure_ascii=False), json.dumps("台股儀表板"))],
                   check=False, capture_output=True)


def ensure_and_open(port):
    """回傳結束碼。0＝已開啟瀏覽器；1＝啟動逾時；2＝埠被佔用；3＝瀏覽器開不起來。"""
    state = probe(port)
    if state == "other":
        notify("埠 %d 被其他程式佔用，請改用 --port 指定其他埠號" % port)
        return 2
    if state == "down":
        server = start_server(port)
        if not wait_until_ready(port):
            server.terminate()          # 沒就緒就收掉，避免重複點擊累積背景程序
            notify("儀表板 %d 秒內沒有啟動，請看 %s" % (STARTUP_TIMEOUT_SEC, LOG_PATH))
            return 1
    if subprocess.run(["open", "http://127.0.0.1:%d/" % port], check=False).returncode != 0:
        notify("儀表板已在執行，但無法開啟瀏覽器：http://127.0.0.1:%d/" % port)
        return 3
    return 0


def _port(text):
    """埠 0 會讓伺服器綁隨機埠，就緒檢查卻永遠打 0，所以只收 1–65535。"""
    value = int(text)
    if not 1 <= value <= 65535:
        raise argparse.ArgumentTypeError("埠號需介於 1–65535")
    return value


def main():
    parser = argparse.ArgumentParser(description="確保儀表板在跑，並用瀏覽器開啟")
    parser.add_argument("--port", type=_port, default=dashboard.DEFAULT_PORT)
    sys.exit(ensure_and_open(parser.parse_args().port))


if __name__ == "__main__":
    main()
