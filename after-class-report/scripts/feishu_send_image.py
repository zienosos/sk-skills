#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError


OPEN_API = "https://open.feishu.cn/open-apis"
REDIRECT_URI = "http://127.0.0.1:8765/callback"


class CallbackHandler(BaseHTTPRequestHandler):
    code = None
    state = None
    error = None
    event = threading.Event()

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        CallbackHandler.code = params.get("code", [None])[0]
        CallbackHandler.state = params.get("state", [None])[0]
        CallbackHandler.error = params.get("error", [None])[0]
        CallbackHandler.event.set()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("授权完成，可以回到 Codex。".encode("utf-8"))


def request_json(method: str, url: str, token: str | None = None, body: object | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    data = request_json(
        "POST",
        f"{OPEN_API}/auth/v3/tenant_access_token/internal",
        body={"app_id": app_id, "app_secret": app_secret},
    )
    if data.get("code") != 0:
        raise RuntimeError(f"failed to get tenant_access_token: {data}")
    return data["tenant_access_token"]


def oauth_user(app_id: str, app_secret: str, no_open: bool = False) -> dict:
    state = secrets.token_urlsafe(16)
    params = {
        "client_id": app_id,
        "redirect_uri": REDIRECT_URI,
        "scope": "contact:user.id:readonly",
        "state": state,
    }
    url = f"https://accounts.feishu.cn/open-apis/authen/v1/authorize?{urlencode(params)}"

    server = HTTPServer(("127.0.0.1", 8765), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print("Open this URL to authorize:")
    print(url)
    if not no_open:
        webbrowser.open(url)

    CallbackHandler.event.wait(timeout=300)
    server.shutdown()
    if CallbackHandler.error:
        raise RuntimeError(f"OAuth error: {CallbackHandler.error}")
    if not CallbackHandler.code:
        raise RuntimeError("Timed out waiting for OAuth callback")
    if CallbackHandler.state != state:
        raise RuntimeError("State mismatch")

    token_data = request_json(
        "POST",
        f"{OPEN_API}/authen/v2/oauth/token",
        body={
            "grant_type": "authorization_code",
            "client_id": app_id,
            "client_secret": app_secret,
            "code": CallbackHandler.code,
            "redirect_uri": REDIRECT_URI,
        },
    )
    if token_data.get("code") != 0:
        raise RuntimeError(f"failed OAuth token exchange: {token_data}")

    user_token = token_data["access_token"]
    user_info = request_json("GET", f"{OPEN_API}/authen/v1/user_info", token=user_token)
    if user_info.get("code") != 0:
        raise RuntimeError(f"failed user_info: {user_info}")
    return user_info["data"]


def upload_image(token: str, image_path: Path) -> str:
    boundary = "----codexfeishuimage"
    raw = image_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="image_type"\r\n\r\n'
        "message\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + raw + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = Request(
        f"{OPEN_API}/im/v1/images",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("code") != 0:
        raise RuntimeError(f"failed upload image: {data}")
    return data["data"]["image_key"]


def send_image(token: str, open_id: str, image_key: str) -> dict:
    return request_json(
        "POST",
        f"{OPEN_API}/im/v1/messages?receive_id_type=open_id",
        token=token,
        body={
            "receive_id": open_id,
            "msg_type": "image",
            "content": json.dumps({"image_key": image_key}, ensure_ascii=False),
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--open-id", default=os.environ.get("FEISHU_OPEN_ID"))
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        print("Missing FEISHU_APP_ID / FEISHU_APP_SECRET", file=sys.stderr)
        return 2

    open_id = args.open_id
    if not open_id:
        user = oauth_user(app_id, app_secret, no_open=args.no_open)
        open_id = user.get("open_id")
        if not open_id:
            raise RuntimeError(f"open_id not found in user_info: {user}")
        print(f"Resolved open_id: {open_id}")

    tenant_token = get_tenant_access_token(app_id, app_secret)
    image_key = upload_image(tenant_token, Path(args.image))
    data = send_image(tenant_token, open_id, image_key)
    if data.get("code") != 0:
        raise RuntimeError(f"failed send message: {data}")
    print("Sent image to Feishu private chat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
