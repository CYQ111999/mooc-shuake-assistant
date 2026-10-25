# -*- coding: utf-8 -*-
"""全部页面内执行的 JS 片段（均在真实页面上验证过）"""

# ---------- 通用 ----------
OUTLINE = """async (api) => {
    try {
        const r = await fetch(api, {credentials: 'include'});
        const t = await r.text();
        try { return JSON.parse(t); } catch (e) { return {_raw: t.slice(0, 200), _status: r.status}; }
    } catch (e) { return {_err: String(e)}; }
}"""

PUSH = """(t) => {
    const r = window.next && window.next.router;
    if (!r || !r.push) return 'no-router';
    try { r.push(t); return 'pushed'; } catch (e) { return 'err:' + e.message; }
}"""

CLICK_KJ = """() => {
    const c = [...document.querySelectorAll('a,div,span,li')]
        .filter(e => (e.innerText || '').trim() === '课件');
    if (c.length) { c[0].click(); return true; }
    return false;
}"""

CLICK_ASSESS = """() => {
    const a = document.querySelector('aside a[href*="/assessments"]');
    if (a) { a.click(); return true; }
    const c = [...document.querySelectorAll('a,div,span,li')]
        .filter(e => /测验与作业|测试与作业/.test((e.innerText || '').trim()) && e.children.length < 4);
    if (c.length) { c[0].click(); return true; }
    return false;
}"""

# ---------- 视频 ----------
VIDEO_SEEK = """() => {
    const v = document.querySelector('video');
    if (!v) return 'no-video';
    v.muted = true;
    try { v.playbackRate = 4; } catch (e) {}
    const d = v.duration;
    if (!d || isNaN(d) || d <= 0) { v.play().catch(() => {}); return 'no-duration'; }
    if (v.ended) return 'already-ended';
    v.currentTime = Math.max(0, d - 1.0);
    v.play().catch(() => {});
    return 'seeking';
}"""

VIDEO_STATE = """() => {
    const v = document.querySelector('video');
    if (!v) return null;
    return {cur: +v.currentTime.toFixed(1), dur: +(v.duration || 0).toFixed(1),
            ended: v.ended, paused: v.paused};
}"""

POPUP = """() => {
    const vis = el => { const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity < 0.1) return false;
        const r = el.getBoundingClientRect(); return r.width > 15 && r.height > 15 && r.top > -10 && r.top < innerHeight; };
    const cands = [...document.querySelectorAll('a,button,span,div,label')].filter(e =>
        vis(e) && e.children.length < 3 &&
        /^(继续播放|继续学习|继续|确定|知道了|关闭|跳过|提交答案|下一题)$/.test((e.innerText || '').trim()));
    if (!cands.length) return 'none';
    cands[0].click();
    return 'clicked:' + (cands[0].innerText || '').trim();
}"""

# ---------- PDF ----------
PDF_INFO = """() => {
    const r = document.querySelector('.mooc-docs-reader');
    if (!r) return null;
    const thumbs = [...r.querySelectorAll('button[aria-label^="跳转到第"]')];
    const st = r.querySelector('.mooc-docs-reader__page-status');
    return {nThumbs: thumbs.length,
            status: st ? (st.innerText || '').replace(/\\s+/g, ' ').trim() : ''};
}"""

PDF_TURN = """async () => {
    const r = document.querySelector('.mooc-docs-reader');
    if (!r) return 'no-reader';
    const thumbs = [...r.querySelectorAll('button[aria-label^="跳转到第"]')];
    for (let i = 0; i < thumbs.length; i++) {
        try { thumbs[i].click(); } catch (e) {}
        await new Promise(res => setTimeout(res, 380));
    }
    return 'turned:' + thumbs.length;
}"""

# ---------- 讨论区 ----------
GET_REPLIES = """() => {
    const acts = [...document.querySelectorAll('.forum-reply-actions')];
    const out = [];
    for (const a of acts) {
        const par = a.parentElement;
        if (!par) continue;
        let t = (par.innerText || '').trim();
        const at = (a.innerText || '').trim();
        if (at) t = t.replace(at, '').trim();
        t = t.split('\\n').map(s => s.trim()).filter(Boolean).join('\\n');
        if (t.length >= 25) out.push(t);
    }
    return out;
}"""

