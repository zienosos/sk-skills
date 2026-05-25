#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from urllib.error import HTTPError


OPEN_API = "https://open.feishu.cn/open-apis"


def request_json(method, url, token=None, body=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc


def require_ok(res, label):
    if res.get("code") != 0:
        raise RuntimeError(f"{label}失败: {json.dumps(res, ensure_ascii=False)}")
    return res


def tenant_access_token(app_id, app_secret):
    res = request_json(
        "POST",
        f"{OPEN_API}/auth/v3/tenant_access_token/internal",
        body={"app_id": app_id, "app_secret": app_secret},
    )
    require_ok(res, "获取tenant_access_token")
    return res["tenant_access_token"]


def resolve_token():
    token = os.environ.get("FEISHU_USER_ACCESS_TOKEN")
    if token:
        return token
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    if app_id and app_secret:
        return tenant_access_token(app_id, app_secret)
    raise RuntimeError("请先设置 FEISHU_USER_ACCESS_TOKEN 或 FEISHU_APP_ID/FEISHU_APP_SECRET")


def add_member(token, file_token, member_id, member_type, perm, file_type):
    params = urllib.parse.urlencode({"type": file_type})
    body = {
        "member_id": member_id,
        "member_type": member_type,
        "perm": perm,
    }
    return request_json(
        "POST",
        f"{OPEN_API}/drive/v1/permissions/{file_token}/members?{params}",
        token=token,
        body=body,
    )


def main():
    parser = argparse.ArgumentParser(description="Add Feishu doc collaborator permission.")
    parser.add_argument("file_token")
    parser.add_argument("--member-id", default=os.environ.get("FEISHU_OPEN_ID", ""))
    parser.add_argument("--member-type", default="openid")
    parser.add_argument("--perm", default="view")
    parser.add_argument("--type", default="docx", dest="file_type")
    args = parser.parse_args()
    if not args.member_id:
        raise SystemExit("请设置 FEISHU_OPEN_ID 或传入 --member-id")
    token = resolve_token()
    res = add_member(token, args.file_token, args.member_id, args.member_type, args.perm, args.file_type)
    require_ok(res, "添加协作者")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
