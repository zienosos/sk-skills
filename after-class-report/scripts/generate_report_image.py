from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ASSET_DIR = SKILL_DIR / "assets"
REFERENCE_DIR = SKILL_DIR / "references"
EXAMPLE_DIR = SKILL_DIR / "examples"
FONT_REGULAR = str(ASSET_DIR / "NotoSansCJKtc-Regular.otf")
FONT_BOLD = str(ASSET_DIR / "NotoSansCJKtc-Bold.otf")


COLORS = {
    "bg": "#eef3f8",
    "paper": "#ffffff",
    "ink": "#24364b",
    "muted": "#667085",
    "line": "#e4e7ec",
    "orange": "#d99200",
    "orange_soft": "#fff8dd",
    "green": "#12a06a",
    "green_soft": "#eaf8f1",
    "blue": "#246bfe",
    "blue_soft": "#edf5ff",
    "gold": "#f79009",
    "gold_soft": "#fff7e6",
    "navy": "#193b68",
    "navy_soft": "#f3f7fb",
    "red": "#d92d20",
}

PRIMARY = "#13b678"
PRIMARY_DARK = "#07945e"
PRIMARY_SOFT = "#eefbf4"
PEA_YELLOW = "#ffd21f"


def load_course_knowledge(course_name: str | None) -> dict[str, Any] | None:
    if not course_name:
        return None
    path = REFERENCE_DIR / "demo_course_knowledge.json"
    if not path.exists():
        return None
    knowledge = json.loads(path.read_text(encoding="utf-8"))
    normalized = course_name.replace(" ", "")
    for course in knowledge.get("courses", []):
        title = course["course"].replace(" ", "")
        if title in normalized or normalized in title:
            return course
    return None


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)


def text_w(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(text, font=fnt)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in text:
        if ch == "\n":
            lines.append(current)
            current = ""
            continue
        trial = current + ch
        if text_w(draw, trial, fnt) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, radius: int = 12, outline: str | None = None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    color: str,
    max_width: int,
    line_gap: int = 8,
) -> int:
    x, y = xy
    line_h = fnt.size + line_gap
    for line in wrap_text(draw, text, fnt, max_width):
        draw.text((x, y), line, font=fnt, fill=color)
        y += line_h
    return y


def split_lead(text: str) -> tuple[str, str]:
    for sep in ("，", "：", "。"):
        idx = text.find(sep)
        if 3 <= idx <= 22:
            return text[: idx + 1], text[idx + 1 :]
    return "", text


def draw_emphasis_line(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    regular: ImageFont.FreeTypeFont,
    bold: ImageFont.FreeTypeFont,
    color: str,
    accent: str,
    max_width: int,
    line_gap: int = 8,
) -> int:
    lead, rest = split_lead(text)
    if not lead:
        return draw_wrapped(draw, xy, text, regular, color, max_width, line_gap)

    x, y = xy
    lead_w = text_w(draw, lead, bold)
    if lead_w < max_width:
        draw.text((x, y), lead, font=bold, fill="#1f2937")
        first_width = max_width - int(lead_w)
        rest_lines = wrap_text(draw, rest, regular, first_width)
        if rest_lines:
            draw.text((x + lead_w, y), rest_lines[0], font=regular, fill=color)
            y += regular.size + line_gap
            for line in rest_lines[1:]:
                draw.text((x, y), line, font=regular, fill=color)
                y += regular.size + line_gap
        else:
            y += regular.size + line_gap
        return y

    return draw_wrapped(draw, xy, text, regular, color, max_width, line_gap)


def draw_tag(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, color: str, bg: str) -> int:
    fnt = font(18, True)
    pad_x, pad_y = 10, 4
    w = int(text_w(draw, text, fnt)) + pad_x * 2
    h = fnt.size + pad_y * 2
    rounded(draw, (x, y, x + w, y + h), bg, radius=7)
    draw.text((x + pad_x, y + pad_y - 1), text, font=fnt, fill=color)
    return x + w + 8