EDITORS = """() => {
    const es = [...document.querySelectorAll('.ql-editor')].filter(e => e.getBoundingClientRect().width > 50);
    return {n: es.length, len: es.length ? (es[0].innerText || '').trim().length : 0,
            blank: es.length ? (es[0].className || '').toString().includes('ql-blank') : true};
}"""

REPLY_BTN = """() => {
    const b = [...document.querySelectorAll('button')].find(e => (e.innerText || '').trim() === '发表回复');
    if (!b) return null;
    const r = b.getBoundingClientRect();
    return {x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
            inView: r.top >= 0 && r.bottom <= innerHeight, disabled: !!b.disabled};
}"""

# ---------- 随堂测验 ----------
# 读出所有 radio 及其选项文本（扁平，按题目顺序排列）
RADIOS = """() => {
    return [...document.querySelectorAll('input[type=radio]')].map((r, i) => {
        const lab = r.closest('label') || r.parentElement;
        return {i: i, text: (lab ? (lab.innerText || '') : '').trim()};
    });
}"""

TICK_ONE = """(gi) => {
    const rs = [...document.querySelectorAll('input[type=radio]')];
    const r = rs[gi];
    if (!r) return 'missing';
    try { r.scrollIntoView({block: 'center'}); } catch (e) {}
    const lab = r.closest('label') || r.parentElement;
    try { lab.click(); } catch (e) { try { r.click(); } catch (e2) { return 'clickfail'; } }
    return 'ok';
}"""

RADIO_STATE = """() => [...document.querySelectorAll('input[type=radio]')].map(r => r.checked ? 1 : 0)"""

QUIZ_SUBMIT_RECTS = """() => {
    const root = document.querySelector('.learn-courseware-panel') || document.body;
    const inEval = b => {
        let n = b;
        for (let i = 0; i < 8 && n; i++) {
            const t = n.innerText || '';
            if (/请评分|撰写.{0,6}评价|如何写好一篇有价值的评价/.test(t) && t.length < 500) return true;
            n = n.parentElement;
        }
        return false;
    };
    const bs = [...root.querySelectorAll('button')]
        .filter(e => (e.innerText || '').trim() === '提交' && !inEval(e));
    const out = [];
    bs.forEach(b => {
        const r = b.getBoundingClientRect();
        if (r.width > 10 && r.height > 10) {
            out.push({x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2)});
        }
    });
    if (bs.length) { try { bs[0].scrollIntoView({block: 'center'}); } catch (e) {} }
    return out;
}"""

CLOSE_EVAL = """() => {
    const vis = el => { const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity < 0.15) return false;
        const r = el.getBoundingClientRect(); return r.width > 20 && r.height > 20; };
    const hasEval = [...document.querySelectorAll('div,section')].some(el => vis(el) &&
        /撰写.{0,6}的评价|请评分|如何写好一篇有价值的评价/.test(el.innerText || ''));
    if (!hasEval) return 'none';
    const cands = [...document.querySelectorAll('button,a,span,div')].filter(e => vis(e) &&
        e.children.length < 3 && ['取消', '关闭'].includes((e.innerText || '').trim()));
    if (cands.length) { cands[0].click(); return 'cancel'; }
    return 'stuck';
}"""

CONFIRM_RECTS = """() => {
    const vis = el => { const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity < 0.15) return false;
        const r = el.getBoundingClientRect(); return r.width > 5 && r.height > 5; };
    const hits = [...document.querySelectorAll('div,section')].filter(el => vis(el) &&
        /确定要提交|确认提交|还有.*题未作答/.test(el.innerText || '') && (el.innerText || '').length < 400);
    hits.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
    const out = [];
    const push = sc => [...sc.querySelectorAll('a,button,span,div')].filter(e => vis(e) &&
        (e.innerText || '').trim() === '确定').forEach(e => {
        const r = e.getBoundingClientRect();
        out.push({x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
                  w: Math.round(r.width), h: Math.round(r.height)});
    });
    hits.slice(0, 2).forEach(push);
    return out;
}"""

