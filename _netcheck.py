# -*- coding: utf-8 -*-
"""只在依赖安装失败时被 一键开始.bat 调用：探测几个 pip 镜像站能不能连通。

目的很单一——把「是网络问题」和「是 Python 版本问题」区分开，
并告诉用户到底是哪个站不通、通到哪一步（DNS / TLS / 超时）。
"""
import socket
import ssl
import sys
import urllib.request

URLS = [
    'https://pypi.tuna.tsinghua.edu.cn/simple/',
    'https://mirrors.aliyun.com/pypi/simple/',
    'https://mirrors.cloud.tencent.com/pypi/simple/',
    'https://pypi.org/simple/',
]


def probe(url):
    host = url.split('/')[2]
    try:
        ip = socket.gethostbyname(host)
    except Exception as e:
        return 'DNS-FAIL', f'{host} 域名解析失败 ({type(e).__name__})'
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(url, timeout=8, context=ctx) as r:
            return 'OK', f'{url}  ->  HTTP {r.status}  ip={ip}'
    except Exception as e:
        return 'FAIL', f'{url}  ->  {type(e).__name__}: {e}  ip={ip}'


def main():
    print('   底下的 python 是：', sys.executable)
    print('   版本：', sys.version.split()[0])
    bad = 0
    for u in URLS:
        state, msg = probe(u)
        if state != 'OK':
            bad += 1
        print(f'   {state:8} {msg}')
    print()
    if bad == len(URLS):
        print('   >>> 四个站全部不通，基本可以确定是本机网络 / 杀毒软件 / 代理的问题。')
        print('   >>> 换个手机热点，或者把 360、火绒、Defender 的实时防护关掉再试。')
    elif bad:
        print('   >>> 有站点是通的，重新运行一次 一键开始.bat 一般就能装上。')
    else:
        print('   >>> 网络是通的，直接重新运行 一键开始.bat 即可。')


if __name__ == '__main__':
    main()
