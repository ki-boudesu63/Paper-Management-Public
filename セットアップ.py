"""Setup script for Paper Management.

Run this once after extracting the distribution.
Double-click on Windows, or run: python セットアップ.py
Requires `uv` to be installed (https://docs.astral.sh/uv/).
"""

from __future__ import annotations

import locale
import os
import shutil
import subprocess
import sys

DEFAULT_LANGUAGE = "ja"

MESSAGES: dict[str, dict[str, str]] = {
    "ja": {
        "title": "  Paper Management セットアップ",
        "program_files_blocked": (
            "[エラー] このフォルダは Program Files 配下に置かれています。"
        ),
        "program_files_reason": (
            "  Program Files 配下は書き込みが制限されており、"
            "依存パッケージのインストール（.venv の作成）に失敗します。"
        ),
        "program_files_fix": (
            "  フォルダごと書き込み可能な場所（例: ドキュメント フォルダ、"
            "D ドライブ直下）に移動してから、セットアップを再実行してください。"
        ),
        "uv_detected": "[OK] uv を検出しました: {version}",
        "uv_missing": "[エラー] uv が見つかりません。",
        "uv_install": (
            "  先に uv をインストールしてください: https://docs.astral.sh/uv/"
        ),
        "uv_retry": "  インストール後、このセットアップを再実行してください。",
        "syncing": "\n依存パッケージを同期しています（uv sync）...",
        "sync_failed": "[エラー] uv sync に失敗しました。",
        "sync_ok": "[OK] 依存パッケージを同期しました。",
        "config_exists": "[OK] config.yaml は既に存在します（上書きしません）。",
        "config_created": (
            "[OK] config.yaml.example から config.yaml を作成しました。"
        ),
        "config_missing": "[警告] config.yaml.example が見つかりませんでした。",
        "complete": "  セットアップ完了",
        "next_steps": "次の手順:",
        "step1_line1": "  1. vault_template/paper_management フォルダを、お使いの",
        "step1_line2": "     Obsidian Vault のルート直下にコピーする",
        "step2": "  2. 起動.bat をダブルクリックしてアプリを起動する",
        "step3": "  3. ブラウザの「設定」画面で各フォルダのパスを設定する",
        "readme": "  詳細は README.md を参照してください。",
        "press_enter": "\nEnter キーで閉じます...",
    },
    "en": {
        "title": "  Paper Management Setup",
        "program_files_blocked": (
            "[ERROR] This folder is located under Program Files."
        ),
        "program_files_reason": (
            "  Program Files is write-restricted, so installing dependencies "
            "(creating .venv) will fail."
        ),
        "program_files_fix": (
            "  Move the whole folder to a writable location (for example your "
            "Documents folder, or the root of the D: drive), then run setup again."
        ),
        "uv_detected": "[OK] Detected uv: {version}",
        "uv_missing": "[ERROR] uv was not found.",
        "uv_install": "  Install uv first: https://docs.astral.sh/uv/",
        "uv_retry": "  After installing uv, run this setup again.",
        "syncing": "\nSyncing dependency packages (uv sync)...",
        "sync_failed": "[ERROR] uv sync failed.",
        "sync_ok": "[OK] Dependency packages synced.",
        "config_exists": "[OK] config.yaml already exists; leaving it unchanged.",
        "config_created": "[OK] Created config.yaml from config.yaml.example.",
        "config_missing": "[WARNING] config.yaml.example was not found.",
        "complete": "  Setup complete",
        "next_steps": "Next steps:",
        "step1_line1": "  1. Copy the vault_template/paper_management folder",
        "step1_line2": "     directly under your Obsidian Vault root.",
        "step2": "  2. Double-click 起動.bat to start the app.",
        "step3": "  3. Set each folder path on the Settings page in your browser.",
        "readme": "  See README.md for details.",
        "press_enter": "\nPress Enter to close...",
    },
    "zh": {
        "title": "  Paper Management 设置",
        "program_files_blocked": "[错误] 此文件夹位于 Program Files 目录下。",
        "program_files_reason": (
            "  Program Files 目录受写入限制，安装依赖包（创建 .venv）会失败。"
        ),
        "program_files_fix": (
            "  请将整个文件夹移动到可写入的位置（例如「文档」文件夹或 D 盘根目录），"
            "然后重新运行设置。"
        ),
        "uv_detected": "[OK] 已检测到 uv: {version}",
        "uv_missing": "[错误] 未找到 uv。",
        "uv_install": "  请先安装 uv: https://docs.astral.sh/uv/",
        "uv_retry": "  安装 uv 后，请重新运行此设置脚本。",
        "syncing": "\n正在同步依赖包 (uv sync)...",
        "sync_failed": "[错误] uv sync 失败。",
        "sync_ok": "[OK] 已同步依赖包。",
        "config_exists": "[OK] config.yaml 已存在；不会覆盖。",
        "config_created": "[OK] 已从 config.yaml.example 创建 config.yaml。",
        "config_missing": "[警告] 未找到 config.yaml.example。",
        "complete": "  设置完成",
        "next_steps": "后续步骤:",
        "step1_line1": "  1. 将 vault_template/paper_management 文件夹",
        "step1_line2": "     复制到你的 Obsidian Vault 根目录下。",
        "step2": "  2. 双击 起動.bat 启动应用。",
        "step3": "  3. 在浏览器的“设置”页面配置各文件夹路径。",
        "readme": "  详情请参阅 README.md。",
        "press_enter": "\n按 Enter 键关闭...",
    },
}


