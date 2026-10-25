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
    if os.path.exists(os.path.join(config.PROFILE_DIR, 'SingletonLock')):
        log('提示：登录态目录里还有锁文件，可能是上次浏览器没关干净。')
        log('      如果下面启动失败，把残留的 Edge 窗口全部关掉再跑。')
    last = None
    for channel in ('msedge', 'chrome', None):
        name = channel or 'chromium'
        log(f'正在启动浏览器（{name}），最多等 30 秒…')
        try:
            ctx = pw.chromium.launch_persistent_context(
                config.PROFILE_DIR, headless=headless, channel=channel,
                args=_ARGS, viewport={'width': 1600, 'height': 950},
                locale='zh-CN', timeout=30000)
            ctx.add_init_script(INIT_SCRIPT)
            log(f'浏览器窗口已打开（{name}）')
            return ctx
        except Exception as e:
            last = e
            log(f'  {name} 启动失败：{str(e).splitlines()[0][:110]}')
    raise RuntimeError(
        '一个浏览器都启动不起来。请按顺序试：\n'
        '  1) 关掉所有 Edge 窗口（含后台残留），再运行一次\n'
        f'  2) 删掉登录态目录后重试：{config.PROFILE_DIR}\n'
        '  3) 确认电脑上有 Microsoft Edge 或 Chrome\n'
        f'最后一次错误：{last}')


def outline(page):
    """拉课程目录（含每个单元完成状态）"""
    try:
        return page.evaluate(js.OUTLINE, config.OUTLINE_API)
    except Exception as e:
        return {'_err': str(e)}


def is_ready(page, absolute=False):
    """能拿到目录 = 有权限访问这门课（注意：未登录也可能返回目录，不能用来判断登录）"""
    api = config.OUTLINE_ABS if absolute else config.OUTLINE_API
    try:
        d = page.evaluate(js.OUTLINE, api)
    except Exception:
        return False
    return bool(d and isinstance(d, dict) and d.get('result', {}).get('chapters'))


# 登录后才会写入的 cookie（注意域名是 .icourse163.com / .icourse163.cn，不是 .org）
LOGIN_COOKIES = ('STUDY_SESS', 'STUDY_INFO')
COURSE_DOMAINS = ('icourse163.org', 'icourse163.com', 'icourse163.cn')


def has_login_cookie(page):
    """只看 cookie，不碰页面 —— 等待登录时完全不会干扰用户操作"""
    try:
        cks = page.context.cookies()
    except Exception:
        return False
    for c in cks:
        if c.get('name') in LOGIN_COOKIES:
            d = c.get('domain') or ''
            if any(k in d for k in COURSE_DOMAINS):
                return True
    return False


def _landed_learn(page):
    """真正进入学习页 = 已登录且已选修（未登录会被重定向到 /course/ 公开页）"""
    u = page.url
    return '/learn/' in u and '/course/' not in u


def _login_ok(page):
    """登录判定的组合规则，尽量不误判"""
    if _landed_learn(page):
        return True
    if '/course/' in page.url:      # 被送去公开课程页 = 没登录或没选课
        return False
    return has_login_cookie(page) and is_ready(page)


def _kbhit():
    if os.name != 'nt':
        return False
    try:
        import msvcrt
        return msvcrt.kbhit()
    except Exception:
        return False


def _drain_key():
    """吃掉一个按键；回车只产生一个字符，不能盲读两次（会卡住等输入）"""
    try:
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ('\x00', '\xe0'):      # 方向键等功能键的第二字节
            msvcrt.getwch()
    except Exception:
        pass


def _goto(page, url, tries=2, wait='domcontentloaded', timeout=90000):
    for i in range(tries):
        try:
            page.goto(url, wait_until=wait, timeout=timeout)
            return True
        except Exception as e:
            if i == tries - 1:
                log('打开页面失败：', str(e).splitlines()[0][:100])
            else:
                page.wait_for_timeout(2500)
    return False


