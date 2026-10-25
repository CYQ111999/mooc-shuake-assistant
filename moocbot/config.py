# -*- coding: utf-8 -*-
"""全局配置：课程常量 + 路径（课程与学期固定，故直接硬编码）"""
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')
# 浏览器登录态目录：默认放程序目录下，可用环境变量 MOOC_PROFILE 指定其它位置
PROFILE_DIR = os.environ.get('MOOC_PROFILE') or os.path.join(ROOT, '.profile')
LOG_DIR = os.path.join(ROOT, 'logs')
REPORT_DIR = os.path.join(ROOT, '报告')
LEARNED_FILE = os.path.join(DATA_DIR, 'learned_answers.json')   # 做题过程中学到的答案

_cache = {}


def load(name):
    if name not in _cache:
        with open(os.path.join(DATA_DIR, name), encoding='utf-8') as f:
            _cache[name] = json.load(f)
    return _cache[name]


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


COURSE = load('course.json')
BASE = COURSE['base']
KEY = COURSE['courseKey']
TERM = COURSE['termId']
COURSE_NAME = COURSE['courseName']
EXPIRED = set(COURSE.get('expiredAssess', []))

LEARN_URL = f"{BASE}/learn/{KEY}?tid={TERM}"
OUTLINE_API = (f"/front-mooc-learn/api/learn/terms/{TERM}/content-outline"
               f"?courseKey={KEY}&entryMode=learn")
# 绝对地址：停在登录页时也能直接查登录态（同源 fetch，不影响页面）
OUTLINE_ABS = BASE + OUTLINE_API
# 未登录时直接停在这里等，避免 /learn/ 被重定向到公开课程页反复跳转
LOGIN_URL = f"{BASE}/member/login.htm#/webLoginIndex"

for _d in (PROFILE_DIR, LOG_DIR, REPORT_DIR):
    os.makedirs(_d, exist_ok=True)
