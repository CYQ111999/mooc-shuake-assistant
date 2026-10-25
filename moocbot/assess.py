# -*- coding: utf-8 -*-
"""测验与作业：读卡片状态 → 按题库作答 → 提交 → 从成绩页学习正确答案（可选重做提分）"""
import os
import re
import time

from . import browser, config, js
from .util import (log, norm, match_question, match_option, is_expired,
                   save_learned, load_learned)

BANK = config.load('unit_quiz_bank.json')
HWS = config.load('homeworks.json')


# ---------------- 卡片解析 ----------------
def parse_cards(page):
    # 先把所有折叠的卡片展开（面板里的“已提交/次数/分数”才读得到）
    page.evaluate(js.EXPAND_ALL)
    page.wait_for_timeout(2500)
    page.evaluate(js.EXPAND_ALL)
    page.wait_for_timeout(1500)
    raw, best = [], []
    for _ in range(3):
        raw = page.evaluate(js.CARDS) or []
        if len(raw) >= len(best):
            best = raw
        if len(best) >= 8:
            break
        page.wait_for_timeout(1500)
    raw = best
    out = []
    for c in raw:
        head = c.get('head') or ''
        panel = c.get('panel') or ''
        mp = re.search(r'assessment-panel-(quiz|homework)-(\d+)', c.get('panelId') or '')
        if mp:
            typ, aid = ('quiz' if mp.group(1) == 'quiz' else 'hw'), mp.group(2)
        else:
            m2 = re.search(r'#/learn/(quiz|hw)\?id=(\d+)', c.get('goHref') or c.get('goData') or '')
            typ, aid = (m2.group(1), m2.group(2)) if m2 else ('', '')
        title = re.split(r'\s*截止时间', head)[0].strip() or head[:24]
        dl = re.search(r'([\d]{4}/[\d]{1,2}/[\d]{1,2}\s*[\d]{1,2}:[\d]{2})', panel) \
            or re.search(r'([\d]{4}/[\d]{1,2}/[\d]{1,2}\s*[\d]{1,2}:[\d]{2})', head)
        mu = re.search(r'有效提交次数\s*(\d+)\s*/\s*(\d+)', panel)
        ms = re.search(r'有效分数\s*([\d.]+)\s*/\s*([\d.]+)', panel)
        if not ms:
            ms = re.search(r'([\d.]+)\s*/\s*([\d.]+)', c.get('scoreText') or '')
        out.append({
            'title': title,
            'type': typ,
            'id': aid,
            'deadline': dl.group(1) if dl else '',
            'used': int(mu.group(1)) if mu else None,
            'total': int(mu.group(2)) if mu else None,
            'score': float(ms.group(1)) if ms else None,
            'full': float(ms.group(2)) if ms else None,
            'goHref': c.get('goHref') or '',
            'goClosed': bool(c.get('goClosed')),
            'body': panel,
        })
    return [x for x in out if x['type'] and x['id']]


def decide(it):
    """返回 (动作, 原因)"""
    if it['title'] in config.EXPIRED:
        return 'skip', '已过期（统一跳过，不占次数）'
    if it['deadline'] and is_expired(it['deadline']):
        return 'skip', '已过截止时间'
    if it['type'] == 'quiz':
        if it['used'] is not None and it['total'] and it['used'] >= it['total']:
            return 'skip', f"次数已用完 {it['used']}/{it['total']}"
        if it['goClosed'] and not it['goHref']:
            return 'skip', '作答入口已关闭'
    else:
        if it['goClosed'] and not it['goHref']:
            return 'skip', '提交入口已关闭'
    return 'go', ''