def _configure_console_output() -> None:
    """Use UTF-8 output so Chinese text does not fail on cp932 terminals."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _language_from_locale(value: str | None) -> str | None:
    """Map a locale name to a supported language."""
    normalized = (value or "").strip().lower().replace("_", "-")
    if not normalized:
        return None
    if normalized.startswith("ja") or normalized.startswith("japanese"):
        return "ja"
    if normalized.startswith("en") or normalized.startswith("english"):
        return "en"
    if normalized.startswith("zh") or normalized.startswith("chinese"):
        return "zh"
    return None


def _detect_language() -> str:
    """Detect setup language from the OS locale, falling back to Japanese."""
    candidates: list[str | None] = []

    # config.yaml does not exist yet during setup, so use OS locale signals.
    try:
        candidates.append(locale.setlocale(locale.LC_CTYPE, ""))
    except locale.Error:
        pass

    try:
        candidates.append(locale.getlocale()[0])
    except ValueError:
        pass

    candidates.extend(
        os.environ.get(name) for name in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE")
    )

    for candidate in candidates:
        language = _language_from_locale(candidate)
        if language is not None:
            return language

    return DEFAULT_LANGUAGE


def _t(language: str, key: str, **kwargs: object) -> str:
    """Translate a console message."""
    return MESSAGES.get(language, MESSAGES[DEFAULT_LANGUAGE])[key].format(**kwargs)


def _is_under_program_files(path: str) -> bool:
    """Return True if the path lies inside a Windows Program Files directory."""
    if os.name != "nt":
        return False
    target = os.path.normcase(os.path.abspath(path))
    for env_name in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        root = os.environ.get(env_name)
        if not root:
            continue
        root = os.path.normcase(os.path.abspath(root))
        if target == root or target.startswith(root + os.sep):
            return True
    return False


def _find_uv() -> str:
    """Return the uv executable path, preferring a copy bundled next to this script."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bundled = os.path.join(script_dir, "uv.exe" if os.name == "nt" else "uv")
    return bundled if os.path.exists(bundled) else "uv"


def main() -> None:
    """Run first-time setup: sync dependencies and create config.yaml."""
    _configure_console_output()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    language = _detect_language()
    uv_executable = _find_uv()

    print("=" * 50)
    print(_t(language, "title"))
    print("=" * 50)
    print()

    # Abort early if installed under a write-restricted Program Files directory.
    if _is_under_program_files(script_dir):
        print(_t(language, "program_files_blocked"))
        print(_t(language, "program_files_reason"))
        print(_t(language, "program_files_fix"))
        input(_t(language, "press_enter"))
        sys.exit(1)

    # Step 1: check that uv is available
    try:
        result = subprocess.run(
            [uv_executable, "--version"], capture_output=True, text=True, check=False
        )
        print(_t(language, "uv_detected", version=result.stdout.strip()))
    except FileNotFoundError:
        print(_t(language, "uv_missing"))
        print(_t(language, "uv_install"))
        print(_t(language, "uv_retry"))
        input(_t(language, "press_enter"))
        sys.exit(1)

    # Step 2: sync dependencies
    print(_t(language, "syncing"))
    sync = subprocess.run([uv_executable, "sync"], cwd=script_dir, check=False)
    if sync.returncode != 0:
        print(_t(language, "sync_failed"))
        input(_t(language, "press_enter"))
        sys.exit(1)
    print(_t(language, "sync_ok"))

    # Step 3: prepare config.yaml from the example
    if os.path.exists("config.yaml"):
        print(_t(language, "config_exists"))
    elif os.path.exists("config.yaml.example"):
        shutil.copyfile("config.yaml.example", "config.yaml")
        print(_t(language, "config_created"))
    else:
        print(_t(language, "config_missing"))

    print()
    print("=" * 50)
    print(_t(language, "complete"))
    print("=" * 50)
    print()
    print(_t(language, "next_steps"))
    print(_t(language, "step1_line1"))
    print(_t(language, "step1_line2"))
    print(_t(language, "step2"))
    print(_t(language, "step3"))
    print()
    print(_t(language, "readme"))
    input(_t(language, "press_enter"))


if __name__ == "__main__":
    main()
