#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from datetime import date, datetime, timedelta


def run(cmd, env=None):
    print("+", " ".join(cmd))
    completed = subprocess.run(cmd, env=env)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def parse_args():
    parser = argparse.ArgumentParser(description="Run HK/MO tomorrow lesson profile workflow and send Feishu links.")
    parser.add_argument("--date", default=(date.today() + timedelta(days=1)).isoformat())
    parser.add_argument("--skip-asr", action="store_true")
    parser.add_argument("--open-id", default=os.environ.get("FEISHU_OPEN_ID", ""))
    return parser.parse_args()


def main():
    args = parse_args()
    env = os.environ.copy()
    day_label = f"{datetime.strptime(args.date, '%Y-%m-%d').day}号"
    run([
        sys.executable,
        "scripts/fetch_crm_wait_class.py",
        "--date",
        args.date,
        "--output",
        "outputs/crm_tomorrow_lessons.csv",
        "--raw-output",
        "outputs/crm_wait_class_raw.json",
        "--include-recordings",
        "--recording-output",
        "outputs/crm_recording_candidates.json",
    ], env=env)

    if not args.skip_asr:
        run([
            sys.executable,
            "scripts/transcribe_valid_recordings.py",
            "--input",
            "outputs/crm_tomorrow_lessons.csv",
            "--output",
            "outputs/crm_tomorrow_lessons.csv",
            "--cache-dir",
            "outputs/asr_cache",
            "--report",
            "outputs/asr_transcription_report.json",
        ], env=env)

    for group in ("02组", "03组"):
        group_label = f"港澳CC{group.replace('组', '')}组{day_label}明日待上课画像分析"
        cmd = [
            sys.executable,
            "scripts/feishu_docx_native.py",
            "--group",
            group,
            "--title-date",
            group_label,
        ]
        if args.open_id:
            cmd.extend(["--send-open-id", args.open_id])
        run(cmd, env=env)


if __name__ == "__main__":
    main()
