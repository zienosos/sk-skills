---
name: tongshi-tongci
description: 港澳CC通時通次播報技能。讀取CRM通話數據，計算02組和03組的撥打均值、通時均值，找出同時低於兩項均值的CC，分別發送到對應小組群。觸發詞：「播報通時通次」「發通時通次」「通時通次」「通時通次播報」「通時通次報告」。
---

# 港澳CC通時通次播報技能

> 核心定位：CRM數據 → 計算均值 → 篩選落後 → 分發02/03組群

---

## 決策樹（快速入口）

```
收到通時通次請求
    │
    ├── 要即時數據（今日）
    │       └─→ CRM實時讀取 → 腳本計算（不能用估算！）
    │
    ├── 問某個CC的通時通次
    │       └─→ 直接查CRM該CC數據 → 對比組均值
    │
    └── 只問指標定義
            └─→ 直接回答定義（見「關鍵維度說明」）
```

---

## 關鍵維度說明

| 維度 | CRM列名 | 說明 | 達標 |
|------|---------|------|------|
| 撥次 | 撥打總數 | 今日總共撥打電話次數 | 組均為基準 |
| 通時 | 撥通總時長(分鐘) | 有效通話總時長 | 組均為基準 |
| 撥打均值 | — | 組內所有人「撥打總數」算術平均 | — |
| 通時均值 | — | 組內所有人「通時」算術平均 | — |

**篩選條件：同時滿足「撥次 < 撥打均值」AND「通時 < 通時均值」**

---

## 快速入口

| 步驟 | 內容 |
|------|------|
| 1 | 連接Edge調試端口 → 打開CRM頁面 |
| 2 | 點擊expand展開組別 |
| 3 | 解析HTML表格數據 |
| 4 | 計算均值 + 篩選落後CC |
| 5 | 校驗計算結果 |
| 6 | 組裝消息格式 |
| 7 | 分開發送到02/03組群 |

---

## ⚠️ 不能用估算！

**今日錯誤案例（2026-05-14）：**
- 錯誤：手工睇圖估算，以為03組「無」低於均值CC
- 正確：用Python腳本計算，發現周春華(14次/4分)、潘海麗(85次/34分) 都低於均值

**必須用自動化腳本從CRM實時拉取數據，否則數字會錯！**

---

## 步驟1-3：讀取CRM數據

### 第一步：打開CRM
1. 連接 Edge 調試端口：`http://localhost:9222`
2. 導航到：`https://cc.vipthink.cn/#/tongji/cc_call_phone`

### 第二步：讀取數據
1. 頁面加載完成後，等待3秒
2. 取消隱藏expand圖標：
```javascript
await page.evaluate(() => {
    document.querySelectorAll('.el-table__expand-icon').forEach(i => i.style.display = '');
});
```
3. 點擊「港澳CC03組」行的expand圖標（x=246, y=238），等待0.8秒
4. 點擊「港澳CC02組」行的expand圖標（x=246, y=285），等待2秒
5. 從HTML中解析表格數據

### 第三步：解析數據

**列索引：**
- `clean[0]` = 姓名
- `clean[3]` = 撥打總數 = **撥次**
- `clean[6]` = 撥通總時長(分鐘) = **通時**

**分組邏輯：**
- 遇到 `港澳CC03組` → 之後的個人數據歸03組
- 遇到 `港澳CC02組` → 之後的個人數據歸02組

---

## 步驟4：計算均值

```
02組均值（撥次）= 02組所有人「撥打總數」之和 ÷ 02組人數
02組均值（通時）= 02組所有人「通時」之和 ÷ 02組人數
03組均值（撥次）= 03組所有人「撥打總數」之和 ÷ 03組人數
03組均值（通時）= 03組所有人「通時」之和 ÷ 03組人數
```

---

## 步驟5：篩選低於均值的CC

**條件：同時滿足「撥打總數 < 撥打均值」AND「通時 < 通時均值」**

