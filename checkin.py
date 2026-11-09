#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCII 节点共享 (https://proxy.mcii.cc) 每日自动签到.

流程:
    1. 打开 https://proxy.mcii.cc/nodes
    2. 未登录时点右上角"登录", 填邮箱 + 密码登录
       (登录后会弹"保持登录状态?"确认框, 点"是"; 再弹 8 步新手引导, 点跳过)
    3. 跳到 https://proxy.mcii.cc/account (我的账号, 概览页),
       点"签到并激活订阅"按钮
       (当天已签到时按钮叫"已签到 · 激活续期", 点了同样续期)
       注意: 签到按钮不在 /nodes 页上, 只在 /account 与 /subscriptions 页有
    4. 如弹出二次确认, 点确认
    5. 截图保存为 checkin.png

凭据全部从环境变量读取, 代码里不写任何明文:
    MCII_EMAIL     登录邮箱(也就是用户名)
    MCII_PASSWORD  登录密码

结果:
    成功: 打印签到结果, 保存 checkin.png, 退出码 0
    失败: 打印错误, 保存 error.png, 退出码 1
          (GitHub Actions 会显示红叉, 日志和截图里能看到失败原因)

依赖: pip install playwright && playwright install chromium
"""

import os
import re
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

BASE_URL = "https://proxy.mcii.cc/nodes"
ACCOUNT_URL = "https://proxy.mcii.cc/account"
CHECKIN_PNG = "checkin.png"
ERROR_PNG = "error.png"


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def find_checkin_button(page):
    """找签到按钮: 未签到叫"签到并激活订阅", 已签到叫"已签到 · 激活续期"."""
    for name in ("签到并激活订阅", "已签到 · 激活续期"):
        btn = page.get_by_role("button", name=name)
        if btn.count() > 0 and btn.first.is_visible():
            return btn.first
    btn = page.get_by_role("button", name=re.compile(r"签到"))
    if btn.count() > 0:
        return btn.first
    return None


def dismiss_tour_if_present(page):
    """新手引导(8 步)每次全新登录都会弹出来, 点跳过关掉. 返回是否点过."""
    for name in ("跳过教程", "跳过"):
        btn = page.get_by_role("button", name=name, exact=True)
        if btn.count() > 0 and btn.first.is_visible():
            log("出现新手引导, 点击跳过")
            btn.first.click()
            page.wait_for_timeout(1000)
            return True
    return False


def wait_for_checkin_button(page, timeout=30):
    """等签到按钮出现, 期间新手引导弹出来就先跳过. 超时返回 None.

    注意: 引导启动时会把页面强制跳回 /nodes(代码里写死的),
    所以跳过引导后必须再回 /account 一次, 否则一直在 /nodes 上等,
    签到按钮永远出不来.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if dismiss_tour_if_present(page):
            log("引导已跳过, 回到我的账号页")
            page.goto(ACCOUNT_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            continue
        btn = find_checkin_button(page)
        if btn is not None:
            return btn
        time.sleep(1)
    return None


def find_login_trigger(page):
    """找右上角的登录入口."""
    for role, name in (("button", "登录"), ("link", "登录")):
        el = page.get_by_role(role, name=name, exact=True)
        if el.count() > 0 and el.first.is_visible():
            return el.first
    el = page.get_by_text("登录", exact=True)
    if el.count() > 0 and el.first.is_visible():
        return el.first
    return None


def do_login(page, email, password):
    """填邮箱 + 密码登录, 成功后等签到按钮出现."""
    log("未登录, 正在登录...")
    trigger = find_login_trigger(page)
    if trigger is None:
        raise RuntimeError("找不到登录入口, 页面结构可能变了")
    trigger.click()
    # 等密码框出现(登录弹窗已打开)
    page.locator('input[type="password"]').first.wait_for(
        state="visible", timeout=15000
    )

    # 用户名框: 先按 placeholder / label 找, 找不到就取弹窗里第一个文本框
    username = None
    for loc in (
        page.get_by_placeholder(re.compile(r"邮箱|用户名|账号")),
        page.get_by_label(re.compile(r"邮箱|用户名|账号")),
    ):
        if loc.count() > 0 and loc.first.is_visible():
            username = loc.first
            break
    if username is None:
        candidates = page.locator(
            'input[type="text"], input[type="email"], input:not([type])'
        )
        for i in range(candidates.count()):
            if candidates.nth(i).is_visible():
                username = candidates.nth(i)
                break
    if username is None:
        raise RuntimeError("找不到用户名输入框")

    username.fill(email)
    page.locator('input[type="password"]').first.fill(password)
    # 回车提交(表单提交比点按钮更稳, 不依赖按钮文字)
    page.locator('input[type="password"]').first.press("Enter")

    # 提交后等登录完成: 登录成功后可能弹出"保持登录状态?"确认框,
    # 必须先点"是"放行; 再等侧边栏"我的账号"出现, 即已登录.
    # 注意: 签到按钮不在 /nodes 页上, 这里不等它.
    deadline = time.time() + 30
    while time.time() < deadline:
        keep = page.get_by_role("button", name="是", exact=True)
        if keep.count() > 0 and keep.first.is_visible():
            log("出现'保持登录状态?'确认框, 点击[是]")
            keep.first.click()
            page.wait_for_timeout(1500)
            continue
        err = page.get_by_text(
            re.compile(r"密码错误|登录失败|账号不存在|验证码错误")
        )
        if err.count() > 0 and err.first.is_visible():
            raise RuntimeError(f"登录失败: {err.first.inner_text().strip()}")
        nav = page.get_by_text("我的账号", exact=True)
        if nav.count() > 0 and nav.first.is_visible():
            log("登录成功")
            return
        time.sleep(1)
    raise RuntimeError("登录后 30 秒内未完成登录, 可能密码错了或页面变了")


def click_confirm_if_present(page):
    """如果弹出二次确认框, 点确认按钮. 返回是否点过."""
    for name in ("确认签到", "仍要签到", "确认"):
        btn = page.get_by_role("button", name=name, exact=True)
        if btn.count() > 0 and btn.first.is_visible():
            log(f"出现二次确认, 点击[{name}]")
            btn.first.click()
            return True
    return False


def wait_for_success(page, timeout=20):
    """等签到成功. 返回成功文案, 超时返回 None."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        ok = page.get_by_text(re.compile(r"签到成功"))
        if ok.count() > 0 and ok.first.is_visible():
            return ok.first.inner_text().strip()
        ok = page.get_by_text(re.compile(r"订阅已激活"))
        if ok.count() > 0 and ok.first.is_visible():
            return ok.first.inner_text().strip()
        btn = find_checkin_button(page)
        if btn is not None and "已签到" in (btn.inner_text() or ""):
            return "已签到 · 激活续期"
        time.sleep(1)
    return None


def get_streak_text(page):
    """抓"连续签到 N 天 · M 积分"那行, 有就打印."""
    el = page.get_by_text(re.compile(r"连续签到\s*\d+\s*天"))
    if el.count() > 0 and el.first.is_visible():
        return el.first.inner_text().strip()
    return ""


def main():
    email = os.environ.get("MCII_EMAIL", "").strip()
    password = os.environ.get("MCII_PASSWORD", "").strip()
    if not email or not password:
        log("错误: 环境变量 MCII_EMAIL / MCII_PASSWORD 没设置")
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.set_default_timeout(20000)
        try:
            log(f"打开 {BASE_URL}")
            page.goto(BASE_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            btn = find_checkin_button(page)
            if btn is None:
                do_login(page, email, password)
            else:
                log("已登录, 直接签到")

            # 签到按钮不在 /nodes 页上: 它只在"我的账号"(/account, 概览页)
            # 和"我的订阅"页内联渲染, 所以登录后跳到 /account 再找
            log(f"打开 {ACCOUNT_URL}")
            page.goto(ACCOUNT_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            btn = wait_for_checkin_button(page, timeout=30)
            if btn is None:
                raise RuntimeError("我的账号页 30 秒内没出现签到按钮")

            label = (btn.inner_text() or "").strip()
            log(f"点击签到按钮[{label}]")
            btn.click()

            result = wait_for_success(page, timeout=15)
            if result is None and click_confirm_if_present(page):
                result = wait_for_success(page, timeout=15)
            if result is None:
                raise RuntimeError("点击签到后 15 秒内没看到成功提示")

            streak = get_streak_text(page)
            log(f"签到成功: {result}" + (f" | {streak}" if streak else ""))
            page.wait_for_timeout(1500)
            page.screenshot(path=CHECKIN_PNG)
            log(f"截图已保存: {CHECKIN_PNG}")
            return 0
        except Exception as e:
            log(f"失败: {e}")
            try:
                page.screenshot(path=ERROR_PNG)
                log(f"失败截图已保存: {ERROR_PNG}")
            except Exception:
                pass
            return 1
        finally:
            browser.close()


if __name__ == "__main__":
    sys.exit(main())
