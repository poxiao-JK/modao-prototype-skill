---
name: modao-prototype
description: 查看与抓取墨刀（MockingBot/Modao）原型：给一个墨刀分享链接，自动读取页面树（含分组层级）、按需或全量导出离线HTML、抓取每页文字与设计标注、生成内容包围盒截图、提取批注。当用户提到墨刀、modao、原型、原型稿、看原型、抓取原型、原型截图、读取原型，或给出 modao.cc 链接要求分析原型内容时，使用本技能。基于 Python + Playwright（自管浏览器，零外部调试依赖）。
---

# 墨刀原型查看与抓取（Python + Playwright 版）

给一个墨刀分享链接，产出完整本地档案：页面树（含分组层级）、每页文字与设计标注、内容包围盒截图、可离线打开的原型源文件、批注提取。

**文字与截图冲突时以截图为准（截图=人眼所见）。**

## 依赖（首次使用一次性准备）

| 依赖 | 版本 | 安装 |
|---|---|---|
| Python | ≥ 3.9 | — |
| playwright（pip 包） | 最新 | `pip install playwright -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| Chromium（Playwright 自管） | 随 pip 包 | `python -m playwright install chromium`（国内慢时先 `set PLAYWRIGHT_DOWNLOAD_HOST=https://registry.npmmirror.com/-/binary/playwright`） |

- **不需要**安装/常驻外部调试 Chrome（Playwright 自管浏览器实例）
- 无需任何 npm 包

## 首次使用流程（AI 按此顺序执行）

1. **装依赖**：上表两条命令（已装过会跳过）
2. **设置存储位置**：检查 `MODAO_PROTOTYPE_HOME` 环境变量（`echo %MODAO_PROTOTYPE_HOME%`）。
   **无默认值，未设置时必须询问用户**希望存放在哪个目录 → 拿到路径后
   `setx MODAO_PROTOTYPE_HOME "<用户给的路径>"` 持久化，并在当前会话同时设置（`set MODAO_PROTOTYPE_HOME ...` 或进程环境）后继续
3. 之后每次使用直接跑下方命令即可（`MODAO_PROTOTYPE_HOME` 已持久化）

不同原型自动按项目隔离：`projects/{页面标题}-{项目ID}/`（标题自动取墨刀页面 title，项目 ID 保证唯一）。

## 标准流程

### A. 全量模式（已知要用整个原型，11 页实测约 45 秒）

```bash
# 1) 读页面树+层级，生成 tree.json（约 6 秒）
python scripts/modao_tree.py "<墨刀分享链接>" "<项目目录>/tree.json"

# 2) 导出离线HTML+资源（默认仅第一个根分支=正式设计；--all 含草稿/副本/调研分支）
python scripts/modao_export.py "<墨刀分享链接>" "<项目目录>/tree.json" "<项目目录>/offline" [--all]

# 3) 逐页读文字+标注+截图（默认不截正常页；无文字页自动强制截图兜底；--shots 全部截图）
python scripts/modao_shoot.py "<项目目录>/tree.json" "<项目目录>/offline" "<项目目录>" [--shots]
```

### B. 按需模式（推荐：先看目录，用到哪页下载哪页）

```bash
# 1) 同上 tree（约 6 秒）
# 2) 读 catalog.md 确定相关页面（不下载任何页面内容）
# 3) 按需下载单页：未下载自动下载（HTML+资源+文字，3~5秒/页）；已下载秒回；--refresh 强刷；--shots 补概览图
python scripts/modao_page.py "<项目目录>" "<页面名>" [--shots] [--refresh]
```

### C. 批注提取（可选，逐页在线切换，较慢）

```bash
python scripts/modao_notes.py "<墨刀分享链接>" "<项目目录>/tree.json" "<项目目录>/notes.json"
```

## catalog.md 是找页面的唯一入口

分析原型**第一步读 catalog.md**，它包含：分享链接（总链接，用于更新/重新下载）、完整层级树、每页下载状态与文字量、根分支说明（当前版/副本/调研）。之后：

- 需要某页文字与标注 → 读该页 `meta.json` 的 `text` 字段
- 需要某页视觉 → 读该页 `overview.png`（若未生成，用 modao_page --shots 补）
- 无文字的页面**自动强制截图**（纯图片页/空白页的视觉是唯一信息源，防止误判为空白）；有文字的页默认不截图（`--shots` 可全量）
- 空白占位页如实标记 empty，列入「待设计补充」，**不编造内容**

## 产出结构

```
<项目目录>/
├── project.json     # 分享链接、页面状态表（downloaded/empty/textLen）、资源下载缓存表
├── tree.json        # 页面树：name/pageFile/path/rootBranch/rootFile
├── catalog.md       # ★ 目录：AI/人找页面的入口
├── offline/         # 离线HTML+资源（浏览器打开 .html 即还原原型）
├── shots/           # 概览截图（按需生成）
└── pages/           # 每页 meta.json（文字+标注+画布尺寸+图片数）
```

## 排障

- playwright 未安装：`pip install playwright && python -m playwright install chromium`（国内建议 `PLAYWRIGHT_DOWNLOAD_HOST=https://registry.npmmirror.com/-/binary/playwright`）
- `未找到原型 iframe`：页面加载慢，重跑即可（本地操作可重试，结果幂等）
- 某页文字与图片均为空：原型本身是空白占位页，如实报告「待设计补充」
- 资源下载 fail 4 个：装饰字体（sketchfonts），不影响内容
- `ALREADY CACHED`：页面已下载过（--refresh 强制刷新）
- MODAO_PROTOTYPE_HOME 未设置（新开终端）：setx 已持久化则重开终端即生效；未 setx 则按首次流程询问用户