---

## 步驟6：校驗計算結果（必須！）

在組裝消息前，快速驗證：
- ✅ 02組每人「撥打總數」之和 ÷ 人數 = 顯示的均值？
- ✅ 03組每人「通時」之和 ÷ 人數 = 顯示的均值？
- ✅ 低於均值的CC：同時滿足「撥次<均值」AND「通時<均值」

如有疑問，必須重新跑腳本核實，唔好手工調整數字！

---

## 步驟7：組裝格式（不能改格式！）

```
📞 当前通时通次播报（截止XX:XX）

【港澳CC02组】 拨打均值：XX次 通时均值：XX分钟

低于均值的CC：姓名(XX次/XX分钟) ⬇️ 姓名(XX次/XX分钟) ⬇️

【港澳CC03组】 拨打均值：XX次 通时均值：XX分钟

低于均值的CC：姓名(XX次/XX分钟) ⬇️

大家加油打电话啦！💪越努力越幸运！🔥
```

**格式規則：**
- 📞 開頭電話emoji + 「当前通时通次播报（截止時間）」
- 兩組分開，每組先列【組名】+ 撥打均值 + 通時均值
- 「低于均值的CC：」+ 姓名(次/分钟) ⬇️，多個用空格分隔
- 如果冇任何人同時低於兩項均值，寫「低于均值的CC：無」
- 結尾：「大家加油打电话啦！💪越努力越幸运！🔥」

---

## 步驟8：分開發送（對應Webhook）

- **02組內容** → 發去「港澳CC02組」釘釘群
- **03組內容** → 發去「港澳CC03組」釘釘群

### Webhook地址
- 02組：`https://oapi.dingtalk.com/robot/send?access_token=f82e421d2a6c26e551b00bd54aff4a4049d0ba7b8b8f1415e45e47c7937e869b`
- 03組：`https://oapi.dingtalk.com/robot/send?access_token=ff1f5667640a2d29f8c9bb5b1dbeff9bdf423a8df7775a6edba8db346400bf33`

---

## 自動化腳本

