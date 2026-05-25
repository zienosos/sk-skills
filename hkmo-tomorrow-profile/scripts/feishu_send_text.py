#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


FEISHU_BASE = "https://open.feishu.cn/open-apis"


def request_json(method, url, token=None, body=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def require_ok(res, label):
    if res.get("code") != 0:
        raise RuntimeError(f"{label}失败: {json.dumps(res, ensure_ascii=False)}")
    return res


def tenant_access_token(app_id, app_secret):
    res = request_json(
        "POST",
        f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
        body={"app_id": app_id, "app_secret": app_secret},
    )
    require_ok(res, "获取tenant_access_token")
    return res["tenant_access_token"]


def send_text(token, receive_id_type, receive_id, text):
    params = urllib.parse.urlencode({"receive_id_type": receive_id_type})
    res = request_json(
        "POST",
        f"{FEISHU_BASE}/im/v1/messages?{params}",
        token=token,
        body={
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        },
    )
    require_ok(res, "发送飞书文本")
    return res


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receive-id", default=os.environ.get("FEISHU_OPEN_ID", ""))
    parser.add_argument("--receive-id-type", default="open_id")
    parser.add_argument("--text", required=True)
    args = parser.parse_args()
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        raise SystemExit("请先设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
    if not args.receive_id:
        raise SystemExit("请设置 FEISHU_OPEN_ID 或传入 --receive-id")
    token = tenant_access_token(app_id, app_secret)
    res = send_text(token, args.receive_id_type, args.receive_id, args.text)
    print(json.dumps({"sent": True, "message_id": (res.get("data") or {}).get("message_id")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
