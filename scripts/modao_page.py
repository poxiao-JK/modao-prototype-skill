# -*- coding: utf-8 -*-
"""modao_page.py — 按需下载单个页面：离线HTML+资源+文字（已存在则秒回）
用法:
  python modao_page.py <项目目录名|项目目录路径> "<页面名>" [--shots] [--refresh] [cdp端口]
产出: <项目>/offline/{页面文件}+资源、<项目>/pages/{页面名}.meta.json、catalog.md 自动刷新
"""
import sys, json, os, time, base64
from urllib.parse import quote
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modao_export import find_modao_frame, resource_refs
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


def modao_home():
    h = os.environ.get('MODAO_PROTOTYPE_HOME', '')
    if not h:
        print('环境变量 MODAO_PROTOTYPE_HOME 未设置：请指定原型档案存放目录（setx MODAO_PROTOTYPE_HOME "<目录>"）')
        sys.exit(1)
    return h.replace('\\', '/').rstrip('/')


def clean_text(s):
    if not s:
        return ''
    return '\n'.join(l.rstrip() for l in s.split('\n')).strip()


def main():
    args = [a for a in sys.argv[1:] if a not in ('--shots', '--refresh')]
    with_shots = '--shots' in sys.argv
    refresh = '--refresh' in sys.argv
    port = 9222
    if args and args[-1].isdigit():
        port = int(args[-1]); args = args[:-1]
    if len(args) < 2:
        print('用法: python modao_page.py <项目目录名|项目目录路径> "<页面名>" [--shots] [--refresh] [cdp端口]')
        sys.exit(2)
    home = modao_home()
    arg0 = args[0].replace('\\', '/')
    proj_dir = (arg0 if '/' in arg0 else home + '/projects/' + arg0).rstrip('/') + '/'
    page_query = args[1]
    proj_path = proj_dir + 'project.json'
    if not os.path.exists(proj_path):
        print('项目不存在（先运行 modao_init.mjs）:', proj_dir)
        sys.exit(1)
    project = json.load(open(proj_path, encoding='utf-8'))
    share_url = project['shareUrl']

    entry = None
    page_file = None
    for pf, st in project.get('pages', {}).items():
        if st.get('name') == page_query or pf == page_query or pf == page_query + '.html':
            entry = {'name': st.get('name', page_query), 'path': st.get('path', [])}
            page_file = pf
            break
    if not entry:
        print('页面不存在。已登记页面：')
        for pf, st in project.get('pages', {}).items():
            print(' -', st.get('name', pf), f'({pf})')
        sys.exit(1)

    meta_name = entry['name'].replace('/', '_') + '.meta.json'
    meta_path = proj_dir + 'pages/' + meta_name
    offline_path = proj_dir + 'offline/' + page_file

    if not refresh and os.path.exists(meta_path) and os.path.exists(offline_path):
        meta = json.load(open(meta_path, encoding='utf-8'))
        print('ALREADY CACHED（--refresh 强制刷新）')
        print('meta:', meta_path)
        print('offline:', offline_path)
        print('text len:', len(meta.get('text') or ''), '| empty:', meta.get('empty'))
        sys.exit(0)

    downloaded = set()
    off_dir = proj_dir + 'offline/'
    if os.path.isdir(off_dir):
        for root, _, files in os.walk(off_dir):
            for f in files:
                downloaded.add(os.path.relpath(os.path.join(root, f), off_dir).replace('\\', '/'))

    t0 = time.time()
    html = ''
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

        remote = base + '/' + quote(page_file)
        html = frame.evaluate(
            "fetch(" + json.dumps(remote) + ").then(r => { if (!r.ok) throw new Error('HTTP'+r.status); return r.text(); })")
        print(f"html: {len(html)}B")

        dl = fail = 0
        for rel in resource_refs(html):
            rel2 = rel[2:] if rel.startswith('./') else rel
            if rel2 in downloaded:
                continue
            try:
                b64 = frame.evaluate(
                    "fetch(" + json.dumps(base + '/' + urllib.parse.quote(rel2)) + ").then(r => { if (!r.ok) throw new Error('HTTP'+r.status); return r.blob(); }).then(b => new Promise(res => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr.readAsDataURL(b); }))")
                rp = off_dir + rel2
                os.makedirs(os.path.dirname(rp), exist_ok=True)
                open(rp, 'wb').write(base64.b64decode(b64.split(',', 1)[1]))
                downloaded.add(rel2); dl += 1
            except Exception:
                fail += 1
        print(f"resources: +{dl} fail{fail}")
        browser.close()

    # 写盘 + 验证
    os.makedirs(os.path.dirname(offline_path), exist_ok=True)
    open(offline_path, 'w', encoding='utf-8').write(html)
    for _ in range(5):
        if os.path.getsize(offline_path) > 0:
            break
        time.sleep(0.3)
    print(f"offline saved: {offline_path} ({os.path.getsize(offline_path)}B)")

    # 本地渲染读文字（空结果自动重试）
    local_url = 'file:///' + quote(offline_path.replace('\\', '/'))
    meta = None
    for attempt in range(3):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context(viewport={'width': 1400, 'height': 900}).new_page()
            page.goto(local_url, wait_until='load', timeout=30000)
            page.wait_for_timeout(1000 if attempt == 0 else 2000)
            info = json.loads(page.evaluate(
                'JSON.stringify({w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight, imgs: document.images.length, text: (document.body.innerText || "")})'))
            text = clean_text(info.get('text'))
            meta = {'name': entry['name'], 'pageFile': page_file, 'path': entry['path'],
                    'canvas': {'w': info['w'], 'h': info['h']}, 'imgs': info['imgs'],
                    'text': text, 'empty': not text,
                    'downloadedAt': time.strftime('%Y-%m-%dT%H:%M:%S')}
            if text:
                break
            print(f'  渲染结果为空，重试 {attempt + 1}/2...')
            browser.close()

    json.dump(meta, open(meta_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # 截图规则：--shots 全截；无文字页（纯图片/空白）自动兜底截图
    if with_shots or meta['empty'] or (meta.get('imgs', 0) > 0 and not meta['text']):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context(viewport={'width': 1400, 'height': 900}).new_page()
            page.goto(local_url, wait_until='load', timeout=30000)
            page.wait_for_timeout(1500)
            bbox = json.loads(page.evaluate(BBOX_EXPR))
            if not bbox.get('empty'):
                shots_dir = proj_dir + 'shots/'
                os.makedirs(shots_dir, exist_ok=True)
                shot_path = shots_dir + meta_name.replace('.meta.json', '.png')
                page.screenshot(path=shot_path,
                                clip={'x': bbox['x'], 'y': bbox['y'], 'width': bbox['w'], 'height': bbox['h']},
                                full_page=True)
                meta['shot'] = shot_path
                json.dump(meta, open(meta_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                print('shot saved:', shot_path)
            else:
                print('页面无有效内容（空白占位页），跳过截图')
            browser.close()

    # 状态 + catalog 刷新
    pageInfo = project['pages'].get(page_file) or {}
    pageInfo.update({'downloaded': True, 'empty': meta['empty'], 'textLen': len(meta['text']),
                     'updatedAt': time.strftime('%Y-%m-%dT%H:%M:%S')})
    project['pages'][page_file] = pageInfo
    project['updatedAt'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    json.dump(project, open(proj_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    from modao_catalog import buildCatalog
    buildCatalog(project, proj_dir)
    print(f"catalog refreshed: {sum(1 for v in project['pages'].values() if v.get('downloaded'))}/{len(project['tree'])}")

    print('PAGE DONE | text len:', len(meta['text']), '| empty:', meta['empty'], f'| {time.time()-t0:.1f}s')
    sys.exit(0)


if __name__ == '__main__':
    main()
