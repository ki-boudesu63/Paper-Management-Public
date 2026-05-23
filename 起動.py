"""Launcher script for Paper Management application.

Double-click this file on Windows to start the server and open the browser.
Assumes system Python is available and `uv` is installed.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import webbrowser
from urllib.error import URLError
from urllib.request import urlopen

# ============================================================
# Constants
# ============================================================

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 12000
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
POLL_INTERVAL_SEC = 0.5
POLL_TIMEOUT_SEC = 30
DEFAULT_LANGUAGE = "ja"
SUPPORTED_LANGUAGES = ("ja", "en", "zh")

MESSAGES: dict[str, dict[str, str]] = {
    "ja": {
        "starting": "  論文管理アプリを起動しています...",
        "server_url": "\n  サーバURL: {url}",
        "stop_instruction": "  終了するには Ctrl+C を押すか、このウィンドウを閉じてください。\n",
        "server_timeout": (
            "\n[WARNING] {timeout} 秒以内にサーバが応答しませんでした。"
            "手動で {url} を開いてください。"
        ),
        "server_exit": "\nサーバが終了コード {code} で停止しました。",
        "uv_missing": (
            "\n[ERROR] 'uv' コマンドが見つかりません。\n"
            "uv をインストールしてください: https://docs.astral.sh/uv/\n"
            "または PATH に uv が含まれていることを確認してください。"
        ),
        "server_stopped": "\n\nサーバを停止しました。",
        "unexpected_error": "\n[ERROR] 予期しないエラーが発生しました: {error}",
        "press_enter": "Enter キーで閉じます...",
    },
    "en": {
        "starting": "  Starting Paper Management app...",
        "server_url": "\n  Server URL: {url}",
        "stop_instruction": "  Press Ctrl+C or close this window to stop.\n",
        "server_timeout": (
            "\n[WARNING] The server did not respond within {timeout} seconds. "
            "Open {url} manually."
        ),
        "server_exit": "\nThe server stopped with exit code {code}.",
        "uv_missing": (
            "\n[ERROR] The 'uv' command was not found.\n"
            "Install uv: https://docs.astral.sh/uv/\n"
            "Or confirm that uv is included in PATH."
        ),
        "server_stopped": "\n\nServer stopped.",
        "unexpected_error": "\n[ERROR] An unexpected error occurred: {error}",
        "press_enter": "Press Enter to close...",
    },
    "zh": {
        "starting": "  正在启动论文管理应用...",
        "server_url": "\n  服务器 URL: {url}",
        "stop_instruction": "  按 Ctrl+C 或关闭此窗口即可停止。\n",
        "server_timeout": (
            "\n[WARNING] 服务器在 {timeout} 秒内没有响应。请手动打开 {url}。"
        ),
        "server_exit": "\n服务器已停止，退出代码为 {code}。",
        "uv_missing": (
            "\n[ERROR] 未找到 'uv' 命令。\n"
            "请安装 uv: https://docs.astral.sh/uv/\n"
            "或者确认 PATH 中包含 uv。"
        ),
        "server_stopped": "\n\n服务器已停止。",
        "unexpected_error": "\n[ERROR] 发生意外错误: {error}",
        "press_enter": "按 Enter 键关闭...",
    },
}


def _configure_console_output() -> None:
    """Use UTF-8 output so Chinese text does not fail on cp932 terminals."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _normalize_language(value: str | None) -> str:
    """Normalize a configured language value to a supported locale."""
    language = (value or "").strip().lower().replace("_", "-")
    for supported_language in SUPPORTED_LANGUAGES:
        if language == supported_language or language.startswith(
            f"{supported_language}-"
        ):
            return supported_language
    return DEFAULT_LANGUAGE


def _read_config_language(config_path: str = "config.yaml") -> str:
    """Read the top-level language field from config.yaml."""
    try:
        with open(config_path, encoding="utf-8") as config_file:
            for line in config_file:
                if line[:1].isspace():
                    continue
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                key, separator, value = stripped.partition(":")
                if key == "language" and separator:
                    raw_value = value.split("#", 1)[0].strip().strip("'\"")
                    return _normalize_language(raw_value)
    except (OSError, UnicodeDecodeError):
        return DEFAULT_LANGUAGE

    return DEFAULT_LANGUAGE


def _t(language: str, key: str, **kwargs: object) -> str:
    """Translate a console message."""
    return MESSAGES.get(language, MESSAGES[DEFAULT_LANGUAGE])[key].format(**kwargs)


def _find_uv() -> str:
    """Return the uv executable path, preferring a copy bundled next to this script."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bundled = os.path.join(script_dir, "uv.exe" if os.name == "nt" else "uv")
    return bundled if os.path.exists(bundled) else "uv"


def _wait_and_open_browser(language: str) -> None:
    """Poll the server until it responds, then open the default browser."""
    deadline = time.monotonic() + POLL_TIMEOUT_SEC
    while time.monotonic() < deadline:
        try:
            urlopen(SERVER_URL, timeout=2)  # noqa: S310
            webbrowser.open(SERVER_URL)
            return
        except (URLError, OSError):
            time.sleep(POLL_INTERVAL_SEC)
    print(_t(language, "server_timeout", timeout=POLL_TIMEOUT_SEC, url=SERVER_URL))


def main() -> None:
    """Entry point: start the server subprocess and open the browser."""
    _configure_console_output()

    # Move cwd to the directory containing this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    language = _read_config_language()
    uv_executable = _find_uv()

    print("=" * 50)
    print(_t(language, "starting"))
    print("=" * 50)
    print(_t(language, "server_url", url=SERVER_URL))
    print(_t(language, "stop_instruction"))

    # Start the browser-opener thread before launching the server
    browser_thread = threading.Thread(
        target=_wait_and_open_browser, args=(language,), daemon=True
    )
    browser_thread.start()

    try:
        process = subprocess.run(
            [uv_executable, "run", "python", "run.py"],
            cwd=script_dir,
        )
        if process.returncode != 0:
            print(_t(language, "server_exit", code=process.returncode))
            input(_t(language, "press_enter"))
    except FileNotFoundError:
        print(_t(language, "uv_missing"))
        input(_t(language, "press_enter"))
        sys.exit(1)
    except KeyboardInterrupt:
        print(_t(language, "server_stopped"))
    except Exception as exc:
        print(_t(language, "unexpected_error", error=exc))
        input(_t(language, "press_enter"))
        sys.exit(1)


if __name__ == "__main__":
    main()
