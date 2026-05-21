---
name: vipthink-crm-recording
description: 豌豆思維CRM錄音分析技能。從CRM調取通話錄音，通過ASR轉文字+AI質檢，生成話術評分、客戶意向、改進建議等報告。當用戶提到以下任何內容時立即使用：CRM錄音、錄音分析、通話質檢、銷售錄音、話術分析、CC復盤、團隊錄音、錄音轉文字、ASR轉錄、質檢評分、錄音報告、錄音排名、優秀錄音、差錄音、錄音培訓、錄音標杆、錄音改進、錄音總結、錄音評價、錄音數據、通話數據、有效通話、錄音時長、CC表現、客戶意向、對話質量、錄音URL、批量分析。觸發詞：「錄音分析」「通話質檢」「話術分析」「CC復盤」「錄音轉文字」「ASR轉錄」「質檢評分」「聽聽錄音」「看看通話」。
---

# 豌豆思維CRM錄音調取與分析技能

> 核心定位：CRM錄音 → ASR轉文字 → AI質檢 → 話術報告
> 適用：CC復盤、團隊培訓、批量質檢

---

## 決策樹（快速入口）

```
收到錄音相關請求
    │
    ├── 問「錄音分析」「話術分析」
    │       └─→ 立即進入兩階段流程（調取+分析）
    │
    ├── 問「某個CC的錄音」
    │       └─→ CRM調取該CC錄音 → ASR → 質檢報告
    │
    ├── 問「團隊整體質檢」
    │       └─→ 批量分析（全組錄音）
    │
    ├── 只問「某個指標的定義」
    │       └─→ 直接回答，不走流程
    │
    └── 問「點樣調取錄音」
            └─→ 直接給出Step 1-6流程
```

---

## 觸發後第一輪對話（必須先確認）

當本Skill被觸發時，**必須先向用戶確認以下信息**後再執行任何CRM或API操作：

1. **分析範圍**：「請確認要分析哪個團隊？」
   - 港澳團隊（默認）
   - 北京上海團隊
   - 台灣團隊
2. **篩選條件**：「要分析哪類學生？」
   - 今日完課（默認）
   - 今日新分配
   - 今日需回訪
   - 未約課
   - 今日上課
   - 課後未撥通
3. **分析模式**：
   - 單條錄音分析（默認）
   - 批量分析（需確認數量上限，建議≤20條/批）
4. **輸出格式**：
   - Markdown報告（默認）
   - Excel報表

用戶確認後，根據選擇拼接CRM URL並開始執行。

---

## 兩階段流程總覽

| 階段 | 內容 | 工具 |
|------|------|------|
| **第一階段：錄音調取** | CRM頁面 → 定位學生 → 獲取錄音URL | browser工具 |
| **第二階段：語音分析** | ASR轉文字 → AI質檢 → 生成報告 | Python腳本 |

---

## 第一階段：CRM錄音調取（6步）

### Step 1：導航到CRM頁面

| 團隊 | admin_group_list | URL |
|------|-----------------|-----|
| 港澳團隊 | 8,70,172 | `https://cc.vipthink.cn/#/student/cc_m_list?admin_group_list=8,70,172&main_type=today_lesson_end` |
| 北京上海團隊 | 8,70,154 | `https://cc.vipthink.cn/#/student/cc_m_list?admin_group_list=8,70,154&main_type=today_lesson_end` |
| 台灣團隊 | 8,70,180 | `https://cc.vipthink.cn/#/student/cc_m_list?admin_group_list=8,70,180&main_type=today_lesson_end` |

### Step 2：點擊學生姓名

```javascript
var rows = document.querySelectorAll('.el-table__body-wrapper tbody tr');
rows[0].querySelector('td:nth-child(4) .el-button--text').click();
```

### Step 3：切換到電話標籤

```javascript
var dialog = document.querySelectorAll('.el-dialog__wrapper')[11];
dialog.querySelectorAll('.el-tabs__item')[2].click();
```

### Step 4：篩選有效通話（>30秒）

列結構: 0=複選框, 1=撥打時間, 2=接聽時間, 3=撥打人, 4=渠道, 5=撥通時長, 6=通話時長, 7=是否有效

條件: `isValid === '是' && totalSeconds > 30`

### Step 5：獲取錄音URL

