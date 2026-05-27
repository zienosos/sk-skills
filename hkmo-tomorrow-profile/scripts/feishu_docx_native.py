#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
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


def require_ok(data, label):
    if data.get("code") != 0:
        raise RuntimeError(f"{label}失败: {json.dumps(data, ensure_ascii=False)[:2000]}")
    return data


def tenant_access_token(app_id, app_secret):
    data = request_json(
        "POST",
        f"{OPEN_API}/auth/v3/tenant_access_token/internal",
        body={"app_id": app_id, "app_secret": app_secret},
    )
    require_ok(data, "获取tenant_access_token")
    return data["tenant_access_token"]


def resolve_token():
    token = os.environ.get("FEISHU_USER_ACCESS_TOKEN")
    if token:
        return token
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    if app_id and app_secret:
        return tenant_access_token(app_id, app_secret)
    raise RuntimeError("Missing FEISHU_USER_ACCESS_TOKEN or FEISHU_APP_ID/FEISHU_APP_SECRET")


def create_document(token, title):
    data = request_json("POST", f"{OPEN_API}/docx/v1/documents", token=token, body={"title": title})
    require_ok(data, "创建飞书文档")
    doc = data.get("data", {}).get("document", {})
    document_id = doc.get("document_id") or data.get("data", {}).get("document_id")
    if not document_id:
        raise RuntimeError(f"document_id not found: {data}")
    return document_id


def text_element(content, bold=False, text_color=None, background_color=None):
    style = {
        "bold": bold,
        "italic": False,
        "strikethrough": False,
        "underline": False,
        "inline_code": False,
    }
    if text_color is not None:
        style["text_color"] = text_color
    if background_color is not None:
        style["background_color"] = background_color
    return {
        "text_run": {
            "content": str(content),
            "text_element_style": style,
        }
    }


def block(block_type, field, content, bold=False, text_color=None, background_color=None):
    return {
        "block_type": block_type,
        field: {
            "elements": [text_element(content, bold=bold, text_color=text_color, background_color=background_color)],
            "style": {"align": 1, "folded": False},
        },
    }


def h1(text):
    return block(3, "heading1", text, bold=True)


def h2(text):
    return block(4, "heading2", text, bold=True)


def h3(text):
    return block(5, "heading3", text, bold=True)


def paragraph(text, bold=False, text_color=None, background_color=None):
    return block(2, "text", text, bold=bold, text_color=text_color, background_color=background_color)


def rich_paragraph(elements):
    return {
        "block_type": 2,
        "text": {
            "elements": elements,
            "style": {"align": 1, "folded": False},
        },
    }


def bullet(text):
    return block(12, "bullet", text)


def color_bullet(text, text_color=None, background_color=None, bold=False):
    return block(12, "bullet", text, bold=bold, text_color=text_color, background_color=background_color)


def divider():
    return {"block_type": 22, "divider": {}}


def callout(background_color, emoji_id, children_count):
    value = {
        "block_type": 19,
        "callout": {
            "background_color": background_color,
        },
        "children": [],
        "_children_count": children_count,
    }
    if emoji_id:
        value["callout"]["emoji_id"] = emoji_id
    return value


def compact_text(text, limit=80):
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip("，,；;。 ") + "..."


