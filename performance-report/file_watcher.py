# -*- coding: utf-8 -*-
"""
文件变动监控脚本
监控益智业绩表.xlsx，检测到更新后自动发送钉钉汇报
状态保存在 last_mtime.txt
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

EXCEL_PATH = r"C:\Users\wangzengzeng\Desktop\益智业绩表.xlsx"
STATE_FILE = os.path.join(os.path.dirname(__file__), "last_mtime.txt")

def get_last_mtime():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_mtime(mtime):
    with open(STATE_FILE, 'w') as f:
        f.write(mtime)

def check_and_run():
    if not os.path.exists(EXCEL_PATH):
        print(f"❌ 文件不存在: {EXCEL_PATH}")
        return False

    current_mtime = str(int(os.path.getmtime(EXCEL_PATH)))
    last_mtime = get_last_mtime()

    if current_mtime != last_mtime:
        print(f"📁 检测到文件更新: {EXCEL_PATH}")
        save_mtime(current_mtime)
        return True
    else:
        print(f"✅ 文件无变化 (mtime={current_mtime})")
        return False

if __name__ == "__main__":
    changed = check_and_run()
    if changed:
        # 文件有更新，运行汇报脚本
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), "read_report.py")
        result = subprocess.run(
            ["uv", "run", "python", script_path],
            capture_output=False,
            cwd=os.path.dirname(os.path.dirname(__file__))
        )
        sys.exit(result.returncode)
    else:
        print("无变化，不发送汇报")
