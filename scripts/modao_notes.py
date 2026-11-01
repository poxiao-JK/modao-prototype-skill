# -*- coding: utf-8 -*-
"""modao_notes.py — 提取墨刀原型的批注（设计/产品贴在原型上的便签说明）
用法: python modao_notes.py <墨刀分享链接> <tree.json> <输出notes.json>
机制: 页面清单取自原型 iframe 的 Axure sitemap（稳定）；逐页切换用
      scrollIntoView + 外层坐标点击（真实鼠标事件，已验证）；批注元素
      .wSticky 在主文档与各 frame 均查找（第一行=编号，其余=内容）。
说明: 批注提取必须在线逐页进行（批注不在离线HTML里），是流程中最慢的一步。
"""
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright

NOTES_EXPR = """(() => {
  const pick = doc => {
    if (!doc || !doc.querySelectorAll) return [];
    return [...doc.querySelectorAll('.wSticky')].map((el, i) => {
      const lines = (el.innerText || '').split('\\n').filter(l => l.trim());
      return { number: (lines[0] || String(i + 1)).trim(), content: lines.slice(1).join('\\n').trim() };
    }).filter(a => a.content);
  };
  const out = [...pick(document)];
  for (let fi = 0; fi < window.frames.length; fi++) {
    try { out.push(...pick(window.frames[fi].document)); } catch {}
  }
  return JSON.stringify(out);
})()"""

TREE_EXPR = """(() => {
  const out = [];
  for (const a of document.querySelectorAll('a.sitemapPageLink')) {
    const name = (a.querySelector('.sitemapPageName')?.textContent || '').trim();
    if (!name) continue;
    a.scrollIntoView({block: 'center'});
    const r = a.getBoundingClientRect();
    out.push({name, x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2)});
  }
  const seen = new Set();
  return JSON.stringify(out.filter(n => !seen.has(n.name) && seen.add(n.name)));
})()"""


def find_modao_frame(page):
    for f in page.frames:
        if 'modao.ink' in f.url:
            return f
    return None


def main():
    if len(sys.argv) < 4:
        print('用法: python modao_notes.py <墨刀分享链接> <tree.json> <输出notes.json>')
        sys.exit(2)
    share_url, tree_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    tree = json.load(open(tree_path, encoding='utf-8'))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1600, 'height': 1000})
        page = ctx.new_page()
        page.goto(share_url, wait_until='domcontentloaded', timeout=60000)

        # 等原型 iframe + sitemap 就绪（Axure 树在 iframe 文档里，稳定）
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

        # 页面清单：iframe 文档（去重，保持顺序）
        nodes = json.loads(frame.evaluate(TREE_EXPR))
        uniq = []
        seen = set()
        for n in nodes:
            if n['name'] not in seen:
                seen.add(n['name'])
                uniq.append(n)
        print(f'页面数: {len(uniq)}')

        # iframe 在外层页面中的偏移（用于把 frame 内坐标换算成外层鼠标坐标）
        offset = page.evaluate("""(() => {
          for (const f of document.querySelectorAll('iframe')) {
            if ((f.src || '').includes('modao.ink')) {
              const r = f.getBoundingClientRect();
              return JSON.stringify({left: r.left, top: r.top});
            }
          }
          return JSON.stringify({left: 0, top: 0});
        })()""")
        off = json.loads(offset)
        print('iframe offset:', off)

        results = []
        for i, n in enumerate(uniq, 1):
            t0 = time.time()
            # scrollIntoView + 真实鼠标点击（frame 内坐标 -> 外层坐标）
            frame.evaluate("""(() => {
              const a = [...document.querySelectorAll('a.sitemapPageLink')].find(x => (x.querySelector('.sitemapPageName')?.textContent || '').trim() === ${});
              if (a) a.scrollIntoView({block: 'center'});
            })()""".replace('${}', json.dumps(n['name'])))
            page.wait_for_timeout(400)
            rect = frame.evaluate("""(() => {
              const a = [...document.querySelectorAll('a.sitemapPageLink')].find(x => (x.querySelector('.sitemapPageName')?.textContent || '').trim() === ${});
              if (!a) return 'null';
              const r = a.getBoundingClientRect();
              return JSON.stringify({x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2)});
            })()""".replace('${}', json.dumps(n['name'])))
            pt = json.loads(rect)
            px, py = off['left'] + pt['x'], off['top'] + pt['y']
            page.mouse.move(px, py)
            page.mouse.down()
            page.mouse.up()
            page.wait_for_timeout(3500)

            # 验证切页 + 提取批注
            cur = frame.evaluate("(() => { const cd = document.querySelector('iframe'); return cd && cd.contentDocument ? cd.contentDocument.title : ''; })()")
            ann = json.loads(frame.evaluate(NOTES_EXPR))
            results.append({'name': n['name'], 'switched': cur == n['name'], 'annotations': ann})
            mark = 'SWITCHED' if cur == n['name'] else 'NOT-SWITCHED'
            print(f"[{i}/{len(uniq)}] {n['name']} | {mark} | notes:{len(ann)} | {time.time()-t0:.1f}s")

        browser.close()

    json.dump(results, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    total = sum(len(r['annotations']) for r in results)
    print(f'NOTES DONE: {len(results)} pages, {total} annotations -> {out_path}')


if __name__ == '__main__':
    import time
    main()