# ---------------- 打开发布在卡片里的链接 ----------------
def _open_card(ctx, page, title, tag):
    card = page.query_selector(f'article.learn-assessment-card:has-text("{title}")')
    if not card:
        log(tag, '!! 找不到卡片')
        return None
    t = card.query_selector('button[data-assessment-toggle="true"]')
    try:
        if t and t.get_attribute('aria-expanded') == 'false':
            t.click()
            page.wait_for_timeout(1500)
    except Exception:
        pass
    go = card.query_selector('.learn-assessment-go')
    if not go:
        go = card.query_selector('a[href*="#/learn/"]')
    if not go:
        log(tag, '!! 卡片里没有作答入口')
        return None
    if not go.get_attribute('href'):
        log(tag, '!! 作答入口不可用（次数用完 / 已关闭）')
        return None
    before = len(ctx.pages)
    card.evaluate("""(a) => { const g = a.querySelector('.learn-assessment-go')
        || a.querySelector('a[href*="#/learn/"]'); if (g) g.click(); }""")
    page.wait_for_timeout(5000)
    if len(ctx.pages) > before:
        np = ctx.pages[-1]
        try:
            np.wait_for_load_state('domcontentloaded', timeout=30000)
        except Exception:
            pass
        return np
    return page


def _close_tab(ctx, page, pop):
    if pop is not None and pop is not page:
        try:
            pop.close()
        except Exception:
            pass
        page.wait_for_timeout(800)


# ---------------- 通用提交（测验） ----------------
def _submit_quiz(p, tag):
    for _ in range(20):
        m = p.evaluate(js.MODAL_TEXT)
        if not m:
            break
        p.evaluate(js.CLOSE_MODAL)
        p.wait_for_timeout(600)
    if p.evaluate(js.MODAL_TEXT):
        log(tag, '  有并发限制弹窗，冷却 20 秒')
        p.wait_for_timeout(20000)
        for _ in range(16):
            if not p.evaluate(js.MODAL_TEXT):
                break
            p.evaluate(js.CLOSE_MODAL)
            p.wait_for_timeout(600)

    p.evaluate("() => { const b = document.querySelector('a.j-submitBtn'); "
               "if (b) b.scrollIntoView({block:'center'}); }")
    p.wait_for_timeout(600)
    p.evaluate("() => { const b = document.querySelector('a.j-submitBtn'); if (b) b.click(); }")

    for i in range(20):
        p.wait_for_timeout(1000)
        if p.evaluate("() => (document.body.innerText||'').includes('确定要提交')"):
            cands = p.evaluate(js.LOCATE_OK)
            if cands:
                c = cands[0]
                p.mouse.click(c['x'], c['y'])
                log(tag, '  已点确定')
            break
        if p.evaluate(js.MODAL_TEXT):
            p.evaluate(js.CLOSE_MODAL)
            p.wait_for_timeout(1000)
            p.evaluate("() => { const b = document.querySelector('a.j-submitBtn'); if (b) b.click(); }")
    p.wait_for_timeout(9000)
    return p.url


def _learn_from_result(p, qid, tag):
    try:
        res = p.evaluate(js.RESULT)
    except Exception as e:
        log(tag, '  !! 成绩页解析失败：', str(e)[:100])
        return None, 0
    score = res.get('score')
    learned = []
    for q in res.get('qs', []):
        letter = (q.get('correct') or '').upper()
        opts = q.get('opts') or []
        if letter not in 'ABCDEF' or not opts:
            continue
        k = 'ABCDEF'.index(letter)
        if k >= len(opts):
            continue
        if len(opts) == 2:
            icons = [o.get('icon') or '' for o in opts]
            if icons.count('T') == 1 and icons.count('F') == 1:
                learned.append({'stem': q['stem'], 'type': 'judge',
                                'ansText': '正确' if opts[k]['icon'] == 'T' else '错误'})
        else:
            learned.append({'stem': q['stem'], 'type': 'choice',
                            'ansText': opts[k]['text']})
    n = save_learned(qid, learned)
    return score, n


