#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每月更新 README 的保活时间戳并提交，防止仓库 60 天无活动导致定时 Actions 被自动停用。"""

import datetime
import pathlib
import re
import sys

README = pathlib.Path(__file__).resolve().parents[2] / "README.md"
MARK = "最近自动保活："


def main() -> int:
    if not README.exists():
        print(f"[FATAL] 未找到 {README}")
        return 1
    text = README.read_text(encoding="utf-8")
    if MARK not in text:
        print(f"[FATAL] README 缺少保活标记行「{MARK}」，请先在 README 中添加")
        return 1

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    new_text, n = re.subn(rf"{re.escape(MARK)}.*", f"{MARK}{stamp}", text)
    if n != 1:
        print(f"[FATAL] 保活标记行出现 {n} 次（应为 1 次），拒绝修改")
        return 1
    if new_text == text:
        print("[INFO] 时间戳未变化，跳过")
        return 0

    README.write_text(new_text, encoding="utf-8")
    print(f"[OK] 保活时间戳已更新为 {stamp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
