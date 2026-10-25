# -*- coding: utf-8 -*-
"""浏览器：启动 Edge/Chrome（复用本地登录态）、登录检测、进入学习页、跳转单元"""
import os
import time
import json

from . import config, js
from .util import log

_ARGS = [
    '--start-maximized',
    '--disable-blink-features=AutomationControlled',
    '--no-first-run',
    '--no-default-browser-check',
]

INIT_SCRIPT = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"


def launch(pw, headless=False):
    """优先用系统 Edge，其次 Chrome，最后 Playwright 自带 Chromium"""
    os.makedirs(config.PROFILE_DIR, exist_ok=True)
    last = None
    for channel in ('msedge', 'chrome', None):
        try:
            ctx = pw.chromium.launch_persistent_context(
                config.PROFILE_DIR, headless=headless, channel=channel,
                args=_ARGS, viewport={'width': 1600, 'height': 950},
                locale='zh-CN')
            ctx.add_init_script(INIT_SCRIPT)
            log(f'浏览器已启动（{channel or "chromium"}）')
            return ctx
        except Exception as e:
            last = e
            log(f'启动 {channel or "chromium"} 失败：{str(e).splitlines()[0][:110]}')
    raise RuntimeError(f'没有可用的浏览器，请安装 Microsoft Edge 后重试。\n{last}')


def outline(page):
    """拉课程目录（含每个单元完成状态）"""
    try:
        return page.evaluate(js.OUTLINE, config.OUTLINE_API)
    except Exception as e:
        return {'_err': str(e)}


def is_ready(page):
    """能拿到目录 = 已登录且有权限"""
    d = outline(page)
    return bool(d and isinstance(d, dict) and d.get('result', {}).get('chapters'))


def ensure_login(page, minutes=12):
    """打开课程页并等用户登录，直到能读到课程目录"""
    log('正在打开课程页面…')
    try:
        page.goto(config.LEARN_URL, wait_until='domcontentloaded', timeout=90000)
    except Exception as e:
        log('打开超时，重试一次：', str(e)[:80])
        page.wait_for_timeout(3000)
        page.goto(config.LEARN_URL, wait_until='domcontentloaded', timeout=90000)
    page.wait_for_timeout(4000)
    if is_ready(page):
        log('已登录，课程数据读取成功')
        return True

    log('')
    log('*' * 72)
    log('  请在浏览器窗口里登录中国大学MOOC（扫码或账号密码都行）。')
    log('  登录成功后脚本会自动继续，不用关闭窗口、也不用回来点任何按钮。')
    log('  （如果提示“立即参加/加入课程”，说明还没选这门课，先点加入再等着）')
    log('*' * 72)
    deadline = time.time() + minutes * 60
    dots = 0
    joined_hint = False
    while time.time() < deadline:
        page.wait_for_timeout(3000)
        if is_ready(page):
            log('')
            log('登录成功，开始干活')
            return True
        dots += 1
        if dots % 5 == 0:
            try:
                body = page.evaluate("() => (document.body.innerText||'').slice(0,3000)")
            except Exception:
                body = ''
            if (not joined_hint) and ('立即参加' in body or '加入课程' in body):
                joined_hint = True
                log('')
                log('  >> 看起来这门课还没加入：请在页面上点「立即参加 / 加入课程」，'
                    '加入成功后脚本会自动继续。')
        if dots % 10 == 0:
            log(f'  仍在等待登录…（已等 {dots * 3} 秒）')
    log('等待登录超时，请重新运行')
    return False


def enter_content(page):
    """从课程首页点进「课件」，建立 SPA 上下文（直接 goto 课件页会被重定向）"""
    for _ in range(3):
        page.goto(config.LEARN_URL, wait_until='domcontentloaded', timeout=90000)
        page.wait_for_timeout(5000)
        if page.evaluate(js.CLICK_KJ):
            page.wait_for_timeout(8000)
            if '/content' in page.url:
                log('已进入课件页')
                return True
            page.wait_for_timeout(5000)
            if '/content' in page.url:
                log('已进入课件页')
                return True
        log('进入课件页失败，重试…')
        page.wait_for_timeout(3000)
    return False


def enter_assess(page):
    """进入「测验与作业」页"""
    for _ in range(3):
        page.goto(config.LEARN_URL, wait_until='domcontentloaded', timeout=90000)
        page.wait_for_timeout(5000)
        if page.evaluate(js.CLICK_ASSESS):
            page.wait_for_timeout(7000)
            if 'assessment' in page.url or page.query_selector('article.learn-assessment-card'):
                log('已进入测验与作业页')
                return True
        log('进入测验与作业页失败，重试…')
        page.wait_for_timeout(3000)
    return False


def push(page, path):
    """SPA 内部跳转（不刷新页面，快且稳）"""
    return page.evaluate(js.PUSH, path)


def unit_path(u):
    return (f"/mooc/learn/{config.KEY}/content/{u['lessonId']}"
            f"?tid={config.TERM}&unitId={u['id']}&chapterId={u['chapterId']}")


def units(page):
    """把目录拍平成单元列表"""
    d = outline(page)
    out = []
    for ch in d.get('result', {}).get('chapters', []):
        for ls in ch.get('lessons', []):
            for u in ls.get('units', []):
                out.append({
                    'id': u['id'], 'lessonId': ls['id'], 'chapterId': ch['id'],
                    'type': u.get('type'), 'name': u.get('name', ''),
                    'chapter': ch.get('name', ''), 'lesson': ls.get('name', ''),
                    'done': u.get('viewStatus') == 'completed',
                    'contentId': u.get('contentId'),
                })
    return out


def progress(page):
    us = units(page)
    stat = {}
    for t in ('video', 'pdf', 'discussion', 'quiz'):
        tot = [x for x in us if x['type'] == t]
        stat[t] = (sum(1 for x in tot if x['done']), len(tot))
    return stat, us