GRADE = """() => {
    const t = document.body.innerText || '';
    const letters = [...t.matchAll(/正确答案[：:]\\s*([A-F])/g)].map(m => m[1]);
    return {wrong: /错选|选错/.test(t), letters: letters,
            hasSubmit: [...document.querySelectorAll('button')].some(e => (e.innerText || '').trim() === '提交')};
}"""

REDO = """() => {
    const b = [...document.querySelectorAll('button')].find(e => (e.innerText || '').trim() === '重新答题');
    if (!b) return 'none';
    try { b.scrollIntoView({block: 'center'}); } catch (e) {}
    try { b.click(); return 'clicked'; } catch (e) { return 'err'; }
}"""

HAS_SUBMIT = """() => [...document.querySelectorAll('button')].some(e => (e.innerText || '').trim() === '提交')"""

# ---------- 测验 / 作业 ----------
EXPAND_ALL = """() => {
    let n = 0;
    document.querySelectorAll('button[data-assessment-toggle="true"]').forEach(b => {
        try {
            if (b.getAttribute('aria-expanded') === 'false') { b.click(); n++; }
        } catch (e) {}
    });
    return n;
}"""

CARDS = """() => {
    const cards = [...document.querySelectorAll('article.learn-assessment-card')];
    return cards.map(c => {
        const h = c.querySelector('button[data-assessment-toggle="true"]');
        const p = c.querySelector('[id^="assessment-panel-"]');
        const go = c.querySelector('.learn-assessment-go');
        const sc = c.querySelector('button[aria-label="有效分数"]');
        return {
            head: h ? (h.innerText || '').replace(/\\s+/g, ' ').trim() : '',
            panelId: p ? (p.id || '') : '',
            panel: p ? (p.innerText || '').replace(/\\s+/g, ' ').trim() : '',
            goHref: go ? (go.getAttribute('href') || '') : '',
            goData: go ? (go.getAttribute('data-assessment-href') || '') : '',
            goClosed: go ? /is-closed/.test(go.className || '') : true,
            goText: go ? (go.innerText || '').trim() : '',
            scoreText: sc ? (sc.innerText || '').trim() : ''
        };
    });
}"""

START_QUIZ = """() => {
    const cb = document.querySelector('input[type=checkbox]');
    if (cb && !cb.checked) { const l = cb.closest('label') || cb; l.click(); }
    const b = [...document.querySelectorAll('a,button,span')]
        .find(x => (x.innerText || '').trim() === '开始测验');
    if (!b) return 'no-btn';
    b.click();
    return 'started';
}"""

QUESTION_COUNT = """() => document.querySelectorAll('.u-questionItem').length"""

# 读出页面每题结构（题干 / 选项文本 / 判断题图标语义）
QUESTIONS = """() => {
    const blocks = [...document.querySelectorAll('.u-questionItem')];
    return blocks.map((b, i) => {
        const labs = [...b.querySelectorAll('label')]
            .filter(l => l.htmlFor && b.querySelector('#' + CSS.escape(l.htmlFor)));
        const rt = b.querySelector('.j-richTxt');
        return {
            idx: i + 1,
            nOpts: labs.length,
            stem: ((rt ? rt.innerText : b.innerText) || '').replace(/\\s+/g, ' ').trim().slice(0, 400),
            opts: labs.map((l, j) => {
                const ic = l.querySelector('i,em,span[class*=icon]');
                const cls = ic ? (ic.className || '').toString().toLowerCase() : '';
                return {letter: String.fromCharCode(65 + j),
                        text: (l.innerText || '').replace(/\\s+/g, ' ').trim(),
                        icon: /correct/.test(cls) ? 'T' : (/wrong/.test(cls) ? 'F' : '')};
            })
        };
    });
}"""

