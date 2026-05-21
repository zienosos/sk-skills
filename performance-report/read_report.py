# -*- coding: utf-8 -*-
"""
港澳CC业绩汇报读取脚本
用法: uv run python read_report.py [--silent]
  --silent: 仅打印，不发送钉钉
"""
import pandas as pd
import requests
import json
import sys
import os
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

# ========== 配置 ==========
EXCEL_PATH = r"C:\Users\wangzengzeng\Desktop\益智业绩表.xlsx"
SHEET_NAME = "2026年5月"
WEBHOOK_URL = "https://oapi.dingtalk.com/robot/send?access_token=93b759980ae566ac2131777f6de2b50441a9ab122dfcbe3801588ab0538b8c4c"

BASELINE = {
    1:0, 2:1, 3:2, 4:4, 5:6, 6:9, 7:12, 8:16, 9:21, 10:26,
    11:29, 12:30, 13:32, 14:34, 15:38, 16:43, 17:48, 18:51,
    19:52, 20:54, 21:57, 22:61, 23:66, 24:71, 25:74, 26:76,
    27:79, 28:82, 29:86, 30:92, 31:100
}

def get_baseline(day):
    return BASELINE.get(day, 0)

def read_performance_data():
    """读取业绩表，返回所有关键数据"""
    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME, engine='openpyxl', header=None)

    today = datetime.now()
    day = min(today.day, 31)
    baseline = get_baseline(day)
    now_str = today.strftime("%Y年%m月%d日 %H:%M")

    # 读取文件修改时间
    file_mtime = os.path.getmtime(EXCEL_PATH)
    file_time = datetime.fromtimestamp(file_mtime).strftime("%Y-%m-%d %H:%M")

    # 整体数据 (row 4)
    total = df.iloc[4]
    total_order_target = int(total[8])
    total_order_current = int(total[9])
    total_order_rate = float(total[10]) * 100
    total_gmv_target = int(total[12])
    total_gmv_current = int(total[13])
    total_gmv_rate = float(total[14]) * 100
    total_today_need = int(total_gmv_target * baseline / 100) - total_gmv_current

    # 02组数据 (row 3)
    team02 = df.iloc[3]
    team02_gmv_target = int(team02[12])
    team02_gmv_current = int(team02[13])
    team02_gmv_rate = float(team02[14]) * 100
    team02_today_need = int(team02_gmv_target * baseline / 100) - team02_gmv_current

    # 03组数据 (row 2)
    team03 = df.iloc[2]
    team03_gmv_target = int(team03[12])
    team03_gmv_current = int(team03[13])
    team03_gmv_rate = float(team03[14]) * 100
    team03_today_need = int(team03_gmv_target * baseline / 100) - team03_gmv_current

    # 落后CC (rows 14-31)
    lagging_02 = []
    lagging_03 = []
    for i in range(14, 32):
        try:
            row = df.iloc[i]
            name = str(row[1]).strip()
            team = str(row[2]).strip()
            rate = float(row[6]) * 100 if pd.notna(row[6]) else 0

            if '02组' in team and rate < baseline and name not in ['nan', '']:
                lagging_02.append(name)
            elif '03组' in team and rate < baseline and name not in ['nan', '']:
                lagging_03.append(name)
        except (IndexError, ValueError):
            continue

    return {
        'now_str': now_str,
        'file_time': file_time,
        'baseline': baseline,
        'total_today_need': total_today_need,
        'total_order_rate': total_order_rate,
        'total_gmv_rate': total_gmv_rate,
        'team02_gmv_rate': team02_gmv_rate,
        'team02_today_need': team02_today_need,
        'lagging_02': lagging_02,
        'team03_gmv_rate': team03_gmv_rate,
        'team03_today_need': team03_today_need,
        'lagging_03': lagging_03,
    }

def generate_message(data):
    """生成钉钉消息文本"""
    return f"""📊 港澳CC每日业绩汇报
{data['now_str']}

🎯 今日基线：{data['baseline']}%
💰 整体今日需完成：{data['total_today_need']:,}
📈 港澳进度：单量{data['total_order_rate']:.1f}% | GMV{data['total_gmv_rate']:.1f}%

【02组】主管：@陈嘉辉
当前进度：{data['team02_gmv_rate']:.2f}% | 今日需完成：{data['team02_today_need']:,}
⚠️ 落后CC：{' / '.join(data['lagging_02']) if data['lagging_02'] else '(暂无落后)'}

【03组】主管：@周春华
当前进度：{data['team03_gmv_rate']:.2f}% | 今日需完成：{data['team03_today_need']:,}
⚠️ 落后CC：{' / '.join(data['lagging_03']) if data['lagging_03'] else '(暂无落后)'}

💪 一起冲单！加油！"""

def send_dingtalk(message):
    headers = {"Content-Type": "application/json"}
    payload = {
        "msgtype": "text",
        "text": {"content": message},
        "at": {"atMobiles": [], "isAtAll": False}
    }
    resp = requests.post(WEBHOOK_URL, headers=headers, data=json.dumps(payload), timeout=10)
    return resp.json()

def main():
    silent = '--silent' in sys.argv or '-s' in sys.argv

    try:
        data = read_performance_data()
        msg = generate_message(data)
        print(msg)

        if not silent:
            result = send_dingtalk(msg)
            print(f"\n✅ 发送结果: {result}")
        else:
            print(f"\n[Silent模式 - 未发送]")
            print(f"📁 数据来源文件更新时间: {data['file_time']}")

    except FileNotFoundError:
        print(f"❌ 找不到文件: {EXCEL_PATH}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
