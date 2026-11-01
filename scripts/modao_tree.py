# -*- coding: utf-8 -*-
"""modao_tree.py — 读取墨刀原型页面树（含分组层级）
用法: python modao_tree.py <墨刀分享链接> <输出tree.json>
产出: tree.json = [{name, pageFile, path, rootBranch, rootFile}]
"""
import sys, json
from playwright.sync_api import sync_playwright

TREE_EXPR = """(() => {
  const out = [];
  for (const a of document.querySelectorAll('a.sitemapPageLink')) {
    const name = (a.querySelector('.sitemapPageName')?.textContent || '').trim();
    const nodeurl = a.getAttribute('nodeurl') || '';
    if (!name || !nodeurl) continue;
    const path = [];
    let ul = a.closest('ul');
    let guard = 0;
    let rootFile = nodeurl;
    while (ul && guard++ < 8) {
      const pli = ul.closest('li');
      if (!pli) break;
      const pa = pli.querySelector('a.sitemapPageLink');
      if (pa && pa !== a) {
        const pn = (pa.querySelector('.sitemapPageName')?.textContent || '').trim();
        if (pn) path.unshift(pn);
        rootFile = pa.getAttribute('nodeurl') || rootFile;
      }
      ul = pli.parentElement ? pli.parentElement.closest('ul') : null;
    }
    out.push({ name, pageFile: nodeurl, path, rootBranch: path[0] || name, rootFile });
  }
  const seen = new Set();
  const uniq = [];
  for (const it of out) {
    const k = it.name + '|' + it.pageFile;
    if (!seen.has(k)) { seen.add(k); uniq.push(it); }
  }
  return JSON.stringify(uniq);
})()"""


def find_modao_frame(page):
    for f in page.frames:
        if 'modao.ink' in f.url:
            return f
    return None


def fetch_tree(share_url, browser):
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
        raise RuntimeError('未找到原型 iframe（确认链接为公开分享链接且网络可用）')
    tree = json.loads(frame.evaluate(TREE_EXPR))
    ctx.close()
    return tree


def main():
    if len(sys.argv) < 3:
        print('用法: python modao_tree.py <墨刀分享链接> <输出tree.json>')
        sys.exit(2)
    share_url, out_path = sys.argv[1], sys.argv[2]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            tree = fetch_tree(share_url, browser)
        finally:
            browser.close()
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(tree, f, ensure_ascii=False, indent=1)
    print(f'TREE DONE: {len(tree)} pages -> {out_path}')
    for t in tree:
        print('  ' + (' > '.join(t['path']) + ' > ' if t['path'] else '') + t['name'], f"[{t['pageFile']}]")


if __name__ == '__main__':
    import json
    main()