```python
import asyncio, sys, re, json
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        page = browser.contexts[0].pages[0]
        await page.goto('https://cc.vipthink.cn/#/tongji/cc_call_phone')
        await asyncio.sleep(3)
        await page.evaluate(
            '() => { document.querySelectorAll(".el-table__expand-icon").forEach(i => i.style.display = ""); }'
        )
        await asyncio.sleep(0.3)
        cdp = await page.context.new_cdp_session(page)

        # 展開03組 (x=246, y=238)
        for evt in ['mouseMoved','mousePressed','mouseReleased']:
            await cdp.send('Input.dispatchMouseEvent', {'type': evt, 'x': 246, 'y': 238, 'button': 'left', 'clickCount': 1})
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.8)

        # 展開02組 (x=246, y=285)
        for evt in ['mouseMoved','mousePressed','mouseReleased']:
            await cdp.send('Input.dispatchMouseEvent', {'type': evt, 'x': 246, 'y': 285, 'button': 'left', 'clickCount': 1})
            await asyncio.sleep(0.1)
        await asyncio.sleep(2)

        html = await page.evaluate('() => document.body.innerHTML')
        rows_html = re.findall(r'<tr[^>]*class="el-table__row[^"]*"[^>]*>(.*?)</tr>', html, re.DOTALL)
        cc_02, cc_03 = [], []
        seen = set()
        current_group = None

        for row_html in rows_html:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
            clean = [re.sub(r'<[^>]+>', '', c).strip().replace('\n', '|') for c in cells]
            name = clean[0].strip() if clean else ''
            if '港澳CC03組' in name:
                current_group = '03'; seen.clear()
            elif '港澳CC02組' in name:
                current_group = '02'; seen.clear()
            elif '港澳CC01組' in name or '[全部]' in name:
                current_group = None
            elif current_group and name and '[全部]' not in name and name not in seen:
                seen.add(name)
                bai = int(clean[3]) if clean[3].isdigit() else 0
                shi = int(clean[6]) if clean[6].isdigit() else 0
                rec = {'name': name, 'b': bai, 't': shi}
                if current_group == '02':
                    cc_02.append(rec)
                else:
                    cc_03.append(rec)

        avg_02_b = sum(c['b'] for c in cc_02) / len(cc_02)
        avg_02_t = sum(c['t'] for c in cc_02) / len(cc_02)
        avg_03_b = sum(c['b'] for c in cc_03) / len(cc_03)
        avg_03_t = sum(c['t'] for c in cc_03) / len(cc_03)
        below_02 = [c for c in cc_02 if c['b'] < avg_02_b and c['t'] < avg_02_t]
        below_03 = [c for c in cc_03 if c['b'] < avg_03_b and c['t'] < avg_03_t]
        ts = datetime.now().strftime('%m月%d日 %H:%M')

        def make_msg(gname, avg_b, avg_t, below_list, ts):
            parts = [c['name']+'('+str(c['b'])+'次/'+str(c['t'])+'分) ⬇️' for c in below_list]
            below_str = ' '.join(parts) if parts else '無'
            return ('📞 當前通時通次播報（截止' + ts + '）\n\n' +
                    '【' + gname + '】 撥打均值：' + str(round(avg_b)) + '次 通時均值：' + str(round(avg_t)) + '分鐘\n\n' +
                    '低於均值的CC：' + below_str + '\n\n' +
                    '大家加油打電話啦！💪越努力越幸運！🔥')

        import requests
        url_02 = 'https://oapi.dingtalk.com/robot/send?access_token=f82e421d2a6c26e551b00bd54aff4a4049d0ba7b8b8f1415e45e47c7937e869b'
        url_03 = 'https://oapi.dingtalk.com/robot/send?access_token=ff1f5667640a2d29f8c9bb5b1dbeff9bdf423a8df7775a6edba8db346400bf33'
        requests.post(url_02, json={'msgtype': 'text', 'text': {'content': make_msg('港澳CC02組', avg_02_b, avg_02_t, below_02, ts)}})
        requests.post(url_03, json={'msgtype': 'text', 'text': {'content': make_msg('港澳CC03組', avg_03_b, avg_03_t, below_03, ts)}})

asyncio.run(main())
```

---

## 錯誤預防

| ❌ 錯誤做法 | ✅ 正確做法 |
|------------|------------|
| 用「接通率」判斷 | 用「撥打均值」和「通時均值」 |
| 混淆列：把「撥打總數」當成「已撥通數」 | 正確列索引（[3]=撥次，[6]=通時） |
| 混合發送到同一個群 | 02組發02組群，03組發03組群 |
| expand坐標錯誤 | 03組(246,238)，02組(246,285) |
| expand後等待時間太短 | 03組expand後等0.8秒，02組expand後等2秒 |

---

## ⚠️ 用戶確認檢查點

**發送前必須確認：**
> 「我幫你睇下今日通時通次數據，confirm我就發去02組和03組群？」

收到確認後才分組發送。

---

## 邊界條件（Fallback）

| 場景 | 處理 |
|------|------|
| CRM頁面打唔開 | 檢查Edge是否已開啟調試端口（9222）；檢查網絡 |
| expand點擊無反應 | 嘗試重新點擊；等待時間增加到2秒 |
| 解析不到數據 | 檢查HTML結構是否有變；用正則匹配關鍵詞定位 |
| 某組沒有成員數據 | 顯示「低於均值的CC：無」，唔顯示空白 |
| 計算結果為空 | 均值顯示「--」，唔顯示「None」或「0」 |
| 釘釘發送失敗 | 顯示錯誤信息，提示用戶手動複製 |

---

*更新：2026-05-16 · Darwin優化*
*決策樹+校驗步驟+自動化腳本+確認點*