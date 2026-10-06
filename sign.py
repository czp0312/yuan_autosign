#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ycoo.net (Discuz! k_misign 插件) 自动签到脚本

仅使用 Python 标准库，GitHub Actions 无需安装任何依赖。
账号密码从环境变量 YCOO_USERNAME / YCOO_PASSWORD 读取；
可选 YCOO_QUESTION_ID / YCOO_ANSWER 用于设置了安全提问的账号。

流程：
1. GET 登录页，取 cookie 与 formhash
2. POST 登录
3. GET 签到页 plugin.php?id=k_misign:sign，取页面 formhash
4. POST 签到接口（多候选端点自动尝试，签到成功/已签到均视为完成）
"""

import os
import re
import sys
import time
import urllib.parse
import urllib.request
import http.cookiejar

BASE = os.environ.get("YCOO_BASE", "https://ycoo.net").rstrip("/")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
TIMEOUT = 30
RETRIES = int(os.environ.get("YCOO_RETRIES", "3"))


class Browser:
    """带 cookie、UA 与浏览器式请求头的极简客户端。"""

    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def get(self, url, referer=None):
        req = urllib.request.Request(url, headers=self._headers(referer))
        return self._open(req)

    def post(self, url, data, referer=None):
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=self._headers(referer))
        return self._open(req)

    @staticmethod
    def _headers(referer):
        h = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
        }
        if referer:
            h["Referer"] = referer
        return h

    def _open(self, req):
        last_err = None
        for attempt in range(1, RETRIES + 1):
            try:
                resp = self.opener.open(req, timeout=TIMEOUT)
                return resp.geturl(), resp.read().decode("utf-8", "ignore")
            except Exception as e:  # 网络抖动重试
                last_err = e
                if attempt < RETRIES:
                    time.sleep(3 * attempt)
        raise RuntimeError(f"请求失败 {req.full_url}: {last_err}")


def formhash_of(text):
    m = re.search(r'name="formhash"[^>]*value="([a-f0-9]+)"', text) \
        or re.search(r'formhash=([a-f0-9]+)', text)
    return m.group(1) if m else ""


def login(browser, username, password, question_id, answer):
    login_url = f"{BASE}/member.php?mod=logging&action=login&infloat=yes&inajax=1"
    _, page = browser.get(login_url)
    formhash = formhash_of(page)
    if not formhash:
        raise RuntimeError("登录页未找到 formhash，站点结构可能已变化")

    m = re.search(r'loginhash=([A-Za-z0-9]+)', page)
    loginhash = m.group(1) if m else "login"
    post_url = (f"{BASE}/member.php?mod=logging&action=login"
                f"&loginsubmit=yes&loginhash={loginhash}&inajax=1")

    fields = {
        "formhash": formhash,
        "referer": BASE + "/",
        "loginfield": "username",
        "username": username,
        "password": password,
        "questionid": question_id or "0",
        "answer": answer or "",
        "cookietime": "2592000",
    }
    _, resp = browser.post(post_url, fields, referer=f"{BASE}/member.php?mod=logging&action=login")
    clean = re.sub(r"<!\[CDATA\[|\]\]>", "", resp).strip()

    if "succeedhandle" in clean or "欢迎" in clean or "成功" in clean:
        return "ok", clean
    if "访问" in clean and "次数" in clean:
        return "fail", "登录尝试过于频繁，站点限制了 IP，请稍后再试"
    if "密码错误" in clean or "登录失败" in clean or "成员不存在" in clean or "没有此成员" in clean:
        return "fail", clean
    # 无明确提示时用 /home.php?mod=space 验证会话是否生效
    url, home = browser.get(f"{BASE}/home.php?mod=space&do=notice")
    if "member.php?mod=logging" not in home and "formhash" in home:
        return "ok", f"无明确登录提示，但会话已生效 ({url})"
    return "fail", clean or "未识别的登录响应"


def kmi_sign(browser, formhash):
    """依次尝试 k_misign 的常见签到端点，返回 (状态, 详情)。

    状态: done=今日已签 / signed=本次签到成功 / fail=失败
    """
    candidates = [
        f"{BASE}/plugin.php?id=k_misign:sign&operation=qiandao&formhash={formhash}",
        f"{BASE}/plugin.php?id=k_misign:sign:sign&operation=qiandao&formhash={formhash}",
        f"{BASE}/plugin.php?id=k_misign:sign&mod=sign&operation=qiandao&formhash={formhash}",
        f"{BASE}/plugin.php?id=k_misign:sign&operation=sign&formhash={formhash}",
        f"{BASE}/plugin.php?id=k_misign:sign&operation=qiandao",
    ]
    referer = f"{BASE}/plugin.php?id=k_misign:sign"
    results = []
    for url in candidates:
        try:
            _, resp = browser.get(url, referer=referer)
        except Exception as e:
            results.append((url, f"请求异常: {e}"))
            continue
        clean = re.sub(r"<!\[CDATA\[|\]\]>", "", resp).strip()
        low = clean.lower()
        if any(k in low for k in ("已签", "已经签", "已签到", "sign done", "already")):
            return "done", clean
        if any(k in low for k in ("签到成功", "success", "恭喜", "奖励", "获赠")):
            return "signed", clean
        results.append((url, clean[:120] or "(空响应)"))
    return "fail", " | ".join(f"{u} => {r}" for u, r in results)


def main():
    username = os.environ.get("YCOO_USERNAME", "")
    password = os.environ.get("YCOO_PASSWORD", "")
    question_id = os.environ.get("YCOO_QUESTION_ID", "")
    answer = os.environ.get("YCOO_ANSWER", "")

    if not username or not password:
        print("[FATAL] 未设置环境变量 YCOO_USERNAME / YCOO_PASSWORD")
        return 2
    if len(password) < 4:
        print("[WARN] 密码长度异常，请检查 Secrets 是否配置正确")

    browser = Browser()

    print("[1/3] 登录 ...")
    status, detail = login(browser, username, password, question_id, answer)
    print("      =>", detail[:200].replace("\n", " "))
    if status != "ok":
        print("[FATAL] 登录失败")
        return 1

    print("[2/3] 打开签到页获取 formhash ...")
    sign_page_url = f"{BASE}/plugin.php?id=k_misign:sign"
    _, sign_page = browser.get(sign_page_url, referer=BASE + "/")
    if "member.php?mod=logging" in sign_page:
        print("[FATAL] 会话未生效，签到页仍指向登录页")
        return 1
    fh = formhash_of(sign_page)
    print("      formhash =", fh or "(未找到)")
    if not fh:
        print("[FATAL] 签到页未找到 formhash")
        return 1

    print("[3/3] 请求签到接口 ...")
    status, detail = kmi_sign(browser, fh)
    print("      =>", detail[:300].replace("\n", " "))

    if status == "signed":
        print("[SUCCESS] 签到成功")
        return 0
    if status == "done":
        print("[SUCCESS] 今日已签到，无需重复操作")
        return 0

    print("[FATAL] 签到失败")
    return 1


if __name__ == "__main__":
    sys.exit(main())