def load_rules(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_rows(path, group):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if group:
        rows = [row for row in rows if row.get("group_name") == group]
    return rows


def normalize_text(row):
    return " ".join(str(row.get(key, "") or "") for key in row.keys()).lower()


def score_items(items, text):
    scored = []
    for item in items:
        keywords = item.get("signals") or item.get("keywords") or []
        score = sum(max(1, len(keyword)) for keyword in keywords if keyword.lower() in text)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


def has_dad_decision_context(text):
    decision_phrases = [
        "同爸爸商量",
        "跟爸爸商量",
        "和爸爸商量",
        "跟爸爸讨论",
        "同爸爸討論",
        "問爸爸",
        "问爸爸",
        "爸爸决定",
        "爸爸決定",
        "爸爸不同意",
        "爸爸唔同意",
        "爸爸考虑",
        "爸爸考慮",
        "爸爸有顾虑",
        "爸爸有顧慮",
        "爸爸觉得",
        "爸爸覺得",
        "老公不同意",
        "老公唔同意",
        "先生不同意",
        "先生唔同意",
        "另一半商量",
        "家人商量",
        "一家人商量",
    ]
    receiver_only = [
        "爸爸接听",
        "爸爸接聽",
        "爸爸接的电话",
        "爸爸接的電話",
        "爸爸听电话",
        "爸爸聽電話",
        "爸爸接电话",
        "爸爸接電話",
        "妈妈接听",
        "媽媽接聽",
        "妈妈接的电话",
        "媽媽接的電話",
        "妈妈听电话",
        "媽媽聽電話",
        "妈妈接电话",
        "媽媽接電話",
    ]
    if any(phrase in text for phrase in decision_phrases):
        return True
    return False if any(phrase in text for phrase in receiver_only) else False


def filter_contextual_matches(items, text):
    filtered = []
    for item in items:
        if item.get("id") == "dad_decision" and not has_dad_decision_context(text):
            continue
        if item.get("name") == "要同爸爸商量" and not has_dad_decision_context(text):
            continue
        filtered.append(item)
    return filtered


def infer_intent(text):
    if not text.strip():
        return "信息不足"
    high = ["想报名", "付款", "怎么买", "课包", "优惠", "转数快", "fps"]
    medium_high = ["试", "有效", "适合", "喜欢", "小一", "呈分", "面试"]
    low = ["不需要", "没兴趣", "太贵", "迟点", "不考虑"]
    if any(word in text for word in high):
        return "高"
    if any(word in text for word in low):
        return "低"
    if any(word in text for word in medium_high):
        return "中高"
    return "中"


def follow_stage(intent, objection):
    if intent == "信息不足":
        return "信息不足", "课前补问关键问题"
    if objection in {"价格贵", "孩子不喜欢/坚持不了", "想比较机构"} and intent in {"低", "中"}:
        return "风险补救", "先处理阻力"
    if objection == "要同爸爸商量":
        return "协助决策", "给妈妈准备说服爸爸的证据"
    if intent in {"高", "中高"}:
        return "可推进", "课后顺势推进试学期/课包"
    return "需培育", "补信任、补效果证据"


def infer_needs(text):
    mapping = {
        "呈分试准备": ["呈分", "band", "升中"],
        "小一衔接": ["小一", "升小", "幼小"],
        "面试逻辑表达": ["面试", "表達", "表达"],
        "数学思维": ["思维", "邏輯", "逻辑", "解难"],
        "专注力": ["专注", "坐不住", "坐唔定"],
        "表达能力": ["表达", "表達", "开口"],
        "解难能力": ["解难", "拆题", "陌生题"],
        "学习兴趣": ["喜欢", "鍾意", "兴趣", "開心", "开心"],
    }
    needs = [need for need, words in mapping.items() if any(word.lower() in text for word in words)]
    return needs or ["数学思维", "学习兴趣"]


def is_priority(item):
    return item["stage"] in {"风险补救", "协助决策"} or item["objection"] in {
        "价格贵",
        "要同爸爸商量",
        "孩子不喜欢/坚持不了",
        "想比较机构",
    }


def first_sentence(objection, primary_need):
    if objection == "价格贵":
        return "媽咪，我哋先唔急住睇價錢，我想先同你講返小朋友今日上堂一個幾明顯嘅表現。"
    if objection == "要同爸爸商量":
        return "媽咪，我整理咗小朋友今日表現三點，你等陣同爸爸傾嘅時候可以直接俾佢睇。"
    if objection == "孩子不喜欢/坚持不了":
        return "媽咪，今日我哋重點唔係睇佢識唔識晒，而係睇佢願唔願意跟老師試同參與。"
    if objection == "想比较机构":
        return "媽咪，比較係應該嘅，我建議你今日可以用幾個標準去睇：測評、跟進服務同解難能力。"
    if primary_need in {"小一衔接", "面试逻辑表达"}:
        return "媽咪，今日可以重點睇小朋友聽指令、表達同跟老師思路嘅情況。"
    return "媽咪，今日我想同你重點睇一樣嘢：小朋友遇到新題目識唔識一步步諗。"


def actions(stage, objection):
    if objection == "价格贵":
        return ["先讲课堂具体表现", "再讲测评体系和4人服务群", "最后用4堂鉴赏期降低风险"]
    if objection == "要同爸爸商量":
        return ["整理孩子表现证据", "给妈妈可转述的三点", "锁定爸爸反馈时间"]
    if objection == "孩子不喜欢/坚持不了":
        return ["先确认孩子参与瞬间", "解释前期磨合正常", "用鉴赏期降低家长压力"]
    if objection == "想比较机构":
        return ["承认可以比较", "把比较维度拉到服务/测评/体系", "避免直接讲竞品坏话"]
    if stage == "信息不足":
        return ["补问家长关注点", "确认陪听安排", "课后再判断方案"]
    return ["先反馈课堂亮点", "连接长期能力价值", "再给试学期/课包方案"]


def analyze_rows(rows, rules):
    items = []
    for row in rows:
        text = normalize_text(row)
        parent_matches = filter_contextual_matches(score_items(rules["parent_types"], text), text)
        objection_matches = filter_contextual_matches(score_items(rules["common_objections"], text), text)
        parent = (parent_matches or rules["parent_types"])[0]
        objection_item = (objection_matches or [None])[0]
        objection = objection_item["name"] if objection_item else "需课后进一步确认"
        stage, goal = follow_stage(infer_intent(text), objection)
        needs = infer_needs(text)
        items.append({
            "row": row,
            "group": row.get("group_name") or "未分组",
            "cc": row.get("cc_name") or "未分配CC",
            "user_id": row.get("user_id") or "-",
            "student_id": row.get("student_id") or "-",
            "student": row.get("student_name") or "未命名学员",
            "lesson_time": row.get("lesson_time") or "待确认",
            "grade": row.get("grade") or "未填写",
            "parent_type": parent["name"],
            "script": objection_item["response"] if objection_item else parent["talking_point"],
            "objection": objection,
            "stage": stage,
            "goal": goal,
            "needs": needs,
            "has_recording": row.get("recording_status") == "已匹配有效录音",
            "recording": recording_line(row),
            "notes": compact_text(row.get("last_call_summary") or row.get("parent_notes"), 90) or "暂无备注",
        })
    return items


def recording_line(row):
    status = row.get("recording_status") or "未拉取录音"
    if status.startswith("暂无有效录音"):
        return "无"
    time_value = row.get("recording_time") or ""
    duration = row.get("recording_duration") or ""
    source = row.get("recording_analysis_source") or ""
    if time_value or duration:
        status = f"{status}｜{time_value}｜{duration}"
    if source:
        status = f"{status}｜{source}"
    return status.replace("已匹配有效录音｜", "有效｜").replace("DashScope ASR", "ASR已分析")


def build_blocks(items, title):
    blocks = [
        h1(title),
        paragraph("主管先看总览和重点ID；CC 搜自己名字，看名下学员卡片。"),
    ]
    priority_items = [item for item in items if is_priority(item)]
    cc_counts = Counter(item["cc"] for item in items)
    priority_by_cc = Counter(item["cc"] for item in priority_items)
    recording_by_cc = Counter(item["cc"] for item in items if item["has_recording"])
    type_counts = Counter(item["parent_type"] for item in items)
    objection_counts = Counter(item["objection"] for item in items)

    blocks.append(h2("一、主管总览"))
    blocks.append(callout(5, "bar_chart", 1))
    blocks.append(paragraph(f"今日概况｜待上课 {len(items)}人｜重点 {len(priority_items)}人｜有效录音 {sum(1 for item in items if item['has_recording'])}人", bold=True))

    blocks.append(h3("课量看板"))
    for name, count in cc_counts.most_common():
        p_count = priority_by_cc.get(name, 0)
        r_count = recording_by_cc.get(name, 0)
        color = 1 if p_count else 7
        blocks.append(callout(color, "round_pushpin" if p_count else "memo", 1))
        blocks.append(paragraph(f"{name}｜课量 {count}人｜重点 {p_count}人｜有效录音 {r_count}人", bold=bool(p_count)))

    blocks.append(h3("重点关注 CC"))
    if priority_by_cc:
        for name, count in priority_by_cc.most_common():
            blocks.append(bullet(f"{name}：{count}个重点学员"))
    else:
        blocks.append(bullet("暂无"))

    blocks.append(h3("家长画像分布"))
    for name, count in type_counts.most_common(5):
        blocks.append(bullet(f"{name}：{count}人"))

    blocks.append(h3("今天先盯的具体ID"))
    if priority_items:
        for item in sorted(priority_items, key=lambda value: (value["cc"], value["lesson_time"]))[:12]:
            blocks.append(bullet(f"{item['cc']}｜{item['student']}｜用户ID {item['user_id']}｜{item['lesson_time']}｜{item['objection']}"))
    else:
        blocks.append(bullet("暂无"))

    blocks.append(h2("二、CC 课量与重点"))
    grouped = defaultdict(list)
    for item in items:
        grouped[item["cc"]].append(item)
    for cc, cc_items in sorted(grouped.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        p_count = sum(1 for item in cc_items if is_priority(item))
        r_count = sum(1 for item in cc_items if item["has_recording"])
        blocks.append(callout(1 if p_count else 7, "round_pushpin" if p_count else "memo", len(cc_items) + 1))
        blocks.append(paragraph(f"{cc}｜共 {len(cc_items)} 人｜重点 {p_count} 人｜有效录音 {r_count} 人", bold=True))
        for item in sorted(cc_items, key=lambda value: value["lesson_time"]):
            mark = "重点" if is_priority(item) else "常规"
            blocks.append(bullet(f"{mark}｜{item['lesson_time']}｜{item['student']}｜用户ID {item['user_id']}｜学员ID {item['student_id']}｜{item['objection']}"))

    blocks.append(h2("三、CC 学员卡片"))
    for cc, cc_items in sorted(grouped.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        p_count = sum(1 for item in cc_items if is_priority(item))
        blocks.append(h2(f"{cc}｜共{len(cc_items)}人｜重点{p_count}人"))
        sorted_items = sorted(cc_items, key=lambda value: (not is_priority(value), value["lesson_time"]))
        for item in sorted_items:
            primary_need = item["needs"][0]
            priority = is_priority(item)
            priority_label = "重点" if priority else "常规"
            blocks.append(callout(1 if priority else 7, "", 7))
            blocks.append(paragraph(f"{priority_label}｜{item['student']}｜{item['lesson_time']}", bold=True))
            blocks.append(rich_paragraph([
                text_element("用户ID ", bold=True),
                text_element(item["user_id"], bold=True),
                text_element(f"｜学员ID {item['student_id']}｜阶段 {item['grade']}", bold=True),
            ]))
            blocks.append(paragraph(f"风险：{item['objection']}｜关注：{' / '.join(item['needs'][:3])}｜录音：{item['recording']}", bold=True))
            blocks.append(paragraph("动作：" + "；".join(actions(item["stage"], item["objection"]))))
            blocks.append(paragraph(f"第一句话：{first_sentence(item['objection'], primary_need)}"))
            blocks.append(paragraph(f"话术：{item['script']}"))
            blocks.append(paragraph(f"备注：{item['notes']}"))
            blocks.append(paragraph(""))
    return blocks


def expand_blocks(blocks):
    expanded = []
    top_ids = []
    counter = 0
    index = 0
    while index < len(blocks):
        item = blocks[index]
        block_id = f"native_{counter}"
        counter += 1
        copied = json.loads(json.dumps(item, ensure_ascii=False))
        children_count = copied.pop("_children_count", 0)
        copied["block_id"] = block_id
        if children_count:
            child_ids = []
            children = blocks[index + 1:index + 1 + children_count]
            for child in children:
                child_id = f"native_{counter}"
                counter += 1
                child_copy = json.loads(json.dumps(child, ensure_ascii=False))
                child_copy["block_id"] = child_id
                child_copy["parent_id"] = block_id
                expanded.append(child_copy)
                child_ids.append(child_id)
            copied["children"] = child_ids
            index += children_count
        expanded.append(copied)
        top_ids.append(block_id)
        index += 1
    return top_ids, expanded


def chunk_top_level(top_ids, descendants, chunk_size=450):
    block_by_id = {block["block_id"]: block for block in descendants}
    chunks = []
    current_top = []
    current_desc = []
    current_count = 0
    for top_id in top_ids:
        block = block_by_id[top_id]
        related = [block]
        related.extend(block_by_id[child_id] for child_id in block.get("children", []))
        if current_top and current_count + len(related) > chunk_size:
            chunks.append((current_top, current_desc))
            current_top = []
            current_desc = []
            current_count = 0
        current_top.append(top_id)
        current_desc.extend(related)
        current_count += len(related)
    if current_top:
        chunks.append((current_top, current_desc))
    return chunks


def insert_blocks(token, document_id, blocks, chunk_size=450):
    top_ids, descendants = expand_blocks(blocks)
    index = 0
    for children_id, chunk_descendants in chunk_top_level(top_ids, descendants, chunk_size=chunk_size):
        body = {"index": index, "children_id": children_id, "descendants": chunk_descendants}
        data = request_json(
            "POST",
            f"{OPEN_API}/docx/v1/documents/{document_id}/blocks/{document_id}/descendant?document_revision_id=-1",
            token=token,
            body=body,
        )
        require_ok(data, "插入飞书原生block")
        index += len(children_id)
        time.sleep(0.2)


def add_member(token, document_id, open_id):
    if not open_id:
        return
    params = urllib.parse.urlencode({"type": "docx"})
    body = {"member_id": open_id, "member_type": "openid", "perm": "view"}
    data = request_json("POST", f"{OPEN_API}/drive/v1/permissions/{document_id}/members?{params}", token=token, body=body)
    require_ok(data, "添加文档协作者")


def set_anyone_readable(token, document_id):
    body = {
        "external_access_entity": "open",
        "security_entity": "anyone_can_view",
        "comment_entity": "anyone_can_view",
        "share_entity": "anyone",
        "link_share_entity": "anyone_readable",
        "copy_entity": "anyone_can_view",
    }
    data = request_json(
        "PATCH",
        f"{OPEN_API}/drive/v2/permissions/{document_id}/public?type=docx",
        token=token,
        body=body,
    )
    require_ok(data, "设置链接公开可读")


def send_text(token, open_id, text):
    if not open_id:
        return
    params = urllib.parse.urlencode({"receive_id_type": "open_id"})
    body = {"receive_id": open_id, "msg_type": "text", "content": json.dumps({"text": text}, ensure_ascii=False)}
    data = request_json("POST", f"{OPEN_API}/im/v1/messages?{params}", token=token, body=body)
    require_ok(data, "发送飞书文本")


def parse_args():
    parser = argparse.ArgumentParser(description="Create Feishu docx directly from CSV using native blocks.")
    parser.add_argument("--input", default="outputs/crm_tomorrow_lessons.csv")
    parser.add_argument("--rules", default="config/hkmo_profile_rules.json")
    parser.add_argument("--group", required=True)
    parser.add_argument("--title-date", required=True)
    parser.add_argument("--send-open-id", default=os.environ.get("FEISHU_OPEN_ID", ""))
    parser.add_argument("--no-public", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    token = resolve_token()
    rules = load_rules(args.rules)
    rows = load_rows(args.input, args.group)
    items = analyze_rows(rows, rules)
    title = f"港澳明日上课学员画像｜{args.title_date}"
    document_id = create_document(token, title)
    blocks = build_blocks(items, title)
    insert_blocks(token, document_id, blocks)
    if not args.no_public:
        set_anyone_readable(token, document_id)
    add_member(token, document_id, args.send_open_id)
    url = f"https://my.feishu.cn/docx/{document_id}"
    send_text(token, args.send_open_id, f"{title}\n{url}")
    print(json.dumps({"document_id": document_id, "url": url, "blocks": len(blocks)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