FILL_PLAN = """(plan) => {
    const blocks = [...document.querySelectorAll('.u-questionItem')];
    const out = [];
    plan.forEach(p => {
        const b = blocks[p.idx - 1];
        if (!b) { out.push('Q' + p.idx + ':no-block'); return; }
        const labs = [...b.querySelectorAll('label')]
            .filter(l => l.htmlFor && b.querySelector('#' + CSS.escape(l.htmlFor)));
        let target = null;
        if (p.want.length === 1 && 'ABCDEF'.includes(p.want)) {
            target = labs['ABCDEF'.indexOf(p.want)];
        } else {
            const wc = p.want === 'T' ? 'correct' : 'wrong';
            target = labs.find(l => {
                const ic = l.querySelector('i,em,span[class*=icon]');
                return ic && (ic.className || '').toString().toLowerCase().includes(wc);
            });
        }
        if (!target) { out.push('Q' + p.idx + ':no-target'); return; }
        const inp = b.querySelector('#' + CSS.escape(target.htmlFor));
        if (inp && inp.checked) { out.push('Q' + p.idx + ':ok'); return; }
        try { (b.querySelector('label[for="' + target.htmlFor + '"]') || inp).click(); }
        catch (e) { out.push('Q' + p.idx + ':clickfail'); return; }
        out.push('Q' + p.idx + ':set');
    });
    return out;
}"""

VERIFY = """() => {
    const blocks = [...document.querySelectorAll('.u-questionItem')];
    return blocks.map((b, i) => {
        const labs = [...b.querySelectorAll('label')]
            .filter(l => l.htmlFor && b.querySelector('#' + CSS.escape(l.htmlFor)));
        let picked = null, mean = '';
        labs.forEach((l, j) => {
            const inp = b.querySelector('#' + CSS.escape(l.htmlFor));
            if (inp && inp.checked) {
                picked = String.fromCharCode(65 + j);
                const ic = l.querySelector('i,em,span[class*=icon]');
                const c = ic ? (ic.className || '').toString() : '';
                if (/correct/i.test(c)) mean = '对';
                else if (/wrong/i.test(c)) mean = '错';
            }
        });
        return {idx: i + 1, nOpts: labs.length, picked: picked, mean: mean};
    });
}"""

MODAL_TEXT = """() => {
    const ms = [...document.querySelectorAll('.ux-modal')].filter(m => {
        const cs = getComputedStyle(m);
        return cs.display !== 'none' && cs.visibility !== 'hidden' && parseFloat(cs.opacity || '1') > 0.1;
    });
    return ms.map(m => (m.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 160));
}"""

CLOSE_MODAL = """() => {
    const ms = [...document.querySelectorAll('.ux-modal')].filter(m => {
        const cs = getComputedStyle(m);
        return cs.display !== 'none' && cs.visibility !== 'hidden';
    });
    if (!ms.length) return 'no-modal';
    for (const m of ms.reverse()) {
        const cands = [...m.querySelectorAll('a,button,span,div')]
            .filter(e => (e.innerText || '').trim() === '确定')
            .map(e => { const r = e.getBoundingClientRect();
                        return {e: e, area: r.width * r.height, w: r.width, h: r.height}; })
            .filter(o => o.w > 5 && o.h > 5)
            .sort((a, b) => (a.area - b.area) || (a.w - b.w));
        if (cands.length) { cands[0].e.click(); return 'clicked'; }
    }
    return 'no-btn';
}"""

