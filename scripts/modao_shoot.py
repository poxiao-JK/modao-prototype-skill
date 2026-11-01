# -*- coding: utf-8 -*-
"""modao_shoot.py — 对离线HTML逐页读文字 + 内容包围盒截图（人眼所见基准）
用法: python modao_shoot.py <tree.json> <离线HTML目录> <输出目录> [--shots]
默认: 只处理离线文件存在的页面；无文字页强制截图（视觉兜底）；--shots 全部截图。
"""
import sys, json, os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright

BBOX_EXPR = """(() => {
  let minX = Infinity, minY = Infinity, maxX = 0, maxY = 0, count = 0;
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 3 || r.height < 3) continue;
    const isLeaf = el.children.length === 0;
    const hasImg = el.tagName === 'IMG';
    const hasText = isLeaf && (el.innerText || '').trim().length > 0;
    if (!(hasImg || hasText)) continue;
    count++;
    if (r.left < minX) minX = r.left;
    if (r.top < minY) minY = r.top;
    if (r.right > maxX) maxX = r.right;
    if (r.bottom > maxY) maxY = r.bottom;
  }
  if (!count) return JSON.stringify({empty: true});
  const pad = 16;
  return JSON.stringify({
    contentEls: count,
    x: Math.max(0, Math.floor(minX - pad)), y: Math.max(0, Math.floor(minY - pad)),
    w: Math.ceil(maxX - minX + pad * 2), h: Math.ceil(maxY - minY + pad * 2)
  });
})()"""


def process_page(ctx, t, off_dir, out_dir, idx, force_shots):
    dir_name = f"{idx:02d}_{t['name'].replace('/', '_')}"
    out_path = os.path.join(out_dir, dir_name)
    os.makedirs(out_path, exist_ok=True)
    meta_path = os.path.join(out_path, 'meta.json')
    meta = {'name': t['name'], 'dir': dir_name, 'pageFile': t['pageFile'], 'path': t['path']}
    t0 = time.time()
    try:
        page = ctx.new_page()
        page.goto(Path(off_dir, t['pageFile']).as_uri(), wait_until='load', timeout=30000)
        page.wait_for_timeout(600)
        info = page.evaluate("""(() => JSON.stringify({
          w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight,
          imgs: document.images.length, text: (document.body.innerText || '')
        }))()""")
        info = json.loads(info)
        meta['canvas'] = {'w': info['w'], 'h': info['h']}
        text = '\n'.join(l.rstrip() for l in info['text'].replace(' ', ' ').split('\n')).strip()
        meta['text'] = text
        meta['empty'] = not text
        need_shot = force_shots or meta['empty']
        if need_shot:
            bbox = json.loads(page.evaluate(BBOX_EXPR))
            if not bbox.get('empty'):
                meta['overview'] = {
                    'contentBox': f"{bbox['w']}x{bbox['h']}@{bbox['x']},{bbox['y']}",
                    'file': os.path.join(out_path, 'overview.png'),
                }
                page.screenshot(path=meta['overview']['file'],
                                clip={'x': bbox['x'], 'y': bbox['y'], 'width': bbox['w'], 'height': bbox['h']},
                                full_page=True)
        page.close()
        meta['updatedAt'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        kb = os.path.getsize(meta['overview']['file']) // 1024 if meta.get('overview') else 0
        print(f"[{idx}/{t.get('_total', '')}] OK {t['name']} | {meta['canvas']['w']}x{meta['canvas']['h']} imgs:{info['imgs']} | text {len(text)} | shot {kb}KB | {time.time()-t0:.1f}s")
        json.dump(meta, open(meta_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return meta
    except Exception as e:
        meta['error'] = str(e)[:120]
        print(f"[{idx}] ERROR {t['name']}: {meta['error']}")
        json.dump(meta, open(meta_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return meta


def main():
    args = sys.argv[1:]
    force_shots = '--shots' in args
    args = [a for a in args if a != '--shots']
    if len(args) < 3:
        print('用法: python modao_shoot.py <tree.json> <离线HTML目录> <输出目录> [--shots]')
        sys.exit(2)
    tree_path, off_dir, out_dir = args[0], args[1].replace('\\', '/').rstrip('/') + '/', args[2].replace('\\', '/').rstrip('/') + '/'
    tree = json.load(open(tree_path, encoding='utf-8'))
    pages = [t for t in tree if os.path.exists(Path(off_dir, t['pageFile']))]
    skipped = len(tree) - len(pages)
    print(f"处理 {len(pages)} 页（跳过未导出 {skipped} 页）")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1400, 'height': 900})
        results = []
        for i, t in enumerate(pages, 1):
            t['_total'] = len(pages)
            results.append(process_page(ctx, t, off_dir, out_dir, i, force_shots))
        browser.close()
    ok = sum(1 for r in results if 'error' not in r)
    empties = [r['name'] for r in results if r.get('empty')]
    json.dump({'capturedAt': time.strftime('%Y-%m-%dT%H:%M:%S'), 'pages': results,
               'note': 'overview.png=内容包围盒截图(人眼所见)；text=页面文字与标注；empty=true=无文字页(已自动截图兜底)；notExported 页未处理。'},
              open(os.path.join(out_dir, 'index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"SHOOT DONE: {ok}/{len(pages)} | 空白页: {empties or '无'}")


if __name__ == '__main__':
    import time
    main()
