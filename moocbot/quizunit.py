# -*- coding: utf-8 -*-
"""课件里的随堂测验：按题库勾选 → 提交 → 若错自动用「正确答案」纠正再答一次"""
import os
import time

from . import browser, config, js
from .util import log, norm, similar

QUIZ = {x['uid']: x for x in config.load('quiz_units.json')}


def _enter_unit(page, u, tag):
    browser.push(page, browser.unit_path(u))
    page.wait_for_timeout(4200)
    for _ in range(2):
        if page.evaluate(js.CLOSE_EVAL) == 'cancel':
            page.wait_for_timeout(800)
    if u['id'] not in page.url:
        return False
    # 已提交过的，点「重新答题」回到可作答状态
    for _ in range(2):
        if page.evaluate(js.HAS_SUBMIT):
            return True
        if page.evaluate(js.REDO) == 'clicked':
            page.wait_for_timeout(2200)
            for _ in range(10):
                if page.evaluate(js.HAS_SUBMIT):
                    return True
                page.wait_for_timeout(600)
        else:
            break
    return page.evaluate(js.HAS_SUBMIT)


def _target_indices(page, q, tag):
    """根据题库算出应该勾选哪些 radio（全局序号）"""
    radios = page.evaluate(js.RADIOS)
    need = sum(len(x['opts']) for x in q['questions'])
    if len(radios) != need:
        log(tag, f'  !! 选项数不符 页面{len(radios)} / 题库{need}，跳过（不提交，保护成绩）')
        return None
    out, acc = [], 0
    for k, item in enumerate(q['questions']):
        seg = radios[acc:acc + len(item['opts'])]
        want = norm(item['ans'])
        hit = None
        for j, r in enumerate(seg):
            if norm(r['text']) == want:
                hit = j
                break
        if hit is None:
            for j, r in enumerate(seg):
                if want and (want in norm(r['text']) or norm(r['text']) in want) and len(norm(r['text'])) > 1:
                    hit = j
                    break
        if hit is None:
            # 按题库里答案原本的位置兜底
            try:
                hit = [norm(o) for o in item['opts']].index(want)
            except ValueError:
                hit = 0
            log(tag, f'  第{k + 1}题选项文本未命中，按原位置用 {hit} 号')
        out.append(acc + hit)
        acc += len(item['opts'])
    return out


def _tick(page, gidx):
    for gi in gidx:
        page.evaluate(js.TICK_ONE, gi)
        page.wait_for_timeout(550)
    st = page.evaluate(js.RADIO_STATE)
    return [k for k, v in enumerate(st) if v]


def _submit(page, tag):
    for attempt in range(3):
        page.wait_for_timeout(500)
        rects = page.evaluate(js.QUIZ_SUBMIT_RECTS)
        if not rects:
            page.evaluate(js.CLOSE_EVAL)
            page.wait_for_timeout(1200)
            rects = page.evaluate(js.QUIZ_SUBMIT_RECTS)
        if not rects:
            continue
        for rc in rects[:2]:
            page.mouse.click(rc['x'], rc['y'])
            page.wait_for_timeout(1300)
            for _ in range(3):
                cands = page.evaluate(js.CONFIRM_RECTS)
                if not cands:
                    break
                cands.sort(key=lambda c: c['w'] * c['h'])
                page.mouse.click(cands[0]['x'], cands[0]['y'])
                page.wait_for_timeout(1200)
            page.wait_for_timeout(1200)
            g = page.evaluate(js.GRADE)
            if g['letters'] or g['wrong']:
                return g
        page.evaluate(js.CLOSE_EVAL)
    return None


def _letters_to_gidx(q, letters):
    """『正确答案 A/B/C』 → 全局 radio 序号"""
    if len(letters) < len(q['questions']):
        return None
    out, acc = [], 0
    for k, item in enumerate(q['questions']):
        letter = (letters[k] or '').upper()
        if letter not in 'ABCDEF':
            return None
        pos = 'ABCDEF'.index(letter)
        if pos >= len(item['opts']):
            return None
        out.append(acc + pos)
        acc += len(item['opts'])
    return out


def run(page, maxn=0):
    _, us = browser.progress(page)
    todo = [u for u in us if u['type'] == 'quiz' and not u['done']]
    known = [u for u in todo if u['id'] in QUIZ]
    unknown = [u for u in todo if u['id'] not in QUIZ]
    log(f'随堂测验：待做 {len(todo)} 个（题库覆盖 {len(known)} 个）')
    if unknown:
        log('  题库未覆盖，跳过：' + '、'.join((x['name'] or x['lesson'])[:14] for x in unknown[:6]))

    ok = fail = 0
    for i, u in enumerate(known):
        if maxn and i >= maxn:
            log(f'达到本次上限 {maxn}，停止')
            break
        q = QUIZ[u['id']]
        tag = f'[{i + 1}/{len(known)}]'
        log(f"{tag} {(u['lesson'] or u['name'])[:30]} | {len(q['questions'])} 题")
        try:
            if not _enter_unit(page, u, tag):
                log(tag, '  !! 进入单元失败')
                fail += 1
                continue
            gidx = _target_indices(page, q, tag)
            if gidx is None:
                fail += 1
                continue
            result = 'unknown'
            for rnd in range(2):
                if rnd:
                    if not _enter_unit(page, u, tag):
                        result = 'nav-fail'
                        break
                got = _tick(page, gidx)
                if got != gidx:
                    log(tag, f'  !! 勾选不一致 期望{gidx} 实际{got}')
                    result = 'tick-mismatch'
                    break
                g = _submit(page, tag)
                if g is None:
                    result = 'submit-fail'
                    break
                log(tag, f"  批改：错={g['wrong']} 正确答案={g['letters']}")
                if not g['wrong']:
                    result = 'correct'
                    break
                ng = _letters_to_gidx(q, g['letters'])
                if not ng:
                    result = 'map-fail'
                    break
                gidx = ng
                result = 'wrong-then-fixed'
            log(tag, '  →', result)
            ok += 1 if result in ('correct', 'wrong-then-fixed') else 0
            fail += 0 if result in ('correct', 'wrong-then-fixed') else 1
        except Exception as e:
            log(tag, '  !! 异常：', str(e).splitlines()[0][:140])
            fail += 1
            page.screenshot(path=os.path.join(config.LOG_DIR, 'quiz_unit_err.png'))
            browser.enter_content(page)
    return ok, fail
