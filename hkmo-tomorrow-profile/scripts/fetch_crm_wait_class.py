#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta


AUTH_BASE = "https://auth.vipthink.cn"
ECC_BASE = "https://gateway-yypt-trans-dept.vipthink.cn"
BIZ_ID_WANDOU = 15
TARGET_GROUPS = ("港澳CC02组", "港澳CC03组")
CSV_FIELDS = [
    "group_name",
    "user_id",
    "student_id",
    "student_name",
    "cc_name",
    "lesson_time",
    "student_age",
    "grade",
    "parent_notes",
    "recording_status",
    "recording_time",
    "recording_duration",
    "recording_cc_name",
    "recording_id",
    "recording_url",
    "recording_analysis_source",
    "last_call_summary",
    "last_call_transcript",
]
MIN_VALID_CALL_SECONDS = 180
BRAND_CODES_WANDOU = ["VIP_WanDou", "WONDER_WanDou", "CSD"]


def request_json(method, url, token=None, body=None, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        bearer = f"Bearer {token}"
        headers.update({"authorization": bearer, "Authorization": bearer, "x-auth-type": "staff"})
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def duration_to_seconds(value):
    text = str(value or "").strip()
    if not text:
        return 0
    parts = text.split(":")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        hours, minutes, seconds = (int(part) for part in parts)
        return hours * 3600 + minutes * 60 + seconds
    if len(parts) == 2 and all(part.isdigit() for part in parts):
        minutes, seconds = (int(part) for part in parts)
        return minutes * 60 + seconds
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else 0


def require_ok(res, label):
    if res.get("code") != 0:
        raise RuntimeError(f"{label}失败: {res}")
    return res


def crm_login(username, password):
    res = request_json(
        "POST",
        f"{AUTH_BASE}/v1/auth/admin/token",
        body={"username": username, "password": password, "__fields": "token,uid"},
    )
    require_ok(res, "CRM登录")
    return res["data"]["token"], res["data"]["uid"]


def enter_wandou_business(token, uid):
    request_json("GET", f"{AUTH_BASE}/v1/auth/admin/token-ugly-crm", token=token)
    res = request_json(
        "POST",
        f"{ECC_BASE}/cc-backend/public/business/setBusinessId",
        token=token,
        body={"biz_id": BIZ_ID_WANDOU, "token": token, "admin_id": uid},
    )
    require_ok(res, "进入豌豆益智业务线")
    cache_res = request_json("POST", f"{ECC_BASE}/cc-backend/oa/cacheDepartment", token=token, body={})
    require_ok(cache_res, "缓存组织架构")


def flatten_org(nodes, path=()):
    for item in nodes or []:
        name = str(item.get("name") or "")
        current_path = path + (name,)
        yield item, current_path
        yield from flatten_org(item.get("children") or [], current_path)


def org_value(item):
    return f"{item.get('pid')}_{item.get('type')}_{item.get('id')}_0"


def get_target_orgs(token):
    res = request_json(
        "POST",
        f"{ECC_BASE}/cc-backend/oa/getDepartment",
        token=token,
        body={"route": "demoCourse/list", "method": "GET", "jobStatus": 1},
    )
    require_ok(res, "读取归属CC组织树")
    matches = {}
    for item, path in flatten_org(res.get("data") or []):
        name = str(item.get("name") or "")
        if name in TARGET_GROUPS:
            matches[name] = {"orgId": org_value(item), "path": " / ".join(path)}
    missing = [name for name in TARGET_GROUPS if name not in matches]
    if missing:
        raise RuntimeError(f"找不到归属CC组别: {', '.join(missing)}")
    return matches


def fetch_wait_class_page(token, target_date, org_ids, page_num=1, page_size=1000):
    params = {
        "startDate": target_date,
        "endDate": target_date,
        "orgIds": ",".join(org_ids),
        "groupType": "",
        "specificUuid": "",
        "timePeriod": "",
        "checkStatus": "0,1,3",
        "sortOrder": "",
        "sortProp": "lst.start_time",
        "pageNum": page_num,
        "pageSize": page_size,
        "tagIdList": "",
    }
    res = request_json("GET", f"{ECC_BASE}/cc-backend/demoCourse/list", token=token, params=params)
    require_ok(res, "读取待上课学员")
    data = res.get("data") or {}
    return data.get("list") or [], int(data.get("total") or 0)


def infer_grade(text):
    patterns = [
        r"小学[一二三四五六]年级",
        r"[一二三四五六]年级",
        r"小[一二三四五六]",
        r"K[1-3]",
        r"幼稚园[低中高]班",
        r"幼兒園[低中高]班",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return ""


def infer_age(text):
    match = re.search(r"(\d{1,2})\s*岁", text)
    if match:
        return match.group(1)
    match = re.search(r"(\d{1,2})\s*歲", text)
    if match:
        return match.group(1)
    return ""


def normalize_group_name(group_name):
    if "02" in group_name:
        return "02组"
    if "03" in group_name:
        return "03组"
    return group_name


def convert_row(row, cc_group_by_admin):
    notes = str(row.get("lastFollowDesc") or "")
    tags = "、".join(str(tag.get("tag_name") or "") for tag in row.get("tagList") or [] if tag.get("tag_name"))
    source = str(row.get("sourceName") or "")
    course = " ".join(str(row.get(key) or "") for key in ["chapterNumberName", "chapterNumber"]).strip()
    context = " ".join([notes, source, course, tags])
    group_name = cc_group_by_admin.get(str(row.get("followCC") or ""), "未分组")
    lesson_time = " ".join(part for part in [str(row.get("courseDate") or ""), str(row.get("coursePeriod") or "")] if part)
    parent_notes = "；".join(part for part in [notes, f"来源：{source}" if source else "", f"标签：{tags}" if tags else "", f"课件：{course}" if course else ""] if part)
    return {
        "group_name": normalize_group_name(group_name),
        "user_id": str(row.get("unificationId") or "").strip(),
        "student_id": str(row.get("studentId") or "").strip(),
        "student_name": str(row.get("name") or row.get("nickName") or row.get("unificationId") or "").strip(),
        "cc_name": str(row.get("followCCName") or "").strip(),
        "lesson_time": lesson_time,
        "student_age": infer_age(context),
        "grade": infer_grade(context),
        "parent_notes": parent_notes,
        "recording_status": "未拉取录音",
        "recording_time": "",
        "recording_duration": "",
        "recording_cc_name": "",
        "recording_id": "",
        "recording_url": "",
        "recording_analysis_source": "",
        "last_call_summary": notes,
        "last_call_transcript": "",
    }


def fetch_student_phone_records(token, student_uuid, page_count=100):
    body = {
        "uuid": str(student_uuid),
        "page_num": 1,
        "page_count": page_count,
        "call_uuid": "",
        "call_admin_ids": "",
        "start_time": "",
        "end_time": "",
        "type": "",
        "order_type": 1,
        "sort_order": 1,
        "brand_code": BRAND_CODES_WANDOU,
    }
    res = request_json("POST", f"{ECC_BASE}/cc-backend/adminPhone/getRecordListOfStudent", token=token, body=body)
    require_ok(res, "读取学生通话记录")
    return res.get("list") or []


def is_valid_record(record, row):
    if not record.get("record_url"):
        return False
    if int(record.get("is_connect") or 0) != 1:
        return False
    duration = duration_to_seconds(record.get("bridge_duration_int") or record.get("total_duration_int"))
    if duration <= MIN_VALID_CALL_SECONDS:
        return False
    follow_cc = str(row.get("followCC") or "")
    follow_cc_name = str(row.get("followCCName") or "").strip()
    call_admin_id = str(record.get("call_admin_id") or "")
    call_admin_name = str(record.get("call_admin_name") or "").strip()
    return bool((follow_cc and call_admin_id == follow_cc) or (follow_cc_name and call_admin_name == follow_cc_name))


def pick_valid_record(records, row):
    valid = [record for record in records if is_valid_record(record, row)]
    valid.sort(key=lambda record: str(record.get("call_time") or ""), reverse=True)
    return valid[0] if valid else None


def flatten_analysis_text(value):
    chunks = []
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        for item in value:
            chunks.append(flatten_analysis_text(item))
    elif isinstance(value, dict):
        for key in ("text", "content", "result", "summary", "sentence", "value"):
            if key in value:
                chunks.append(flatten_analysis_text(value.get(key)))
        if not chunks:
            for item in value.values():
                chunks.append(flatten_analysis_text(item))
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def query_existing_analysis(token, record_id):
    if not record_id:
        return "", ""
    exists = request_json(
        "POST",
        f"{ECC_BASE}/cc-backend/adminPhone/queryExistsAnalysisRecord",
        token=token,
        body={"clinkIds": [str(record_id)]},
    )
    if exists.get("code") != 0:
        return "", ""
    candidates = []
    for value in exists.values():
        if isinstance(value, list):
            candidates.extend(value)
        elif isinstance(value, dict):
            candidates.extend(item for item in value.values() if isinstance(item, dict))
    analysis_id = ""
    for item in candidates:
        if str(item.get("clinkId") or item.get("clink_id") or item.get("voiceId") or "") == str(record_id):
            analysis_id = str(item.get("id") or item.get("recordId") or item.get("analysisRecordId") or "")
            break
        if not analysis_id:
            analysis_id = str(item.get("id") or item.get("recordId") or item.get("analysisRecordId") or "")
    if not analysis_id:
        return "", ""
    detail = request_json(
        "GET",
        f"{ECC_BASE}/cc-backend/adminPhone/queryAnalysisText",
        token=token,
        params={"recordId": analysis_id},
    )
    if detail.get("code") != 0:
        return "", ""
    text = flatten_analysis_text(detail.get("textResultItemList") or detail.get("data") or detail)
    return text, f"CRM已有分析:{analysis_id}"


def enrich_row_with_recording(token, raw_row, converted_row):
    student_uuid = raw_row.get("unificationId") or raw_row.get("studentId")
    if not student_uuid:
        converted_row["recording_status"] = "暂无有效录音：缺少学生ID"
        return {"student": converted_row["student_name"], "status": converted_row["recording_status"], "records": []}

    records = fetch_student_phone_records(token, student_uuid)
    record = pick_valid_record(records, raw_row)
    if not record:
        converted_row["recording_status"] = "暂无有效录音：归属CC本人且通话超过3分钟的录音未找到"
        return {
            "student": converted_row["student_name"],
            "student_uuid": student_uuid,
            "status": converted_row["recording_status"],
            "total_records": len(records),
            "records": records,
        }

    record_id = str(record.get("id") or "")
    analysis_text, analysis_source = query_existing_analysis(token, record_id)
    summary_parts = [
        f"有效录音：{record.get('call_time') or ''}",
        f"拨打CC：{record.get('call_admin_name') or ''}",
        f"通话时长：{record.get('bridge_duration_int') or record.get('total_duration_int') or ''}",
    ]
    if converted_row.get("last_call_summary"):
        summary_parts.append(f"CRM备注：{converted_row['last_call_summary']}")

    converted_row.update({
        "recording_status": "已匹配有效录音",
        "recording_time": str(record.get("call_time") or ""),
        "recording_duration": str(record.get("bridge_duration_int") or record.get("total_duration_int") or ""),
        "recording_cc_name": str(record.get("call_admin_name") or ""),
        "recording_id": record_id,
        "recording_url": str(record.get("record_url") or ""),
        "recording_analysis_source": analysis_source or "待ASR转写",
        "last_call_summary": "；".join(part for part in summary_parts if part),
        "last_call_transcript": analysis_text,
    })
    return {
        "student": converted_row["student_name"],
        "student_uuid": student_uuid,
        "status": converted_row["recording_status"],
        "selected_record": record,
        "analysis_source": converted_row["recording_analysis_source"],
        "total_records": len(records),
    }


def build_cc_group_map(token, group_orgs):
    cc_group = {}
    res = request_json(
        "POST",
        f"{ECC_BASE}/cc-backend/oa/getDepartment",
        token=token,
        body={"route": "demoCourse/list", "method": "GET", "jobStatus": 1},
    )
    require_ok(res, "读取CC归属")
    target_org_ids = {name: item["orgId"] for name, item in group_orgs.items()}
    for item, path in flatten_org(res.get("data") or []):
        item_id = str(item.get("id") or "")
        for group_name in TARGET_GROUPS:
            if group_name in path:
                cc_group[item_id] = group_name
    return cc_group, target_org_ids


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch HK/MO CC02/CC03 wait-class students from CRM.")
    parser.add_argument("--date", default=(date.today() + timedelta(days=1)).isoformat(), help="Lesson date, YYYY-MM-DD.")
    parser.add_argument("--output", default="outputs/crm_tomorrow_lessons.csv")
    parser.add_argument("--raw-output", default="outputs/crm_wait_class_raw.json")
    parser.add_argument("--recording-output", default="outputs/crm_recording_candidates.json")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--include-recordings", action="store_true", help="Fetch and attach valid owned-CC recordings over 3 minutes.")
    return parser.parse_args()


def main():
    args = parse_args()
    username = os.environ.get("CRM_USERNAME")
    password = os.environ.get("CRM_PASSWORD")
    if not username or not password:
        raise SystemExit("请先设置 CRM_USERNAME 和 CRM_PASSWORD")

    token, uid = crm_login(username, password)
    enter_wandou_business(token, uid)
    group_orgs = get_target_orgs(token)
    cc_group_by_admin, target_org_ids = build_cc_group_map(token, group_orgs)
    org_ids = [target_org_ids[name] for name in TARGET_GROUPS]
    rows, total = fetch_wait_class_page(token, args.date, org_ids, page_size=args.page_size)

    converted = [convert_row(row, cc_group_by_admin) for row in rows]
    recording_results = []
    if args.include_recordings:
        for raw_row, converted_row in zip(rows, converted):
            recording_results.append(enrich_row_with_recording(token, raw_row, converted_row))

    output_path = os.path.abspath(args.output)
    raw_path = os.path.abspath(args.raw_output)
    recording_path = os.path.abspath(args.recording_output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    os.makedirs(os.path.dirname(recording_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(converted)

    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({"date": args.date, "groups": group_orgs, "total": total, "rows": rows}, f, ensure_ascii=False, indent=2)

    if args.include_recordings:
        with open(recording_path, "w", encoding="utf-8") as f:
            json.dump({"date": args.date, "min_valid_call_seconds": MIN_VALID_CALL_SECONDS, "results": recording_results}, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "date": args.date,
        "groups": group_orgs,
        "total": total,
        "csv": output_path,
        "raw": raw_path,
        "recordings": recording_path if args.include_recordings else None,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
