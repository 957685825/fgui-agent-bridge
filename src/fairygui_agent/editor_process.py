"""只读识别正在运行的 FairyGUI Editor。"""

from __future__ import annotations

import csv
import os
import plistlib
import re
import subprocess
import sys
from pathlib import Path

EDITOR_ENV = "FAIRYGUI_EDITOR_PATH"
LEGACY_EDITOR_ENV = "FAIRYGUI_EDITOR_APP"


class EditorProcess:
    def __init__(self, editor_path: str | None = None) -> None:
        configured = editor_path or os.environ.get(EDITOR_ENV) or os.environ.get(LEGACY_EDITOR_ENV)
        self.path = Path(configured).expanduser() if configured else None

    def _mac_executable(self) -> str | None:
        if self.path is None:
            return "FairyGUI-Editor"
        if self.path.suffix.lower() != ".app":
            return self.path.name
        # .app 可以被重命名，实际进程名以应用包声明的可执行文件为准。
        try:
            with (self.path / "Contents" / "Info.plist").open("rb") as info:
                name = plistlib.load(info).get("CFBundleExecutable")
        except (OSError, ValueError, plistlib.InvalidFileException):
            return None
        return name if isinstance(name, str) and name else None

    def is_running(self) -> bool | None:
        """区分已运行、未运行和系统无法提供进程状态，不触发任何窗口操作。"""
        try:
            if sys.platform == "darwin":
                name = self._mac_executable()
                if not name:
                    return None
                result = subprocess.run(
                    ["/usr/bin/pgrep", "-x", "--", re.escape(name)],
                    capture_output=True, text=True, timeout=2, check=False,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return True
                # 受限环境下 pgrep 可能无法读取进程表，不能把这类失败报告为未运行。
                if result.returncode == 1 and not result.stderr.strip():
                    return False
            elif sys.platform == "win32":
                names = {"fairygui-editor.exe", "fairyeditor.exe"}
                if self.path:
                    names.add(self.path.name.casefold())
                result = subprocess.run(
                    ["tasklist", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, errors="replace", timeout=2, check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if result.returncode == 0:
                    # 只有取得有效的进程记录，才有依据判断编辑器未运行。
                    processes = {row[0].casefold() for row in csv.reader(result.stdout.splitlines())
                                 if len(row) >= 2 and row[1].strip().isdigit()}
                    if processes:
                        return not names.isdisjoint(processes)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return None