def ensure_login(page, minutes=15):
    """确认登录状态。

    这里踩过三个坑，都在这修掉了：
      1. 未登录访问 /learn/ 会被重定向到「公开课程页」，那页的 hash 路由会连跳
         好几次，看起来像网页一直在刷新，而且那页没有登录入口 —— 未知登录态时
         改为停在登录页等，等待期间不导航。
      2. 课程目录接口**不登录也返回章节**，不能当登录判据。
      3. 光有登录 cookie 也不够（会话可能已过期，只能看到未完成的目录）——
         最终以「能不能进 /learn/ 学习页」为准。
    """
    log('正在检查登录状态…')
    log('正在打开课程页（最多等 90 秒）…')
    if _goto(page, config.LEARN_URL):
        page.wait_for_timeout(2500)
        if _landed_learn(page):
            log('已登录，开始干活')
            return True

    had_cookie = has_login_cookie(page)
    if had_cookie:
        # 有登录记录但进不了学习页：多半是没选修，或者会话过期
        log('')
        log('=' * 74)
        log('  检测到登录记录，但没能进入学习页。请二选一：')
        log('    · 还没加入这门课  → 在页面上点「立即参加 / 加入课程」')
        log('    · 登录已经过期    → 点右上角「登录」重新登一次')
        log('  弄好之后按一下【回车】，我马上重新检查（也可以什么都不按，我会自动轮询）')
        log('=' * 74)
        log('')
    else:
        # 完全没登录：停在登录页等，不刷新不跳转
        if not _goto(page, config.LOGIN_URL):
            log('!! 打不开登录页，请检查网络后重试')
            return False
        page.wait_for_timeout(3000)
        log('')
        log('=' * 74)
        log('  请在这个浏览器窗口里登录中国大学 MOOC')
        log('  · 页面已停在【登录页】，不会再自动刷新，慢慢扫码或输密码都行')
        log('  · 登录成功后脚本会自动继续，不用关窗口、不用回来点按钮')
        log('=' * 74)
        log('')

    deadline = time.time() + minutes * 60
    waited = 0
    while time.time() < deadline:
        page.wait_for_timeout(2000)
        waited += 2

        if _landed_learn(page):
            log('登录成功，开始干活')
            return True

        # 新登录：cookie 刚出现 → 只主动跳一次学习页
        if (not had_cookie) and has_login_cookie(page):
            had_cookie = True
            log('检测到登录成功，正在打开课程…')
            _goto(page, config.LEARN_URL)
            page.wait_for_timeout(3000)
            if _landed_learn(page):
                log('课程数据读取成功，开始干活')
                return True
            log('')
            log('  已登录，但没进到学习页。如果显示「立即参加」，请点它加入课程；')
            log('  加入后按一下【回车】我再检查一次。')
            log('')

        # 用户按回车 → 立刻再检查一次
        if _kbhit():
            _drain_key()
            log('收到回车，重新检查…')
            _goto(page, config.LEARN_URL)
            page.wait_for_timeout(2500)
            if _landed_learn(page):
                log('课程数据读取成功，开始干活')
                return True
            if not has_login_cookie(page):
                log('  还是没登录上，请再登一次，或按回车重试。')
            else:
                log('  还是进不去学习页，检查一下这门课是否已经「加入课程」。')

        if waited % 6 == 0:
            left = max(int((deadline - time.time()) // 60), 0)
            mm, ss = divmod(waited, 60)
            tip = '等待你登录' if not had_cookie else '等待你加入课程 / 重新登录'
            log(f'  ⏳ {tip}…  已等 {mm:02d}:{ss:02d}，还剩 {left} 分钟'
                f'（在浏览器里操作，好了我会自动继续）')
            if waited == 30 and not has_login_cookie(page):
                log('     看不到登录页内容的话，点一下浏览器的刷新按钮；'
                    '或者换手机热点再试。')

    log('等待超时。可以重新运行 —— 登录态会记住，不用重复登录。')
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
