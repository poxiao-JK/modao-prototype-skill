# -*- coding: utf-8 -*-
"""modao_export.py — 按页面清单导出离线HTML+资源（Playwright 版，纯 fetch 零交互）
用法: python modao_export.py <墨刀分享链接> <tree.json> <离线HTML输出目录> [--roots <名,名>]
导出 tree.json 列出的全部页面；--roots <逗号分隔根分支名> 可过滤指定根分支。
"""
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modao_tree import find_modao_frame
from playwright.sync_api import sync_playwright

FETCH_HTML = "fetch({url}).then(r => {{ if (!r.ok) throw new Error('HTTP'+r.status); return r.text(); }})"
FETCH_B64 = "fetch({u}).then(r => {{ if (!r.ok) throw new Error('HTTP'+r.status); return r.blob(); }}).then(b => new Promise(res => {{ const fr = new FileReader(); fr.onload = () => res(fr.result); fr.readAsDataURL(b); }}))"


def resource_refs(html):
    import re
    refs = set()
    for m in re.finditer(r'(?:src|href)="([^"]+\.(?:css|js|png|svg|jpg|ttf|woff2?))"', html):
        refs.add(m.group(1))
    for m in re.finditer(r'url\(&quot;([^&]+?)&quot;\)', html):
        refs.add(m.group(1))
    for m in re.finditer(r"url\('([^']+)'\)", html):
        refs.add(m.group(1))
    return [r for r in refs if not r.startswith('data:') and not r.startswith('http')]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--roots')]
    roots = None
    ri = sys.argv.index('--roots') if '--roots' in sys.argv else -1
    if ri >= 0:
        roots = sys.argv[ri + 1]
    if len(args) < 3:
        print('用法: python modao_export.py <墨刀分享链接> <tree.json> <离线HTML输出目录> [--roots <名,名>]')
        sys.exit(2)
    share_url, tree_path, out_dir = args[0], args[1], args[2]
    out_dir = out_dir.replace('\\', '/').rstrip('/') + '/'
    tree = json.load(open(tree_path, encoding='utf-8'))
    pages = tree
    if roots:
        keep = roots.split(',')
        pages = [t for t in tree if t.get('rootFile') in keep]
    print(f"pages: {len(pages)}/{len(tree)}")

    # 资源缓存预扫描
    downloaded = set()
    for root, _, files in os.walk(out_dir):
        for f in files:
            downloaded.add(os.path.relpath(os.path.join(root, f), out_dir).replace('\\', '/'))
    print('resource cache:', len(downloaded), 'files')

    os.makedirs(out_dir, exist_ok=True)
    ok = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1400, 'height': 900})
        page = ctx.new_page()
        page.goto(share_url, wait_until='domcontentloaded', timeout=60000)
        frame = None
        for _ in range(20):
            page.wait_for_timeout(1500)
            frame = find_modao_frame(page)
            if frame:
                n = frame.evaluate("document.querySelectorAll('a.sitemapPageLink').length")
                if n >= 5:
                    break
        if not frame:
            print('ERROR: 未找到原型 iframe')
            sys.exit(1)
        base = frame.url.rsplit('/', 1)[0]
        print('base:', base)

        for i, t in enumerate(pages, 1):
            t0 = time.time()
            try:
                remote = base + '/' + urllib.parse.quote(t['pageFile'])
                html = frame.evaluate(FETCH_HTML.format(url=json.dumps(remote)))
                refs = resource_refs(html)
                dl = skip = fail = 0
                for rel in refs:
                    rel = rel[2:] if rel.startswith('./') else rel
                    if rel in downloaded:
                        skip += 1
                        continue
                    try:
                        b64 = frame.evaluate(
                            FETCH_B64.format(u=json.dumps(base + '/' + urllib.parse.quote(rel))),
)
                        rp = out_dir + rel
                        os.makedirs(os.path.dirname(rp), exist_ok=True)
                        open(rp, 'wb').write(base64.b64decode(b64.split(',', 1)[1]))
                        downloaded.add(rel)
                        dl += 1
                    except Exception:
                        fail += 1
                open(out_dir + t['pageFile'], 'w', encoding='utf-8').write(html)
                ok += 1
                print(f"[{i}/{len(pages)}] OK {t['name']} | html {len(html)} | res +{dl}/skip{skip}/fail{fail} | {time.time()-t0:.1f}s")
            except Exception as e:
                print(f"[{i}/{len(pages)}] ERROR {t['name']}: {str(e)[:100]}")
        browser.close()
    print(f'EXPORT DONE: {ok}/{len(pages)}')


if __name__ == '__main__':
    import json, os, time, base64, urllib.parse
    main()