# ---------------- 测验 ----------------
def _build_plan(qs, bank):
    plan, hit = [], 0
    for q in qs:
        item = match_question(q['stem'], bank)
        want = None
        if item:
            ans_text = item.get('ansText') or ''
            if q['nOpts'] == 2:
                base = norm(ans_text)
                if base in ('正确', '对', 'T', 'true', '√'):
                    want = 'T'
                elif base in ('错误', '错', 'F', 'false', '×'):
                    want = 'F'
                elif ans_text:
                    # 文本可能是「对/错」的完整表述
                    want = 'T' if '正确' in ans_text or ans_text.strip() == '对' else 'F'
            else:
                k = match_option(ans_text, q['opts'])
                if k is not None:
                    want = q['opts'][k]['letter']
                elif item.get('ans') in 'ABCDEF':
                    want = item['ans']
        if want:
            hit += 1
        else:
            want = 'T' if q['nOpts'] == 2 else 'A'
        plan.append({'idx': q['idx'], 'want': want})
    return plan, hit


def do_quiz(ctx, page, it, redo=True, min_cov=0.5, dry=False, force=False):
    tag = '[测验]'
    qid = it['id']
    bank = (BANK.get(qid, {}) or {}).get('questions', [])
    if not bank:
        log(tag, f"{it['title']}：题库里没有这道题，跳过（保护答题次数）")
        return 'no-bank'
    bank = list(bank) + load_learned(qid)

    attempts = it['total'] or (BANK.get(qid, {}) or {}).get('attempts') or 2
    used = it['used'] or 0
    left = max(0, attempts - used)
    log(tag, f"{it['title']}｜已用 {used}/{attempts} 次｜题库 {len(bank)} 条")

    best = None
    rounds = 2 if redo else 1
    for rnd in range(min(rounds, left) if left else 0):
        if dry and rnd > 0:
            break
        log(tag, f'  第 {rnd + 1} 轮作答')
        p = _open_card(ctx, page, it['title'], tag)
        if p is None:
            return 'open-fail'
        try:
            p.wait_for_timeout(6000)
            n = p.evaluate(js.QUESTION_COUNT)
            if n == 0:
                r = p.evaluate(js.START_QUIZ)
                log(tag, '  开始测验：', r)
                if r == 'no-btn':
                    log(tag, '  当前不可作答（已提交 / 次数用完）')
                    return 'unavailable'
                p.wait_for_timeout(9000)
                n = p.evaluate(js.QUESTION_COUNT)
                if n == 0:
                    # 少数情况下会弹「确认开始」框
                    for _ in range(3):
                        cands = [c for c in (p.evaluate(js.HW_CONFIRM_RECTS) or [])
                                 if c['t'] in ('确定', '是', '确认')]
                        if not cands:
                            break
                        cands.sort(key=lambda c: c['w'] * c['h'])
                        p.mouse.click(cands[0]['x'], cands[0]['y'])
                        p.wait_for_timeout(3000)
                    n = p.evaluate(js.QUESTION_COUNT)
            if n == 0:
                log(tag, '  !! 没有读到题目')
                return 'no-question'
            log(tag, f'  题数 {n}')
            qs = p.evaluate(js.QUESTIONS)
            plan, hit = _build_plan(qs, bank)
            cov = hit / max(1, len(plan))
            log(tag, f'  题库命中 {hit}/{len(plan)}（{cov * 100:.0f}%）')
            if cov < min_cov and not force:
                log(tag, f'  覆盖率低于 {min_cov * 100:.0f}%，本轮不提交（保护次数）。'
                         f'可加 --force 强制提交')
                return 'low-coverage'
            if dry:
                p.evaluate(js.FILL_PLAN, plan)
                p.wait_for_timeout(1200)
                log(tag, '  演练模式：已勾选但未提交')
                p.screenshot(path=os.path.join(config.LOG_DIR, f'dry_{qid}.png'), full_page=True)
                return 'dry'

            res = p.evaluate(js.FILL_PLAN, plan)
            bad = [x for x in res if x.endswith('no-target') or x.endswith('no-block')]
            p.wait_for_timeout(2200)
            ver = p.evaluate(js.VERIFY)
            filled = sum(1 for v in ver if v['picked'])
            log(tag, f'  已勾选 {filled}/{len(ver)}' + (f'，异常 {bad[:3]}' if bad else ''))
            if filled < len(ver) * 0.9:
                log(tag, '  !! 勾选数不足，放弃提交')
                return 'fill-fail'

            _submit_quiz(p, tag)
            score, learned_n = _learn_from_result(p, qid, tag)
            log(tag, f'  成绩 {score}｜从成绩页学到 {learned_n} 条正确答案')
            p.screenshot(path=os.path.join(config.LOG_DIR, f'result_{qid}.png'), full_page=True)
            if score:
                try:
                    got, full = [float(x) for x in score.split('/')]
                    best = max(best or 0, got)
                    if full and got >= full:
                        log(tag, '  已满分，不再重做')
                        return 'full'
                except Exception:
                    pass
            bank = list((BANK.get(qid, {}) or {}).get('questions', [])) + load_learned(qid)
            # 还要重做的话，先看学到的答案能不能覆盖 90% 以上，够高才值得再花一次机会
            if rnd + 1 < min(rounds, left):
                probe_plan, probe_hit = _build_plan(qs, bank)
                cov2 = probe_hit / max(1, len(probe_plan))
                if cov2 < max(min_cov, 0.9):
                    log(tag, f'  学到的答案只能覆盖 {cov2 * 100:.0f}%，'
                             f'再考一次提升有限，保留剩余次数不重做')
                    return f'best={best}'
                log(tag, f'  已补全答案（覆盖 {cov2 * 100:.0f}%），用剩余次数再考一次')
        except Exception as e:
            log(tag, '  !! 异常：', str(e).splitlines()[0][:140])
            p.screenshot(path=os.path.join(config.LOG_DIR, 'quiz_err.png'))
            return 'error'
        finally:
            _close_tab(ctx, page, p)
            page.wait_for_timeout(2500)

    return f'best={best}' if best else 'done'


