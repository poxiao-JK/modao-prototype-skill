# -*- coding: utf-8 -*-
"""cli.py — modao-prototype 命令行入口（子命令分发，零逻辑）。"""
import sys

USAGE = """modao-prototype — 墨刀原型抓取（Python + Playwright）

用法:
  modao-prototype tree   <墨刀分享链接> <输出tree.json>
  modao-prototype export <墨刀分享链接> <tree.json> <离线HTML目录> [--roots <名,名>]
  modao-prototype page   <项目目录> "<页面名>" [--shots] [--refresh]
  modao-prototype shoot  <tree.json> <离线HTML目录> <输出目录> [--shots]
  modao-prototype notes  <墨刀分享链接> <tree.json> <输出notes.json>
  modao-prototype catalog <项目目录>            # 重新生成 catalog.md
"""


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print(USAGE)
        sys.exit(0 if args else 2)
    cmd, rest = args[0], args[1:]
    sys.argv = [sys.argv[0]] + rest
    if cmd == 'tree':
        import modao_tree
        modao_tree.main()
    elif cmd == 'export':
        import modao_export
        modao_export.main()
    elif cmd == 'page':
        import modao_page
        modao_page.main()
    elif cmd == 'shoot':
        import modao_shoot
        modao_shoot.main()
    elif cmd == 'notes':
        import modao_notes
        modao_notes.main()
    elif cmd == 'catalog':
        import modao_catalog
        import json, os
        if len(rest) < 1:
            print('用法: modao-prototype catalog <项目目录>')
            sys.exit(2)
        proj_dir = rest[0].replace('\\', '/').rstrip('/') + '/'
        proj = json.load(open(proj_dir + 'project.json', encoding='utf-8'))
        from modao_catalog import buildCatalog
        buildCatalog(proj, proj_dir)
        print('catalog.md refreshed')
    else:
        print(f'未知命令: {cmd}\n')
        print(USAGE)
        sys.exit(2)
