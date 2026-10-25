# -*- coding: utf-8 -*-
"""进度汇总 / 结果报告"""
import os
import time

from . import browser, config
from .util import log, human_left

CN = {'video': '视频', 'pdf': '文档', 'discussion': '讨论', 'quiz': '随堂测验'}


def summary(page, results=None, write_file=True):
    try:
        stat, us = browser.progress(page)
    except Exception as e:
        log('读取进度失败：', str(e)[:100])
        return
    log('')
    log('=' * 72)
    log('  当前学习进度')
    log('=' * 72)
    total_done = total_all = 0
    for t in ('video', 'pdf', 'discussion', 'quiz'):
        a, b = stat.get(t, (0, 0))
        total_done += a
        total_all += b
        bar = '完整' if b and a >= b else '待补'
        log(f'  {CN[t]:<6} {a:>3}/{b:<3}  {bar}')
    log(f'  合计     {total_done:>3}/{total_all:<3}')
    left = [x for x in us if not x['done'] and x['type'] != 'quiz']
    if left:
        log('  未完成：')
        for x in left[:15]:
            log(f"    - [{CN.get(x['type'], x['type'])}] {(x['name'] or x['lesson'])[:34]}")
        if len(left) > 15:
            log(f'    …… 还有 {len(left) - 15} 个')

    if results:
        log('')
        log('  测验与作业处理结果')
        for k, v in results.items():
            log(f'    {k:<10} {v}')

    if write_file:
        p = os.path.join(config.REPORT_DIR, f'刷课报告_{time.strftime("%Y%m%d_%H%M")}.txt')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(f'{config.COURSE_NAME} 刷课报告  {time.strftime("%Y-%m-%d %H:%M")}\n')
            f.write('-' * 60 + '\n')
            for t in ('video', 'pdf', 'discussion', 'quiz'):
                a, b = stat.get(t, (0, 0))
                f.write(f'{CN[t]}: {a}/{b}\n')
            if left:
                f.write('\n未完成：\n')
                for x in left:
                    f.write(f"  [{CN.get(x['type'], x['type'])}] {x['name'] or x['lesson']}\n")
            if results:
                f.write('\n测验与作业：\n')
                for k, v in results.items():
                    f.write(f'  {k}: {v}\n')
            f.write('\n注：课程总成绩要等学期结束、作业互评完成后才公布，'
                    '本报告只反映课件学习与提交状态。\n')
        log(f'  报告已保存：{p}')
    return stat