# ---------------- 作业 ----------------
def do_hw(ctx, page, it, dry=False):
    tag = '[作业]'
    hw = HWS.get(it['id'])
    if not hw:
        log(tag, f"{it['title']}：没有内置答案，跳过")
        return 'no-answer'
    p = _open_card(ctx, page, it['title'], tag)
    if p is None:
        return 'open-fail'
    try:
        p.wait_for_timeout(6000)
        txt0 = p.evaluate("() => (document.body.innerText||'').replace(/\\s+/g,' ')")
        if '已完成并提交' in txt0 or '作业已提交' in txt0:
            log(tag, f"{it['title']}：平台显示「作业已完成并提交」→ 跳过")
            return 'already'
        sel = '.ql-container.ql-snow .ql-editor'
        eds = p.locator(sel)
        n = eds.count()
        log(tag, f"{it['title']}｜答题框 {n} 个｜答案 {len(hw['answers'])} 段")
        if n == 0:
            log(tag, '  没有答题框（可能已提交过）')
            return 'no-editor'
        can = p.evaluate("""() => [...document.querySelectorAll('a,button')]
            .some(x => (x.innerText||'').trim() === '提交答案')""")
        if not can:
            log(tag, '  页面上没有「提交答案」按钮 → 已提交过，跳过')
            return 'already'
        if n != len(hw['answers']):
            log(tag, f'  !! 答题框数量与答案不符，跳过以免写错位置')
            return 'count-mismatch'

        try:
            cbs = p.evaluate(js.HW_CB)
            if cbs and not all(cbs):
                p.evaluate(js.HW_CHECK_CB)
                p.wait_for_timeout(600)
        except Exception:
            pass

        for i, ans in enumerate(hw['answers']):
            el = eds.nth(i)
            el.scroll_into_view_if_needed()
            p.wait_for_timeout(300)
            el.click()
            p.wait_for_timeout(400)
            p.keyboard.press('Control+A')
            p.keyboard.press('Delete')
            p.wait_for_timeout(250)
            p.keyboard.insert_text(ans['text'])
            p.wait_for_timeout(1100)
            L = p.evaluate(f"() => (document.querySelectorAll('{sel}')[{i}].innerText||'').length")
            log(tag, f"  第{i + 1}题写入 {L}/{len(ans['text'])} 字")

        lens = p.evaluate(js.HW_EDITORS)
        log(tag, '  各框字数：', lens)
        if any(x < 300 for x in lens):
            log(tag, '  !! 有答案过短，放弃提交')
            return 'too-short'
        if dry:
            p.screenshot(path=os.path.join(config.LOG_DIR, f'dry_hw_{it["id"]}.png'), full_page=True)
            log(tag, '  演练模式：已填写但未提交')
            return 'dry'

        p.evaluate(js.HW_SUBMIT)
        for i in range(15):
            p.wait_for_timeout(1000)
            cands = p.evaluate(js.HW_CONFIRM_RECTS)
            if cands:
                cands.sort(key=lambda c: c['w'] * c['h'])
                p.mouse.click(cands[0]['x'], cands[0]['y'])
                break
        p.wait_for_timeout(7000)
        p.screenshot(path=os.path.join(config.LOG_DIR, f'submitted_hw_{it["id"]}.png'), full_page=True)
        txt = p.evaluate("() => (document.body.innerText||'').slice(0,200)")
        done = bool(re.search(r'已提交|提交成功|等待互评|作业批改', txt or ''))
        log(tag, f"  提交后状态：{'已提交' if done else (txt or '').replace(chr(10), ' ')[:80]}")
        return 'submitted' if done else 'submit-unclear'
    except Exception as e:
        log(tag, '  !! 异常：', str(e).splitlines()[0][:150])
        p.screenshot(path=os.path.join(config.LOG_DIR, 'hw_err.png'))
        return 'error'
    finally:
        _close_tab(ctx, page, p)
        page.wait_for_timeout(2000)


