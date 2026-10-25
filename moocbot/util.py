# -*- coding: utf-8 -*-
"""公共工具：日志、文本归一化、题干匹配、截止时间解析"""
import os
import re
import sys
import time
import datetime
import difflib

from . import config

LOG_LINES = []
_LOG_FILE = None


def init_log(tag='run'):
    global _LOG_FILE
    os.makedirs(config.LOG_DIR, exist_ok=True)
    p = os.path.join(config.LOG_DIR, f'{tag}_{time.strftime("%Y%m%d_%H%M%S")}.log')
    _LOG_FILE = open(p, 'w', encoding='utf-8')
    return p


def log(*args):
    s = ' '.join(str(a) for a in args)
    ts = time.strftime('%H:%M:%S')
    line = f'[{ts}] {s}'
    print(line, flush=True)
    LOG_LINES.append(line)
    if _LOG_FILE:
        _LOG_FILE.write(line + '\n')
        _LOG_FILE.flush()


def title(s):
    log('')
    log('=' * 72)
    log('  ' + s)
    log('=' * 72)


def _strip(s):
    if not s:
        return ''
    for ch in ('\u200b', '\u200c', '\u200d', '\ufeff', '\u202a', '\u202c', '\u2060'):
        s = s.replace(ch, '')
    s = s.replace('\xa0', ' ')
    return s


def norm(s):
    """归一化题干/选项：去不可见字符、去空白、去题号、统一括号"""
    s = _strip(s)
    s = re.sub(r'^\s*\d+\s*[\.、]\s*', '', s)
    s = re.sub(r'^\s*\d+\s*(单选|多选|判断)\s*[（(]\s*\d+\s*分\s*[)）]', '', s)
    s = re.sub(r'\s+', '', s)
    s = s.replace('（', '(').replace('）', ')').replace('，', ',').replace('"', '"').replace('"', '"')
    return s


def similar(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def match_question(stem, bank, threshold=0.72):
    """在题库里找题干最相近的一条；bank: [{'stem':..., ...}]"""
    n = norm(stem)
    if len(n) < 4:
        return None
    # 1) 完全包含（有的题干带图注/多余提示）
    best, best_r = None, 0.0
    for item in bank:
        m = norm(item.get('stem', ''))
        if not m:
            continue
        if n == m:
            return item
        if len(m) >= 6 and (m in n or n in m):
            r = 0.95 - abs(len(m) - len(n)) * 0.001
        else:
            r = similar(n, m)
        if r > best_r:
            best, best_r = item, r
    return best if best_r >= threshold else None


def match_option(ans_text, opts):
    """在选项列表里找答案文本对应的选项 index；opts: [{'letter','text'}]"""
    a = norm(ans_text)
    if not a:
        return None
    for i, o in enumerate(opts):
        if norm(o.get('text', '')) == a:
            return i
    for i, o in enumerate(opts):
        t = norm(o.get('text', ''))
        if t and (t in a or a in t):
            return i
    if len(a) >= 1 and a in 'TF':
        for i, o in enumerate(opts):
            if o.get('icon') == a:
                return i
    return None


def parse_deadline(s):
    """从 '截止时间：2026/10/30 00:30' 这类文本里取 datetime"""
    if not s:
        return None
    m = re.search(r'(20\d\d)[/\-年](\d{1,2})[/\-月](\d{1,2})[日]?\s*(\d{1,2}):(\d{2})', s)
    if not m:
        m2 = re.search(r'(20\d\d)[/\-年](\d{1,2})[/\-月](\d{1,2})', s)
        if not m2:
            return None
        y, mo, d = map(int, m2.groups())
        return datetime.datetime(y, mo, d, 23, 59)
    y, mo, d, h, mi = map(int, m.groups())
    try:
        return datetime.datetime(y, mo, d, h, mi)
    except ValueError:
        return None


def is_expired(deadline_text):
    dt = parse_deadline(deadline_text)
    return bool(dt and dt < datetime.datetime.now())


def human_left(deadline_text):
    dt = parse_deadline(deadline_text)
    if not dt:
        return ''
    d = (dt - datetime.datetime.now()).total_seconds() / 86400
    if d < 0:
        return '已截止'
    if d < 1:
        return f'{d * 24:.0f} 小时后截止'
    return f'{d:.0f} 天后截止'


def save_learned(qid, qlist):
    """把成绩页学到的正确答案并入本地题库（按题干存，选项乱序也不怕）"""
    if not qlist:
        return 0
    data = {}
    if os.path.exists(config.LEARNED_FILE):
        try:
            import json
            with open(config.LEARNED_FILE, encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}
    bucket = data.setdefault(str(qid), {})
    n = 0
    for q in qlist:
        stem = q.get('stem') or ''
        ans_text = q.get('ansText') or ''
        if len(norm(stem)) < 4 or not ans_text:
            continue
        key = norm(stem)[:120]
        bucket[key] = {'stem': stem, 'ansText': ans_text,
                       'type': q.get('type', 'choice'),
                       'at': time.strftime('%Y-%m-%d %H:%M')}
        n += 1
    config.save_json(config.LEARNED_FILE, data)
    return n


def load_learned(qid):
    import json
    try:
        with open(config.LEARNED_FILE, encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return []
    return list(data.get(str(qid), {}).values())


class Tee(object):
    """把 print 同时写进日志文件（供最终报告使用）"""

    def __init__(self, path):
        self.path = path

    def dump(self):
        if not self.path:
            return
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(LOG_LINES))
        except Exception:
            pass