def draw_metric(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, value: str, color: str, symbol: str) -> None:
    x1, y1, x2, y2 = box
    fill = "#f8fffb" if color == COLORS["green"] else PRIMARY_SOFT if color == COLORS["orange"] else "#f7fbff"
    outline = "#bfead9" if color == COLORS["green"] else "#ffe08a" if color == COLORS["orange"] else "#c8dcff"
    rounded(draw, box, fill, radius=16, outline=outline, width=2)
    tf = font(20, True)
    vf = font(24, True)
    sf = font(23, True)
    draw.text(((x1 + x2) / 2 - text_w(draw, title, tf) / 2, y1 + 22), title, font=tf, fill=COLORS["muted"])
    draw.text(((x1 + x2) / 2 - text_w(draw, symbol, sf) / 2, y1 + 57), symbol, font=sf, fill="#f6b900")
    draw.text(((x1 + x2) / 2 - text_w(draw, value, vf) / 2, y1 + 92), value, font=vf, fill=color)


def section(
    draw: ImageDraw.ImageDraw,
    y: int,
    title: str,
    symbol: str,
    accent: str,
    points: list[str],
    tags: list[str],
    notes: list[str],
    width: int,
) -> int:
    x = 38
    inner_w = width - x * 2
    rounded(draw, (x, y, width - x, y + 58), "#f8fafc", radius=12)
    draw.rounded_rectangle((x, y, x + 9, y + 58), radius=4, fill=accent)
    draw.text((x + 24, y + 15), symbol, font=font(20, True), fill=accent)
    draw.text((x + 64, y + 14), title, font=font(25, True), fill="#1d2939")
    y += 76

    body_font = font(20)
    for i, point in enumerate(points, 1):
        prefix = f"{i}. "
        draw.text((x + 16, y), prefix, font=font(20, True), fill=accent)
        y = draw_emphasis_line(draw, (x + 46, y), point, body_font, font(20, True), COLORS["ink"], accent, inner_w - 52, line_gap=9)
        y += 8

    if tags:
        tx = x + 16
        for tag in tags:
            tx = draw_tag(draw, tx, y, tag, accent, COLORS["green_soft"] if accent == COLORS["green"] else COLORS["orange_soft"] if accent == COLORS["orange"] else COLORS["blue_soft"])
        y += 42

    note_fill = COLORS["green_soft"] if accent == COLORS["green"] else COLORS["orange_soft"] if accent == COLORS["orange"] else COLORS["blue_soft"]
    for note in notes:
        rounded(draw, (x + 16, y, width - 38, y + 38), note_fill, radius=7)
        draw.text((x + 30, y + 7), "提示", font=font(18, True), fill=accent)
        draw.text((x + 82, y + 7), note, font=font(18), fill=COLORS["ink"])
        y += 46

    return y + 28


def course_box(draw: ImageDraw.ImageDraw, y: int, course: dict[str, Any], width: int) -> int:
    x = 38
    draw.rounded_rectangle((x, y, x + 8, y + 42), radius=4, fill=PRIMARY)
    draw.text((x + 24, y - 1), "本次 Demo 課程", font=font(30, True), fill="#1d2939")
    y += 70
    rounded(draw, (x, y, width - x, y + 184), "#fbfffc", radius=18, outline="#bfead9", width=2)
    draw.text((x + 28, y + 26), f"{course['level']} {course['course']}", font=font(30, True), fill=PRIMARY_DARK)
    core = "、".join(course.get("math_points", [])[:4])
    ability = "、".join(course.get("abilities", [])[:4])
    draw.text((x + 30, y + 76), "核心知識：", font=font(22, True), fill=COLORS["muted"])
    draw_wrapped(draw, (x + 148, y + 76), core, font(22, True), "#4f5662", width - x * 2 - 176, line_gap=6)
    draw.text((x + 30, y + 118), "能力培養：", font=font(22, True), fill=COLORS["muted"])
    draw_wrapped(draw, (x + 148, y + 118), ability, font(22, True), "#4f5662", width - x * 2 - 176, line_gap=6)
    ty = y + 144
    labels = course.get("math_points", [])[:5]
    tx = x + 24
    if False:
        for label in labels:
            tx = draw_tag(draw, tx, ty, label, COLORS["blue"], COLORS["blue_soft"])
    return y + 224


