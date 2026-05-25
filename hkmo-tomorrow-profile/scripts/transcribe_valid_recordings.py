#!/usr/bin/env python3
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


CREATE_TASK_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription"
TASK_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
DEFAULT_MODEL = "paraformer-v2"


def request_json(method, url, api_key=None, body=None, headers=None, timeout=60):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req_headers = {"Content-Type": "application/json"}
    if api_key:
        req_headers["Authorization"] = f"Bearer {api_key}"
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def seconds_from_duration(value):
    parts = str(value or "").split(":")
    if len(parts) != 3:
        return 0
    try:
        hours, minutes, seconds = (int(part) for part in parts)
    except ValueError:
        return 0
    return hours * 3600 + minutes * 60 + seconds


def load_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames or []


def write_csv(path, rows, fieldnames):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def create_transcription_task(api_key, record_url):
    body = {
        "model": DEFAULT_MODEL,
        "input": {"file_urls": [record_url]},
        "parameters": {
            "channel_id": [0],
            "language_hints": ["zh", "yue"],
            "diarization_enabled": True,
            "disfluency_removal_enabled": True,
        },
    }
    res = request_json(
        "POST",
        CREATE_TASK_URL,
        api_key=api_key,
        body=body,
        headers={"X-DashScope-Async": "enable"},
    )
    task_id = ((res.get("output") or {}).get("task_id") or res.get("task_id") or "").strip()
    if not task_id:
        raise RuntimeError(f"ASR任务创建失败: {res}")
    return task_id, res


def poll_task(api_key, task_id, poll_seconds, timeout_seconds):
    deadline = time.time() + timeout_seconds
    last = {}
    while time.time() < deadline:
        last = request_json("GET", TASK_URL.format(task_id=task_id), api_key=api_key)
        output = last.get("output") or {}
        status = str(output.get("task_status") or last.get("task_status") or "").upper()
        if status in {"SUCCEEDED", "SUCCESS"}:
            return last
        if status in {"FAILED", "CANCELED", "UNKNOWN"}:
            raise RuntimeError(f"ASR任务失败 {task_id}: {last}")
        time.sleep(poll_seconds)
    raise TimeoutError(f"ASR任务超时 {task_id}: {last}")


def fetch_transcription_payload(result):
    output = result.get("output") or {}
    results = output.get("results") or result.get("results") or []
    if not results:
        return result
    first = results[0] or {}
    transcription_url = first.get("transcription_url") or first.get("url")
    if not transcription_url:
        return first
    with urllib.request.urlopen(transcription_url, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def flatten_text(value):
    if isinstance(value, str):
        return value.strip()
    chunks = []
    if isinstance(value, list):
        for item in value:
            chunks.append(flatten_text(item))
    elif isinstance(value, dict):
        for key in ("text", "sentence", "content", "transcript"):
            if key in value:
                chunks.append(flatten_text(value.get(key)))
        for key in ("sentences", "transcripts", "paragraphs", "results"):
            if key in value:
                chunks.append(flatten_text(value.get(key)))
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def is_candidate(row):
    return (
        row.get("recording_status") == "已匹配有效录音"
        and row.get("recording_url")
        and not row.get("last_call_transcript", "").strip()
        and seconds_from_duration(row.get("recording_duration")) > 180
    )


def transcribe_row(api_key, row, cache_dir, poll_seconds, timeout_seconds):
    record_id = row.get("recording_id") or row.get("student_name") or str(int(time.time()))
    cache_path = cache_dir / f"{record_id}.json"
    if cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        task_id, create_res = create_transcription_task(api_key, row["recording_url"])
        task_res = poll_task(api_key, task_id, poll_seconds, timeout_seconds)
        transcription = fetch_transcription_payload(task_res)
        payload = {"task_id": task_id, "create": create_res, "task": task_res, "transcription": transcription}
        cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    text = flatten_text(payload.get("transcription") or payload)
    if not text:
        raise RuntimeError(f"未能提取转写文本: {cache_path}")
    row["last_call_transcript"] = text
    row["recording_analysis_source"] = "DashScope ASR"
    summary = row.get("last_call_summary", "").strip()
    if "ASR已转写" not in summary:
        row["last_call_summary"] = f"{summary}；ASR已转写" if summary else "ASR已转写"
    return {"recording_id": record_id, "student_name": row.get("student_name"), "cache": str(cache_path)}


def parse_args():
    parser = argparse.ArgumentParser(description="Transcribe valid owned-CC CRM recordings and update the lesson CSV.")
    parser.add_argument("--input", default="outputs/crm_tomorrow_lessons.csv")
    parser.add_argument("--output", default="outputs/crm_tomorrow_lessons.csv")
    parser.add_argument("--cache-dir", default="outputs/asr_cache")
    parser.add_argument("--report", default="outputs/asr_transcription_report.json")
    parser.add_argument("--limit", type=int, default=0, help="Max recordings to transcribe; 0 means all candidates.")
    parser.add_argument("--poll-seconds", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    return parser.parse_args()


def main():
    args = parse_args()
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise SystemExit("请先设置 DASHSCOPE_API_KEY")

    rows, fieldnames = load_csv(args.input)
    candidates = [row for row in rows if is_candidate(row)]
    if args.limit > 0:
        candidates = candidates[:args.limit]

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    results = []
    failures = []
    for row in candidates:
        try:
            results.append(transcribe_row(api_key, row, cache_dir, args.poll_seconds, args.timeout_seconds))
        except (urllib.error.URLError, RuntimeError, TimeoutError) as exc:
            failures.append({"student_name": row.get("student_name"), "recording_id": row.get("recording_id"), "error": str(exc)})

    write_csv(args.output, rows, fieldnames)
    report = {
        "input": os.path.abspath(args.input),
        "output": os.path.abspath(args.output),
        "candidate_count": len(candidates),
        "success_count": len(results),
        "failure_count": len(failures),
        "results": results,
        "failures": failures,
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
