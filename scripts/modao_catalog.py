# -*- coding: utf-8 -*-
"""modao_catalog.py — 目录（catalog.md）生成器：人/AI 双友好，找页面的入口文件"""
import os


def buildCatalog(project, proj_dir):
    tree = project.get('tree') or []
    pages = project.get('pages') or {}
    dl_count = sum(1 for p in pages.values() if p.get('downloaded'))
    now = (project.get('updatedAt') or '')[:19]
    title = project.get('title', '')
    share_url = project.get('shareUrl', '')
    share_id = project.get('shareId', '')
    dir_name = project.get('dirName', '')

    md = '# 墨刀原型目录：' + title + '\n\n'
    md += '> 分享链接（总链接，用于更新/重新下载）：' + share_url + '\n'
    md += ('> 项目ID：' + share_id + ' ｜ 目录：projects/' + dir_name +
           ' ｜ 树更新：' + now + ' ｜ 已下载页面：' + str(dl_count) + '/' + str(len(tree)) + '\n\n')
    md += ('> **找页面方法**：① 在下方页面树定位需要的页面 ② 未下载的执行 '
           '`python scripts/modao_page.py <项目目录> "<页面名>"`（3~5秒自动下载并提取文字）'
           '③ 已下载的页面直接读 pages/*.meta.json（text 字段 = 该页全部文字与设计标注）。'
           '视觉：offline/ 里的 .html 用浏览器打开，或 shots/ 概览图。\n\n')

    md += '## 页面树（完整层级）\n\n'
    for t in tree:
        st = pages.get(t['pageFile'], {})
        indent = '  ' * len(t.get('path', []))
        if st.get('downloaded'):
            status = '已下载 ' + (st.get('updatedAt') or '')[:16]
        else:
            status = '未下载'
        md += indent + '- ' + t['name'] + ' [' + status + ']（' + t['pageFile'] + '）\n'

    md += '\n## 页面明细\n\n'
    md += '| 页面 | 层级路径 | 文件 | 状态 | 文字量 | 更新时间 |\n'
    md += '|---|---|---|---|---|---|\n'
    for t in tree:
        st = pages.get(t['pageFile'], {})
        path_str = ' > '.join(t.get('path', [])) or '（根）'
        status = '已下载' if st.get('downloaded') else '未下载'
        md += ('| ' + t['name'] + ' | ' + path_str + ' | ' + t['pageFile'] + ' | ' + status +
               ' | ' + str(st.get('textLen', 0)) + ' | ' + (st.get('updatedAt') or '')[:16] + ' |\n')

    empties = [st for st in pages.values() if st.get('downloaded') and st.get('empty')]
    md += '\n## 空白页（原型占位页）\n\n'
    if empties:
        for st in empties:
            md += '- ' + (st.get('name') or '') + '：无文字且无图片——如需求需要此页设计，请联系设计师补充；不需要则忽略\n'
    else:
        md += '- 已下载页面中无空白页\n'

    roots = []
    for t in tree:
        rf = t.get('rootFile')
        if rf and rf not in roots:
            roots.append(rf)
    md += '\n## 根分支\n\n'
    for rf in roots:
        cnt = sum(1 for t in tree if t.get('rootFile') == rf)
        md += '- ' + rf + '：' + str(cnt) + ' 页\n'

    catalog_path = os.path.join(proj_dir, 'catalog.md')
    with open(catalog_path, 'w', encoding='utf-8') as f:
        f.write(md)
    return md
