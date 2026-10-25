# -*- coding: utf-8 -*-
"""MOOC 刷课助手 —— 主入口"""
import os
import sys
import argparse
import traceback

# ---- 让中文在 Windows 控制台不乱码 ----
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from moocbot import assess, browser, config, courseware, quizunit, report, util  # noqa: E402
from moocbot.util import log  # noqa: E402

BANNER = r"""
  __  __  ___   ___   ____         _   _      _                 
 |  \/  |/ _ \ / _ \ / ___|       | | | | ___| |_ __   ___ _ __ 
 | |\/| | | | | | | | |      _____| |_| |/ _ \ | '_ \ / _ \ '__|
 | |  | | |_| | |_| | |___  |_____|  _  |  __/ | |_) |  __/ |   
 |_|  |_|\___/ \___/ \____|       |_| |_|\___|_| .__/ \___|_|   
                                              |_|              
        数据结构与算法 · 课件 + 测验作业 自动完成工具
"""

MENU = """
请选择要做的任务（输入数字后回车）：

  1  一键全自动     课件（视频/文档/讨论/随堂测验）+ 测验作业   ← 推荐
  2  只刷课件       视频 + 文档 + 讨论 + 随堂测验
  3  只做测验作业   单元测验 / 在线练习 / 单元作业
  4  只看进度       不改动任何东西，只报告完成情况
  0  退出
"""


def ask_mode():
    print(MENU)
    while True:
        try:
            s = input('  请输入 1 / 2 / 3 / 4 / 0 ：').strip()
        except (EOFError, KeyboardInterrupt):
            return 'quit'
        if s in ('0', 'q', 'Q'):
            return 'quit'
        if s == '1':
            return 'all'
        if s == '2':
            return 'cw'
        if s == '3':
            return 'assess'
        if s == '4':
            return 'check'
        print('  输入无效，请重新输入')


def parse_args():
    ap = argparse.ArgumentParser(add_help=True, description='MOOC 刷课助手')
    ap.add_argument('mode', nargs='?', default=None,
                    choices=['all', 'cw', 'assess', 'check', 'quiz'],
                    help='all=全自动 cw=只刷课件 assess=只做测验作业 check=只看进度')
    ap.add_argument('--max', type=int, default=0, help='本次最多处理多少个课件单元')
    ap.add_argument('--no-redo', action='store_true', help='测验不重做提分（只做一次）')
    ap.add_argument('--force', action='store_true', help='题库覆盖率低也强制提交')
    ap.add_argument('--min-cov', type=float, default=0.5, help='提交所需最低题库覆盖率，默认 0.5')
    ap.add_argument('--dry', action='store_true', help='演练模式：只填写不提交')
    ap.add_argument('--headless', action='store_true', help='不显示浏览器窗口（不建议）')
    args = ap.parse_args()
    return args


def main():
    print(BANNER)
    args = parse_args()
    mode = args.mode or ask_mode()
    if mode == 'quit':
        print('  已退出')
        return 0

    logf = util.init_log(mode)
    log(f'运行模式：{mode}｜日志：{os.path.basename(logf)}')
    log(f'课程：{config.COURSE_NAME}（{config.KEY} / {config.TERM}）')
    for t in config.EXPIRED:
        log(f'  已过期、按约定跳过：{t}')

    from playwright.sync_api import sync_playwright

    results = {}
    code = 0
    try:
        with sync_playwright() as pw:
            log('')
            log('—— 第 1 步：启动浏览器（会弹出一个窗口，别关它）——')
            log(f'   登录态目录：{config.PROFILE_DIR}')
            ctx = browser.launch(pw, headless=args.headless)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            log('—— 第 2 步：检查登录状态 ——')
            try:
                if not browser.ensure_login(page):
                    log('未检测到登录状态，任务结束')
                    ctx.close()
                    return 2

                if mode in ('all', 'cw', 'quiz'):
                    if browser.enter_content(page):
                        if mode in ('all', 'cw'):
                            ok, fail = courseware.run(page, maxn=args.max)
                            log(f'课件完成：成功 {ok} 个，失败 {fail} 个')
                        if mode in ('all', 'cw', 'quiz'):
                            ok2, fail2 = quizunit.run(page, maxn=args.max)
                            log(f'随堂测验：成功 {ok2} 个，失败 {fail2} 个')
                    else:
                        log('!! 进入课件页失败，跳过课件部分')

                if mode in ('all', 'assess'):
                    results = assess.run(ctx, page, redo=not args.no_redo,
                                         min_cov=args.min_cov, dry=args.dry,
                                         force=args.force)

                report.summary(page, results)

                if args.headless or not sys.stdin.isatty():
                    ctx.close()
                else:
                    log('')
                    log('浏览器保持打开，方便你核对结果；按提示关闭即可。')
                    try:
                        input('  全部完成，按回车关闭浏览器…')
                    except (EOFError, KeyboardInterrupt):
                        pass
                    ctx.close()
            except Exception:
                log('!! 运行出错：')
                log(traceback.format_exc()[-1500:])
                try:
                    page.screenshot(path=os.path.join(config.LOG_DIR, 'fatal.png'))
                except Exception:
                    pass
                code = 1
                try:
                    ctx.close()
                except Exception:
                    pass
    except Exception as e:
        log('!! 启动失败：', str(e)[:400])
        log('   如果提示缺少 playwright，请运行「一键开始.bat」自动安装。')
        code = 3
    return code


if __name__ == '__main__':
    sys.exit(main())
