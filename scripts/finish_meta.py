# -*- coding: utf-8 -*-
"""finish_meta.py — 对已下载的 offline 页面补齐文字 meta（纯本地，无在线步骤）
用法: python finish_meta.py <项目目录名>
"""
import sys, json, os, time
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
  return JSON.stringify({contentEls: count, x: Math.max(0, Math.floor(minX - pad)), y: Math.max(0, Math.floor(minY - pad)), w: Math.ceil(maxX - minX + pad * 2), h: Math.ceil(maxY - minY + pad * 2)});
})()"""


def clean_text(s):
    if not s:
        return ''
    return '\n'.join(l.rstrip() for l in s.split('\n')).strip()


def main():
    proj_name = sys.argv[1]
    home = os.environ.get('MODAO_PROTOTYPE_HOME', '').replace('\\', '/').rstrip('/')
    if not home:
        print('MODAO_PROTOTYPE_HOME 未设置')
        sys.exit(1)
    proj_dir = f'{home}/projects/{proj_name}'
    project = json.load(open(proj_dir + '/project.json', encoding='utf-8'))
    off = proj_dir + '/offline/'
    pages_dir = proj_dir + '/pages/'

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={'width': 1400, 'height': 900}).new_page()
        fixed = 0
        for pf, st in project['pages'].items():
            html_path = off + pf
            if not os.path.exists(html_path):
                continue
            meta_path = pages_dir + st.get('name', pf).replace('/', '_') + '.meta.json'
            need = (not os.path.exists(meta_path)) or (not (json.load(open(meta_path, encoding='utf-8')).get('text') or '').strip())
            if not need:
                continue
            page.goto(Path(html_path).as_uri(), wait_until='load', timeout=30000)
            page.wait_for_timeout(1200)
            info = json.loads(page.evaluate(
                'JSON.stringify({w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight, imgs: document.images.length, text: (document.body.innerText || "")})'))
            text = clean_text(info.get('text'))
            meta = {'name': st.get('name', pf), 'pageFile': pf, 'path': st.get('path', []),
                    'canvas': {'w': info['w'], 'h': info['h']}, 'imgs': info['imgs'],
                    'text': text, 'empty': not text, 'downloadedAt': time.strftime('%Y-%m-%dT%H:%M:%S')}
            json.dump(meta, open(meta_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            fixed += 1
            print(f"FIXED {st.get('name', pf)} | text {len(text)} | {info['w']}x{info['h']} imgs:{info['imgs']}")
        browser.close()
    print(f'FINISH META DONE: {fixed} fixed')


if __name__ == '__main__':
    main()
