"""登录审计信号：登录成功/失败时写入 LoginRecord。

审计上下文提取逻辑（UA 解析 + IP 双引擎地区解析）见 core/audit.py。
"""
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .audit import extract_request_context
from .models import LoginRecord


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """登录成功时，记录用户名、IP、设备、系统、浏览器与登录地区。"""
    if not user or not request:
        return

    ctx = extract_request_context(request)
    LoginRecord.objects.create(
        user=user,
        username_attempted=user.username,
        success=True,
        **ctx,
    )


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request=None, **kwargs):
    """登录失败时，记录尝试用户名、失败原因、IP、设备、系统、浏览器与地区。

    失败登录没有 User 对象，user 置空；尝试用户名从 credentials 取。
    """
    credentials = credentials or {}
    username = credentials.get('username', '') or ''

    ctx = extract_request_context(request)
    LoginRecord.objects.create(
        user=None,
        username_attempted=username,
        success=False,
        fail_reason='用户不存在' if not username else '密码错误或用户不存在',
        **ctx,
    )
