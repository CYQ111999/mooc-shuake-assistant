# -*- coding: utf-8 -*-
"""课件：视频秒过 / PDF 翻页 / 讨论区回帖"""
import os
import re
import time

from . import browser, config, js
from .util import log


def _reenter(page):
    if browser.enter_content(page):
        return True
    log('!! 重新进入课件页失败')
    return False


def _goto(page, u, tag):
    r = browser.push(page, browser.unit_path(u))
    page.wait_for_timeout(1800)
    if u['id'] not in page.url:
        if not _reenter(page):
            return False
        r = browser.push(page, browser.unit_path(u))
        page.wait_for_timeout(2000)
    if u['id'] not in page.url:
        log(tag, '!! 跳转未命中：', page.url[:90])
        return False
    return True


def do_video(page, u, tag):
    try:
        page.wait_for_selector('video', timeout=25000)
    except Exception:
        log(tag, '!! 视频元素未出现')
        return False
    page.wait_for_timeout(1600)
    r = page.evaluate(js.VIDEO_SEEK)
    if r == 'no-duration':
        page.wait_for_timeout(3000)
        r = page.evaluate(js.VIDEO_SEEK)
    for k in range(16):
        page.wait_for_timeout(750)
        st = page.evaluate(js.VIDEO_STATE)
        if st is None:
            return True
        if st['ended'] or (st['dur'] and st['cur'] >= st['dur'] - 0.4):
            log(tag, f"视频完成 {st['cur']}/{st['dur']}s")
            break
        if st['paused']:
            p = page.evaluate(js.POPUP)
            if p != 'none':
                log(tag, '弹窗:', p)
            page.evaluate(js.VIDEO_SEEK)
    page.wait_for_timeout(1500)
    return True


def do_pdf(page, u, tag):
    try:
        page.wait_for_selector('.mooc-docs-reader', timeout=20000)
    except Exception:
        log(tag, '!! 阅读器未出现')
        return False
    page.wait_for_timeout(1400)
    info = page.evaluate(js.PDF_INFO)
    if not info or not info.get('nThumbs'):
        log(tag, 'PDF 无可翻页缩略图，直接跳过（可能已翻完）')
        return True
    r = page.evaluate(js.PDF_TURN)
    log(tag, f"PDF {info.get('nThumbs')} 页 → {r}")
    page.wait_for_timeout(1400)
    return True


def _pick_reply(replies):
    cand = sorted([r for r in replies if 30 <= len(r) <= 600], key=len)
    if not cand:
        cand = replies
    text = cand[len(cand) // 2]
    return re.sub(r'\n{2,}', '\n', text).strip()


def do_discussion(page, u, tag, net):
    page.wait_for_timeout(4000)
    replies = page.evaluate(js.GET_REPLIES)
    if replies:
        text = _pick_reply(replies)
        src = '评论区'
    else:
        pool = config.load('discussions.json')['pool']
        text = pool[int(u['id']) % len(pool)]
        src = '内置话术'
    if len(text) < 20:
        log(tag, '!! 没有可用回复内容')
        return False
    log(tag, f'取{src}({len(text)}字): {text[:46].replace(chr(10), " ")}…')

    ed = page.locator('.ql-editor:visible').first
    try:
        ed.scroll_into_view_if_needed(timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(400)
    ed.click()
    page.wait_for_timeout(500)
    page.keyboard.press('Control+A')
    page.keyboard.press('Delete')
    page.wait_for_timeout(200)
    page.keyboard.insert_text(text)
    page.wait_for_timeout(1000)

    net.clear()
    clicked = False
    try:
        loc = page.get_by_role('button', name='发表回复').first
        loc.scroll_into_view_if_needed(timeout=6000)
        page.wait_for_timeout(300)
        loc.click(timeout=8000)
        clicked = True
    except Exception:
        try:
            page.evaluate("""() => { const b=[...document.querySelectorAll('button')]
                .find(e => (e.innerText||'').trim() === '发表回复'); if (b) b.click(); }""")
            clicked = True
        except Exception:
            pass
    page.wait_for_timeout(4500)

    st = page.evaluate(js.EDITORS)
    status = net[-1][1] if net else None
    if status == 409:
        log(tag, '>> 今日回帖数已达上限（平台限制），剩余讨论留到明天再跑一次即可')
        return 'limit'
    ok = status == 200 or st.get('blank')
    log(tag, f'回帖 clicked={clicked} http={status} 编辑器清空={bool(st.get("blank"))} → {"成功" if ok else "未确认"}')
    page.wait_for_timeout(700)
    return True if ok else False


def run(page, types=('video', 'pdf', 'discussion'), maxn=0, progress_cb=None):
    """按类型分批处理未完成的课件单元"""
    net = []

    def on_resp(r):
        try:
            if 'forum/write' in r.url and r.request.method == 'POST':
                net.append(('write', r.status))
        except Exception:
            pass

    page.on('response', on_resp)

    _, us = browser.progress(page)
    stat0 = {t: (sum(1 for x in us if x['type'] == t and x['done']),
                sum(1 for x in us if x['type'] == t)) for t in ('video', 'pdf', 'discussion', 'quiz')}
    log('当前课件进度：' + ' | '.join(f'{t} {a}/{b}' for t, (a, b) in stat0.items()))

    ok = fail = 0
    total = 0
    limit_hit = False
    for t in types:
        todo = [u for u in us if u['type'] == t and not u['done']]
        if t == 'discussion' and limit_hit:
            log('今日回帖额度已满，跳过剩余讨论')
            continue
        if not todo:
            log(f'{t}: 无需处理')
            continue
        log('')
        log(f'—— {t}：待处理 {len(todo)} 个 ——')
        for i, u in enumerate(todo):
            if maxn and total >= maxn:
                log(f'已达到本次上限 {maxn} 个，停止')
                return ok, fail
            total += 1
            tag = f'[{i + 1}/{len(todo)}]'
            label = (u['name'] or u['lesson'])[:34]
            log(f'{tag} {label}')
            t0 = time.time()
            try:
                if not _goto(page, u, tag):
                    fail += 1
                    continue
                if t == 'video':
                    ok += 1 if do_video(page, u, tag) else 0
                elif t == 'pdf':
                    ok += 1 if do_pdf(page, u, tag) else 0
                else:
                    r = do_discussion(page, u, tag, net)
                    if r == 'limit':
                        limit_hit = True
                        break
                    ok += 1 if r else 0
            except Exception as e:
                fail += 1
                log(tag, '!! 异常：', str(e).splitlines()[0][:150])
                page.screenshot(path=os.path.join(config.LOG_DIR, 'cw_err.png'))
                _reenter(page)
            log(f'{tag} 用时 {time.time() - t0:.1f}s')

    if limit_hit:
        log('提示：讨论区有每日回帖上限，隔天再运行一次即可自动补齐。')
    return ok, fail