def summary_box(draw: ImageDraw.ImageDraw, y: int, data: dict[str, Any], width: int) -> int:
    x = 38
    recommended_level = data.get("recommended_level") or "S6"
    text = data.get(
        "summary",
        f"詩行基礎理解和專注力較穩，建議銜接 {recommended_level}，重點提升應用題分析、分步列式和單位檢查。",
    )
    rounded(draw, (x, y, width - x, y + 118), PRIMARY_SOFT, radius=18, outline="#bfead9", width=2)
    draw.text((x + 26, y + 22), "一句話結論", font=font(24, True), fill=PRIMARY_DARK)
    rounded(draw, (width - x - 164, y + 18, width - x - 24, y + 60), PRIMARY, radius=21)
    badge = f"推薦 {recommended_level}"
    draw.text((width - x - 94 - text_w(draw, badge, font(23, True)) / 2, y + 26), badge, font=font(23, True), fill="#ffffff")
    draw_wrapped(draw, (x + 26, y + 64), text, font(21, True), COLORS["ink"], width - x * 2 - 52, line_gap=8)
    return y + 146


def draw_header_sparkles(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    for dx, dy, r, color in [
        (0, 0, 6, "#c8f7df"),
        (38, 22, 4, "#ffffff"),
        (82, -8, 5, "#fff2a8"),
        (120, 34, 3, "#b8f0d1"),
    ]:
        draw.ellipse((x + dx - r, y + dy - r, x + dx + r, y + dy + r), fill=color)
    star = "✦"
    draw.text((x + 54, y - 4), star, font=font(22, True), fill=PEA_YELLOW)


def draw_brand(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    logo_path = ASSET_DIR / "vipthink_logo_primary.png"
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")
        diff = Image.new("RGBA", logo.size, (255, 255, 255, 255))
        alpha = Image.eval(ImageChops.difference(logo, diff).convert("L"), lambda p: 0 if p < 12 else 255)
        bbox = alpha.getbbox()
        if bbox:
            logo = logo.crop(bbox)
            alpha = alpha.crop(bbox)
        logo.putalpha(alpha)
        target_w = 150
        target_h = int(logo.height * target_w / logo.width)
        logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
        rounded(draw, (x - 12, y - 8, x + target_w + 12, y + target_h + 8), "#ffffff", radius=18)
        draw._image.paste(logo, (x, y), logo)
        return
    rounded(draw, (x, y, x + 178, y + 46), "#ffffff", radius=23)
    draw.ellipse((x + 8, y + 8, x + 38, y + 38), fill=COLORS["orange"])
    draw.text((x + 16, y + 12), "V", font=font(18, True), fill="#ffffff")
    draw.text((x + 48, y + 10), "VIPThink", font=font(22, True), fill=COLORS["navy"])


def paste_pea(img: Image.Image, x: int, y: int, size: int) -> None:
    pea_path = ASSET_DIR / "vipthink_pease_figure.png"
    if not pea_path.exists():
        return
    pea = Image.open(pea_path).convert("RGBA")
    pea.thumbnail((size, size), Image.Resampling.LANCZOS)
    img.paste(pea, (x, y), pea)


def build_image(data: dict[str, Any], output: Path) -> None:
    width = int(data.get("width", 1080))
    margin = 12
    y = margin
    img = Image.new("RGB", (width, 2800), COLORS["bg"])
    draw = ImageDraw.Draw(img)

    paper_x1, paper_y1, paper_x2 = margin, margin, width - margin
    rounded(draw, (paper_x1, paper_y1, paper_x2, 2700), COLORS["paper"], radius=24)

    header_h = 250
    header_fill = "#ffffff"
    rounded(draw, (paper_x1, y, paper_x2, y + header_h), header_fill, radius=24)
    draw.rectangle((paper_x1, y + 196, paper_x2, y + header_h), fill=header_fill)
    draw.rounded_rectangle((paper_x1 + 26, y + 24, paper_x2 - 26, y + header_h - 26), radius=24, fill=PRIMARY)
    draw.rounded_rectangle((paper_x1 + 26, y + 24, paper_x2 - 26, y + header_h - 26), radius=24, outline="#71e3b1", width=1)
    draw.rectangle((paper_x1, y + header_h - 1, paper_x2, y + header_h + 2), fill="#ffffff")
    draw_header_sparkles(draw, paper_x1 + 78, y + 52)
    recommended_level = data.get("recommended_level") or "S6"
    draw_brand(draw, paper_x2 - 224, y + 46)
    draw.text((paper_x1 + 58, y + 74), "WONDERLAB  VIPTHINK", font=font(22, True), fill="#dffbea")
    draw.text((paper_x1 + 58, y + 112), "Demo 課後報告", font=font(50, True), fill="#ffffff")
    draw.text((paper_x1 + 60, y + 180), "體驗課學習反饋", font=font(25, True), fill="#f3fff8")
    subtitle = f"{data['student']['date']}  {data['student']['time']}｜{data['student']['teacher']}｜{data['student']['course']}"
    y += header_h

    info_h = 112
    draw.rectangle((paper_x1, y, paper_x2, y + info_h), fill="#ffffff")
    info_items = [
        ("學員", data["student"]["name"]),
        ("課程", data["student"]["course"]),
        ("日期", data["student"]["date"]),
    ]
    cell_w = (paper_x2 - paper_x1) // 3
    for idx, (label, value) in enumerate(info_items):
        cx1 = paper_x1 + idx * cell_w
        cx2 = paper_x1 + (idx + 1) * cell_w if idx < 2 else paper_x2
        if idx:
            draw.line((cx1, y + 28, cx1, y + info_h - 28), fill="#d9d9df", width=2)
        lf = font(22, True)
        vf = font(30, True)
        draw.text(((cx1 + cx2) / 2 - text_w(draw, label, lf) / 2, y + 24), label, font=lf, fill="#9a9a9a")
        draw.text(((cx1 + cx2) / 2 - text_w(draw, value, vf) / 2, y + 58), value, font=vf, fill="#333333")
    y += info_h + 34

    y = summary_box(draw, y, data, width)

    metric_y = y
    metric_h = 150
    metrics = data["metrics"]
    gap = 14
    metric_w = (paper_x2 - paper_x1 - 60 - gap * 3) // 4
    metric_defs = [
        ("投入狀態", metrics["interest"], COLORS["green"], "★★★★☆"),
        ("知識掌握", metrics["mastery"], COLORS["green"], "★★★★☆"),
        ("優勢表現", metrics["strength"], COLORS["orange"], "★★★★★"),
        ("待提升項", metrics["growth"], COLORS["blue"], "★★★☆☆"),
    ]
    for idx, item in enumerate(metric_defs):
        x1 = paper_x1 + 30 + idx * (metric_w + gap)
        x2 = x1 + metric_w
        draw_metric(draw, (x1, metric_y, x2, metric_y + metric_h), *item)
    y += metric_h + 46

    matched_course = data.get("course_knowledge") or load_course_knowledge(data.get("student", {}).get("course"))
    if matched_course:
        y = course_box(draw, y, matched_course, width)

    for sec in data["sections"]:
        y = section(
            draw,
            y,
            sec["title"],
            sec["symbol"],
            COLORS[sec["accent"]],
            sec["points"],
            sec.get("tags", []),
            sec.get("notes", []),
            width,
        )

    plan = data["plan"]
    x = 38
    plan_h = 330
    rounded(draw, (x, y, width - x, y + plan_h), "#fffdf0", radius=16, outline="#ffe08a")
    draw.text((x + 22, y + 22), "學習規劃建議", font=font(26, True), fill=COLORS["orange"])
    py = y + 68
    for item in plan:
        label = item["label"]
        body = item["body"]
        draw.text((x + 26, py), label, font=font(20, True), fill=COLORS["orange"])
        py = draw_wrapped(draw, (x + 142, py), body, font(20), COLORS["ink"], width - x * 2 - 170, line_gap=9)
        py += 14
    y += plan_h + 32

    close = data["closing"]
    rounded(draw, (x, y, width - x, y + 210), "#f8fbff", radius=16, outline="#bfdbfe")
    draw.text((x + 22, y + 22), "同家長溝通重點", font=font(26, True), fill=COLORS["blue"])
    draw_wrapped(draw, (x + 24, y + 70), close, font(21), COLORS["ink"], width - x * 2 - 48, line_gap=10)
    paste_pea(img, width - x - 112, y + 116, 92)
    y += 236

    footer = "此報告根據試堂觀察、課堂內容及港澳升學場景整理，供家長了解小朋友現階段學習特點。"
    draw.text((x, y), footer, font=font(16), fill="#98a2b3")
    final_h = y + 52

    img = img.crop((0, 0, width, final_h))
    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, quality=95)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Cantonese after-class report image.")
    parser.add_argument("--input", default=str(EXAMPLE_DIR / "sample_report.json"))
    parser.add_argument("--output", default=str(SKILL_DIR / "outputs" / "sample_after_class_report.png"))
    parser.add_argument("--course", help="Override course name for matching demo_course_knowledge.json")
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if args.course:
        data.setdefault("student", {})["course"] = args.course
    build_image(data, Path(args.output))
    print(Path(args.output).resolve())


if __name__ == "__main__":
    main()
