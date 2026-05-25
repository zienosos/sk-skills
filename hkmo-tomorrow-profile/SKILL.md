---
name: hkmo-tomorrow-profile
description: 港澳CC明日待上课学员画像生成。自动拉取CRM待上课学员，筛选港澳CC02/03组、有效录音，ASR转写，并生成两份飞书原生文档链接给主管/负责人。触发词：「明日用户画像」「明日待上课画像」「港澳待上课画像」「生成用户画像」「明日学员画像」。
---

# 港澳明日待上课学员画像

## 目标

把 CRM「待上课学员」自动整理成港澳CC02组、港澳CC03组两份飞书原生文档，用于主管和 CC 第二天课后跟进。

## 运行方式

先设置环境变量，参考 `.env.example`：

```bash
export CRM_USERNAME='CRM账号'
export CRM_PASSWORD='CRM密码'
export DASHSCOPE_API_KEY='DashScope Key'
export FEISHU_APP_ID='飞书应用ID'
export FEISHU_APP_SECRET='飞书应用Secret'
export FEISHU_OPEN_ID='接收链接的人'
```

一键生成：

```bash
python3 scripts/run_daily_feishu_profiles.py --date YYYY-MM-DD
```

## 核心规则

- 只拉取港澳CC02组、港澳CC03组。
- 录音只分析归属CC本人拨打的电话。
- 录音必须已接通、有录音URL、通话时长超过3分钟。
- 不在飞书文档里展示高/中/低意向。
- 飞书文档直接用原生 block 生成，不输出 Markdown。
- 飞书文档默认设置为获得链接的所有互联网用户可查看。
- 飞书标题格式：`港澳CC02组26号明日待上课画像分析`。

## 输出结构

1. 主管总览：待上课人数、重点关注人数、有效录音画像、每个CC课量和重点提醒。
2. CC课量与重点：每个CC一张轻卡，列出学员ID、用户ID、上课时间和风险。
3. CC学员卡片：按CC分组，重点学员排前，给出用户ID、学员ID、画像判断、今日动作、课后第一句话、话术和备注摘要。

## 文件说明

- `scripts/run_daily_feishu_profiles.py`：一键入口。
- `scripts/fetch_crm_wait_class.py`：CRM待上课学员和录音筛选。
- `scripts/transcribe_valid_recordings.py`：有效录音ASR。
- `scripts/feishu_docx_native.py`：飞书原生文档生成和链接发送。
- `config/hkmo_profile_rules.json`：港澳画像规则和粤语话术。
- `templates/tomorrow_lessons_sample.csv`：脱敏样例。

## 注意

不要提交运行产生的 `outputs/`，其中可能包含真实学员ID、录音URL和转写内容。