# ---------------- 入口 ----------------
def run(ctx, page, redo=True, min_cov=0.5, dry=False, force=False):
    if not browser.enter_assess(page):
        log('!! 无法进入测验与作业页')
        return {}
    page.wait_for_timeout(2000)
    items = parse_cards(page)
    log(f'共发现 {len(items)} 个测验/作业：')
    for it in items:
        log(f"  · {it['title']:<8} {('作业' if it['type'] == 'hw' else '测验')} "
            f"截止 {it['deadline'] or '?'} "
            f"{'已用 %s/%s' % (it['used'], it['total']) if it['used'] is not None else ''}")

    results = {}
    for idx, it in enumerate(items):
        act, why = decide(it)
        log('')
        log(f"[{idx + 1}/{len(items)}] {it['title']}")
        if act == 'go' and it['score'] is not None and it['full'] \
                and it['score'] >= it['full'] - 0.001:
            act, why = 'skip', f'已满分 {it["score"]:g}/{it["full"]:g}'
        if act == 'skip':
            log(f"  跳过：{why}")
            results[it['title']] = '跳过（' + why + '）'
            continue
        if redo and it['type'] == 'quiz' and it['used']:
            log(f"  已做过 {it['used']} 次，按「取最高分」规则尝试提分")
        try:
            if it['type'] == 'quiz':
                r = do_quiz(ctx, page, it, redo=redo, min_cov=min_cov, dry=dry, force=force)
            else:
                r = do_hw(ctx, page, it, dry=dry)
            results[it['title']] = r
        except Exception as e:
            log('  !! 未捕获异常：', str(e).splitlines()[0][:150])
            results[it['title']] = 'error'
            browser.enter_assess(page)
    return results
