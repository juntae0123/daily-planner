import threading
import time
import socket

import uvicorn
import webview

PORT = 8177


def run_server():
    # reload는 스레드에서 못 씀 — 창 모드는 reload 없이
    uvicorn.run("server.main:app", host="127.0.0.1", port=PORT, log_level="info")


def wait_port(port, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.3)
    return False


if __name__ == "__main__":
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    if not wait_port(PORT):
        raise SystemExit(f"서버가 {PORT} 포트에서 안 떴다. 기존 uvicorn이 포트 잡고 있는지 확인.")
    webview.create_window(
        "일해라 김준태",
        f"http://127.0.0.1:{PORT}",
        width=1280,
        height=860,
        min_size=(900, 600),
    )
    webview.start()
