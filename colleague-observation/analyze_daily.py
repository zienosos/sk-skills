# colleague-observation 每日分析腳本
# 用途：每天22:30自動分析當日對話記錄，更新問題圖譜+教練切入點
# 使用：uv run python analyze_daily.py

import sys
from pathlib import Path
from datetime import datetime, date
import re

COACHING_DIR = Path(r"C:\Users\wangzengzeng\.openclaw\workspace-vipthink\coaching")
CONVERSATIONS_FILE = COACHING_DIR / "colleague_conversations.md"
PROFILES_FILE = COACHING_DIR / "colleague_profiles.md"
LOG_FILE = COACHING_DIR / "coaching_log.md"

def read_conversations():
    """讀取對話記錄"""
    if not CONVERSATIONS_FILE.exists():
        print(f"[警告] 找不到 {CONVERSATIONS_FILE}")
        return []
    
    with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    records = []
    entries = content.split("## ")
    
    for entry in entries:
        if "**同事：**" not in entry:
            continue
        
        record = {}
        lines = entry.strip().split("\n")
        
        for line in lines:
            if "**同事：**" in line:
                name_part = line.split("**同事：**")[1].strip()
                # 格式：「名字（組別）」
                if "（" in name_part:
                    record["name"] = name_part.split("（")[0].strip()
                    record["group"] = name_part.split("（")[1].split("）")[0].strip()
                else:
                    record["name"] = name_part
                    record["group"] = ""
            elif "**問題類型：**" in line:
                record["type"] = line.split("**問題類型：**")[1].strip()
            elif "**問題內容：**" in line:
                record["content"] = line.split("**問題內容：**")[1].strip()
            elif "**教練意義：**" in line:
                record["signal"] = line.split("**教練意義：**")[1].strip()
        
        if "name" in record and "content" in record:
            records.append(record)
    
    return records

def get_today_records(records):
    """取得今日記錄"""
    today = date.today().strftime("%Y-%m-%d")
    today_str = date.today().strftime("%Y-%m-%d")
    
    today_records = []
    for r in records:
        # 簡單匹配：包含今天日期的記錄
        # 實際記錄格式是 "## YYYY-MM-DD HH:MM"
        # 需要從conversations文件提取日期
        pass
    
    return [r for r in records if "content" in r]  # 暫時返回所有記錄

def analyze_by_colleague(records):
    """按同事分組分析"""
    analysis = {}
    
    for r in records:
        name = r.get("name", "未知")
        if name not in analysis:
            analysis[name] = {
                "count": 0,
                "types": {},
                "contents": [],
                "signals": [],
                "group": r.get("group", "")
            }
        
        analysis[name]["count"] += 1
        
        qtype = r.get("type", "其他")
        analysis[name]["types"][qtype] = analysis[name]["types"].get(qtype, 0) + 1
        
        content = r.get("content", "")
        if content:
            analysis[name]["contents"].append(content[:50])  # 只保存前50字
        
        signal = r.get("signal", "")
        if signal:
            analysis[name]["signals"].append(signal)
    
    return analysis

def generate_daily_report(analysis):
    """生成每日教練報告"""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    total_questions = sum(d["count"] for d in analysis.values())
    
    report = f"""
========================================
同事觀察每日報告 - {today}
========================================

今日提問總數：{total_questions}條
涉及同事：{len(analysis)}人

"""
    
    for name, data in sorted(analysis.items(), key=lambda x: x[1]["count"], reverse=True):
        report += f"\n【{name}】（{data['group']}）\n"
        report += f"  提問次數：{data['count']}次\n"
        
        top_types = sorted(data["types"].items(), key=lambda x: x[1], reverse=True)
        type_str = " / ".join([f"{t}({c}次)" for t, c in top_types])
        report += f"  問題類型：{type_str}\n"
        
        # 教練信號
        risk_signals = [s for s in data["signals"] if "⚠️" in s or "🔴" in s]
        good_signals = [s for s in data["signals"] if "✅" in s]
        
        if risk_signals:
            report += f"  ⚠️ 風險信號：{'；'.join(set(risk_signals))}\n"
        if good_signals:
            report += f"  ✅ 積極信號：{'；'.join(set(good_signals))}\n"
        
        # 最近問題
        if data["contents"]:
            report += f"  最近問題：{data['contents'][-1]}...\n"
    
    return report

def main():
    """主程序"""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"[同事觀察系統] {today} 開始分析")
    
    # 讀取對話記錄
    records = read_conversations()
    print(f"讀取到 {len(records)} 條對話記錄")
    
    if not records:
        print("[完成] 今日暫無對話記錄")
        return
    
    # 分析
    analysis = analyze_by_colleague(records)
    print(f"分析了 {len(analysis)} 位同事")
    
    # 生成報告
    report = generate_daily_report(analysis)
    print(report)
    
    # 記錄到教練日誌
    log_entry = f"\n{today} - 每日對話分析：{len(records)}條記錄，{len(analysis)}位同事"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry + "\n")
    
    print(f"\n[同事觀察系統] 分析完成")

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
