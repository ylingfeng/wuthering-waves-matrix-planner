"""Standalone local planner launcher; no combat imports or game input."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import threading
import webbrowser
from http.server import ThreadingHTTPServer

from matrix_planner import planner_server


def main():
    root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    planner_server.ROOT = root
    if "--smoke-test" in sys.argv:
        import json
        store = planner_server.Store(root)
        result = store.plan(all_characters=True)
        (root / "smoke-test.json").write_text(json.dumps({"characters": len(store.state()["characters"]),
            "teams": len(store.state()["teams"]), "planned": result["count"]}), encoding="utf-8")
        return
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[RotatingFileHandler(logs / "planner.log", maxBytes=2_000_000,
                                                      backupCount=2, encoding="utf-8")])
    # Stable origin preserves browser-local preferences across launches.
    server = ThreadingHTTPServer(("127.0.0.1", 18765), planner_server.Handler)
    server.store = planner_server.Store(root)
    url = f"http://127.0.0.1:{server.server_port}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    import tkinter as tk
    from tkinter import ttk
    window = tk.Tk()
    window.title("矩阵配队工具")
    window.geometry("430x210")
    window.resizable(False, False)
    icon = root / "assets" / "planner.ico"
    if icon.exists():
        window.iconbitmap(str(icon))
    ttk.Label(window, text="矩阵配队工具已启动", font=("Microsoft YaHei", 14)).pack(pady=(22, 10))
    ttk.Label(window, text=url).pack()
    ttk.Label(window, text="关闭此窗口将停止服务；浏览器关闭后可重新打开。").pack(pady=10)
    ttk.Button(window, text="打开配队网页", command=lambda: webbrowser.open(url)).pack(pady=6)
    webbrowser.open(url)
    try:
        window.mainloop()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("启动失败")
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, "启动失败。如已打开工具，请先关闭旧的启动窗口。详情见 logs/planner.log。", "矩阵配队工具", 16)
        raise
