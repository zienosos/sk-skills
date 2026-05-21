---
name: vipthink-performance-report
description: 港澳CC每日業績彙報技能。當用戶提到「業績」「彙報」「基線」「進度」「落後CC」時自動觸發。讀取桌面益智業績表.xlsx，計算當月GMV差距、落後CC，生成釘釘消息發送至港澳5月馬到成功群。觸發詞：「最新業績」「最新進度」「今日基線」「發一下業績彙報」「業績彙報」「落後CC」。
---

# 港澳CC業績彙報 Skill

> 核心定位：桌面益智業績表.xlsx → 計算GMV差距+落後CC → 釘釘馬到成功群
> 與daily-report分工：本技能=主動查詢（用戶問時）；daily-report=自動定時（每天10:30）

---

## 決策樹（快速入口）

```
收到業績查詢請求
    │
    ├── 問「最新業績」「今日進度」
    │       └─→ 讀取Excel → 計算GMV差距 → 發送馬到成功群
    │
    ├── 問「某個CC落後」
    │       └─→ 讀取Excel → 定位該CC → 對比組均
    │
    ├── 想主動發給02組/03組群
    │       └─→ 用cc-analysis的Webhook（不是馬到成功群）
    │
    └── 只問指標定義
            └─→ 直接回答（見「關鍵維度說明」）
```

---

## 數據源

| 字段 | 內容 |
|------|------|
| 文件 | `C:\Users\wangzengzeng\Desktop\益智業績表.xlsx` |
| Sheet | `2026年5月` |
| 讀取方式 | `openpyxl`，`data_only=True` |

---

## 步驟1：讀取Excel數據

```python
import openpyxl
from datetime import datetime

today = datetime.now()
day = today.day

wb = openpyxl.load_workbook(r'C:\Users\wangzengzeng\Desktop\益智業績表.xlsx', data_only=True)
ws = wb['2026年5月']
```

---

## 步驟2：計算今日基線

```python
baseline_map = {
    1:0, 2:1, 3:2, 4:4, 5:6, 6:9, 7:12, 8:16, 9:21, 10:26,
    11:29, 12:30, 13:32, 14:34, 15:38, 16:43, 17:48, 18:51,
    19:52, 20:54, 21:57, 22:61, 23:66, 24:71, 25:74, 26:76,
    27:79, 28:82, 29:86, 30:92, 31:100
}
baseline = baseline_map.get(day, 0)
```

---

## 步驟3：讀取彙總數據

| 行 | 內容 |
|----|------|
| 2 | 03組彙總數據 |
| 3 | 02組彙總數據 |
| 4 | 整體彙總數據 |
| 14-31 | 各CC明細 |

每行通常包含：組名、GMV、達成率等列（具體列位以實際Excel為準）

---

## 步驟4：識別落後CC

達成率 < 今日基線 的CC即為落後

---

## 步驟5：生成消息格式

```
📊 港澳CC每日業績彙報
YYYY年MM月DD日 HH:MM

🎯 今日基線：XX%
💰 整體今日需完成：XXX,XXX
📈 港澳進度：單量XX.X% | GMVXX.X%

【02組】主管：@陳嘉輝
當前進度：XX.XX% | 今日需完成：XXX,XXX
⚠️ 落後CC：落後CC名單（用 / 分隔）

【03組】主管：@周春華
當前進度：XX.XX% | 今日需完成：XXX,XXX
⚠️ 落後CC：落後CC名單（用 / 分隔）

💪 一起沖單！加油！
```

---

## 步驟6：發送釘釘

```python
import requests

webhook = "https://oapi.dingtalk.com/robot/send?access_token=93b759980ae566ac2131777f6de2b50441a9ab122dfcbe3801588ab0538b8c4c"
requests.post(webhook, json={"msgtype": "text", "text": {"content": message}})
```

### Webhook
- 馬到成功群：`https://oapi.dingtalk.com/robot/send?access_token=93b759980ae566ac2131777f6de2b50441a9ab122dfcbe3801588ab0538b8c4c`

---

## ⚠️ 用戶確認檢查點

**發送前必須確認：**
> 「我幫你睇下今日業績數據，confirm我就發去馬到成功群？」

收到確認後才發送，避免發錯群或數據有誤。

---

## 邊界條件（Fallback）

| 場景 | 處理 |
|------|------|
| Excel文件搵唔到 | 提示「益智業績表.xlsx未喺桌面搵到，請確認文件位置」 |
| Sheet名稱唔對 | 嘗試常見名稱：`2026年5月`、`5月`、`May` |
| 數據行位置有變 | 根據關鍵詞搜索行（如「03組彙總」），唔 hardcode行號 |
| 落後CC名單為空 | 顯示「⚠️ 落後CC：無」，唔顯示空白 |
| 釘釘發送失敗 | 顯示錯誤信息，提示用戶手動複製消息內容 |
| 數值為None或空 | 顯示「--」，唔顯示「None」 |

---

## 腳本位置

| 腳本 | 用途 |
|------|------|
| `daily_task/read_report.py` | 主腳本，讀取Excel並發送釘釘消息 |
| `daily_task/report_cc02.py` | 02組數據 |
| `daily_task/report_cc03.py` | 03組數據 |

**參數：** `--silent`（不發送，僅打印消息內容，用於調試）；`--date YYYY-MM-DD`（指定日期，預設今日）

---

*更新：2026-05-16 · Darwin優化*
*決策樹+分工邊界+繁體統一+確認點*