---
name: after-class-report
description: 港澳 VIPThink demo 課後報告圖片生成技能。當用戶提供老師課後反饋、學員 demo 課表現、推薦 level，並要求生成可發給家長的繁體粵語圖片報告、課後學習規劃、飛書私聊發圖時使用。
metadata:
  short-description: 生成港澳家長版 VIPThink 課後報告圖片
---

# VIPThink 課後報告圖片生成

## 使用時機

當用戶貼出老師 demo 課後反饋，希望整理成「可直接發給港澳家長看的圖片報告」時使用本技能。

固定輸出風格：
- 繁體中文，偏港澳家長可讀的粵語書面語。
- VIPThink 豌豆綠視覺，logo 右上角。
- 長圖、資訊完整、排版清晰；避免花哨高亮、紫綠配色、右上角擁擠裝飾。
- 融入數學能力點、香港升學場景、兒童心理角度和學習規劃。

## 工作流

1. 從老師反饋提取：學員姓名、ID、日期、demo 課名稱、性格/課堂狀態、各環節表現、推薦 level、家長溝通情況。
2. 參考 `references/demo_course_knowledge.json` 匹配課程知識點；如果未匹配到，根據反饋自行概括數學能力點。
3. 按 `examples/sample_report.json` 結構寫一份臨時 JSON。真實學員 JSON 應保存在本地工作目錄，不要提交到倉庫。
4. 執行生成腳本：

```bash
python3 after-class-report/scripts/generate_report_image.py \
  --input /path/to/report.json \
  --output /path/to/outputs/student_after_class_report.png
```

5. 生成後用圖片查看工具快速檢查：文字無遮擋、logo 不擁擠、推薦 level 不截斷、繁體字體正常。
6. 如需飛書私聊發圖，使用：

```bash
FEISHU_APP_ID="..." FEISHU_APP_SECRET="..." FEISHU_OPEN_ID="..." \
python3 after-class-report/scripts/feishu_send_image.py /path/to/image.png
```

敏感資料只可使用環境變量或本機安全配置，不要寫入 skill 文件。

## 文案規則

- 不要把老師原話逐字搬給家長；要轉成專業、溫和、可行動的表述。
- 先肯定孩子，再指出提升方向。對害羞、專注力不足、基礎薄弱等問題，用兒童心理角度解釋成「可訓練能力」。
- 數學知識要具體：例如觀察對應、分類歸納、逆向推理、組合枚舉、5 以內加減、時間統籌等。
- 學習規劃分為學習方向、短期目標、中期目標、家長配合。
- 香港升學連結要自然，例如小學課堂適應、面試表達、應用題審題、呈分前的理解力和表達力。

## 依賴

```bash
python3 -m pip install -r after-class-report/requirements.txt
```

## 清理

生成圖片屬臨時文件。白天連續生成時可先保留，晚上或用戶要求時再統一清理輸出目錄。