```javascript
// 方法1：從audio元素獲取
var audio = document.querySelector('audio');
var url = audio ? audio.src : null;

// 方法2：從下載按鈕獲取
if (!url) {
    var btns = document.querySelectorAll('.el-button--text');
    btns.forEach(function(btn) {
        if (btn.textContent.includes('下載')) {
            url = btn.getAttribute('href') || btn.onclick.toString().match(/'(https?:\/\/[^']+)'/);
        }
    });
}
```

### Step 6：播放/驗證錄音

點擊小喇叭播放驗證

---

## 第二階段：語音分析

### API配置

| 配置項 | 值 |
|--------|------|
| DashScope API Key | `sk-99f9364af58c49d5b927f43dc08e2e5c` |
| ASR模型 | paraformer-v2 |
| ASR端點 | `https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription` |
| 質檢模型 | qwen-plus |
| 質檢端點 | `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions` |

### ASR轉錄參數

```json
{
  "model": "paraformer-v2",
  "input": {"file_urls": ["錄音URL"]},
  "parameters": {
    "channel_id": [0],
    "language_hints": ["zh", "yue"],
    "diarization_enabled": true,
    "disfluency_removal_enabled": true
  }
}
```

### 質檢分析輸出格式

```json
{
  "checkpoints": [{"name", "status", "evidence", "suggestion"}],
  "score": 0-100,
  "level": "優秀/合格/待改進",
  "summary": "整體評價",
  "customer_intent": "高/中/低",
  "conversation_quality": "流暢/一般/生硬",
  "key_phrases": ["關鍵話術"],
  "improvements": ["改進建議"]
}
```

---

## ⚠️ 三個確認檢查點

| 檢查點 | 時機 | 必須問 |
|--------|------|--------|
| **CP1** | 分析前確認 | 展示篩選結果（學生數量、有效通話數量），用戶確認後再開始 |
| **CP2** | 批量分析前確認 | 當有效通話>10條時，提醒用戶分析時間和API消耗（約30秒/條） |
| **CP3** | 報告生成後確認 | 展示報告摘要，詢問用戶是否需要深入分析某條錄音或導出Excel |

---

## 批量分析報告結構

| 模塊 | 內容 |
|------|------|
| 總體概況 | 錄音數、平均分、質量分佈、趨勢對比 |
| CC維度分析 | CC排名、詳細表現、薄弱項識別 |
| 渠道維度分析 | 各渠道平均分、標準差 |
| 質檢項完成情況 | 完成率可視化、薄弱項典型案例 |
| 客戶意向分析 | 高/中/低意向分佈及跟進建議 |
| 對話質量分析 | 流暢/一般/生硬分佈 |
| 錄音詳細分析 | 每條錄音完整質檢項、關鍵話術、改進建議 |
| 行動建議 | 高意向客戶清單、需補救CC、培訓建議 |

---

## 腳本文件

| 腳本 | 用途 |
|------|------|
| `batch_recording_analyzer_v2.py` | 批量分析主腳本（並行+多維度報告） |
| `pre_class_recording_analyzer.py` | 單條課前錄音分析腳本 |

---

## 故障排除（CRM操作）

| 問題 | 解決方案 |
|------|---------|
| browser_evaluate返回null | 檢查preload腳本；刷新頁面後重試 |
| 學生姓名snapshot不可見 | 使用JavaScript直接操作，不要依賴snapshot |
| 彈窗未出現 | 等待2秒後檢查；確認點擊的是正確元素 |
| CRM頁面改版/選擇器失效 | 使用browser_snapshot重新獲取頁面結構，動態適配新的CSS選擇器 |
| 日期設值後頁面數據空白 | 使用箭頭刷新法：點擊右箭頭前進一天→點擊左箭頭回到目標日期，觸發Vue響應式刷新 |
| 只獲取到第一頁數據 | 滾動到底部檢查分頁組件，遍歷所有頁獲取完整數據 |

---

## 故障排除（語音分析）

| 問題 | 解決方案 |
|------|---------|
| ASR轉錄失敗 | 檢查錄音URL是否過期（OSS簽名7天有效）；檢查網絡 |
| 質檢分析返回404 | 確認使用 `/compatible-mode/v1/` 端點 |
| API Key無效 | 確認使用DashScope API Key（sk-開頭） |
| 粵語識別不準 | 確認language_hints包含yue |
| 轉錄亂碼/識別率低 | 嘗試單獨使用 `language_hints: [yue]` 或 `[zh]` 重試 |

---

*更新：2026-05-16 · Darwin優化*
*決策樹+三個確認檢查點+繁體frontmatter*