LOCATE_OK = """() => {
    const vis = el => { const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity || '1') < 0.2) return false;
        const r = el.getBoundingClientRect(); return r.width > 5 && r.height > 5 && r.top >= 0 && r.left >= 0; };
    const pickFrom = (root) => {
        const c = [...root.querySelectorAll('a,button,input,span,div')]
            .filter(e => vis(e) && (e.innerText || e.value || '').trim() === '确定')
            .map(e => { const r = e.getBoundingClientRect(); return {e: e, a: r.width * r.height}; })
            .filter(o => o.a > 0)
            .sort((x, y) => x.a - y.a);
        return c.length ? c[0].e : null;
    };
    const hits = [...document.querySelectorAll('div,section,article,p')]
        .filter(el => vis(el) && (el.innerText || '').includes('确定要提交') && (el.innerText || '').length < 400);
    hits.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
    if (hits.length) {
        let cur = hits[0];
        for (let d = 0; d < 4 && cur; d++) {
            const b = pickFrom(cur);
            if (b) { const r = b.getBoundingClientRect();
                     return [{x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
                              w: Math.round(r.width), h: Math.round(r.height), via: 'ancestor' + d}]; }
            cur = cur.parentElement;
        }
    }
    const g = [...document.querySelectorAll('a,button,input,span,div')]
        .filter(e => vis(e) && (e.innerText || e.value || '').trim() === '确定')
        .map(e => { const r = e.getBoundingClientRect();
                    return {x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
                            w: Math.round(r.width), h: Math.round(r.height), via: 'global'}; })
        .filter(o => o.w > 0 && o.h > 0)
        .sort((a, b) => (a.w * a.h) - (b.w * b.h));
    return g.length ? [g[0]] : [];
}"""

# 成绩页：总分 + 每题正确答案
RESULT = """() => {
    const txt = document.body.innerText || '';
    const blocks = [...document.querySelectorAll('.u-questionItem')];
    const qs = blocks.map((b, i) => {
        const t = b.innerText || '';
        const cm = t.match(/正确答案[：:]\\s*([A-F])/);
        const ym = t.match(/(?:你的答案|我的答案|您的答案)[：:]\\s*([A-F])/);
        const labs = [...b.querySelectorAll('label')]
            .filter(l => l.htmlFor && b.querySelector('#' + CSS.escape(l.htmlFor)));
        const opts = labs.map((l, j) => {
            const ic = l.querySelector('i,em,span[class*=icon]');
            const c = ic ? (ic.className || '').toString().toLowerCase() : '';
            return {letter: String.fromCharCode(65 + j),
                    text: (l.innerText || '').replace(/\\s+/g, ' ').trim(),
                    icon: /correct/.test(c) ? 'T' : (/wrong/.test(c) ? 'F' : '')};
        });
        const rt = b.querySelector('.j-richTxt');
        return {idx: i + 1,
                stem: ((rt ? rt.innerText : t) || '').replace(/\\s+/g, ' ').trim().slice(0, 300),
                correct: cm ? cm[1] : '', mine: ym ? ym[1] : '', opts: opts};
    });
    const sc = txt.match(/(\\d+(?:\\.\\d+)?)\\s*\\/\\s*(\\d+(?:\\.\\d+)?)/);
    return {url: location.href, score: sc ? sc[0] : '', qs: qs, head: txt.slice(0, 260)};
}"""

# ---------- 作业 ----------
HW_EDITORS = """() => [...document.querySelectorAll('.ql-container.ql-snow .ql-editor')]
    .map(e => (e.innerText || '').length)"""

HW_CB = """() => {
    const cs = [...document.querySelectorAll('input[type=checkbox]')];
    return cs.map(c => c.checked);
}"""

HW_CHECK_CB = """() => {
    const cs = [...document.querySelectorAll('input[type=checkbox]')];
    const c = cs.find(x => !x.checked);
    if (c) { const l = c.closest('label'); (l || c).click(); return 'ticked'; }
    return 'none';
}"""

HW_SUBMIT = """() => {
    const b = [...document.querySelectorAll('a,button')]
        .find(x => (x.innerText || '').trim() === '提交答案');
    if (!b) return 'no-btn';
    try { b.scrollIntoView({block: 'center'}); } catch (e) {}
    b.click();
    return 'clicked';
}"""

HW_CONFIRM_RECTS = """() => {
    const vis = el => { const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity || '1') < 0.2) return false;
        const r = el.getBoundingClientRect(); return r.width > 5 && r.height > 5; };
    return [...document.querySelectorAll('a,button,input,span,div')]
        .filter(el => vis(el) && ['确定', '是', '确认'].includes((el.innerText || el.value || '').trim()))
        .map(el => { const r = el.getBoundingClientRect();
                     return {t: (el.innerText || el.value || '').trim(),
                             x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
                             w: Math.round(r.width), h: Math.round(r.height)}; });
}"""
