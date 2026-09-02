"""登录审计信号：登录成功/失败时写 LoginRecord + 登录限流计数。

- 审计上下文提取（UA 解析 + IP 双引擎地区解析）见 core/audit.py；
- 登录限流计数逻辑（cache 双维度计数/封禁/清除）见 core/middleware.py，本文件只在
  登录成功/失败信号里调用它们，避免信号与中间件各自维护一套 key。
"""
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .audit import extract_request_context
from .middleware import bump_login_failures, clear_login_failures
from .models import LoginRecord


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """登录成功：写审计记录 + 清除该 IP/账号的失败计数。"""
    if not user or not request:
        return

    # 限流：登录成功清除该 IP 与 username 的失败计数（封禁标记等自然过期）
    clear_login_failures(request, user.username)

    ctx = extract_request_context(request)
    LoginRecord.objects.create(
        user=user,
        username_attempted=user.username,
        success=True,
        **ctx,
    )


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request=None, **kwargs):
    """登录失败：写审计记录 + 按 IP/username 计数（满 5 次封禁该 IP）。"""
    credentials = credentials or {}
    username = credentials.get('username', '') or ''

    # 限流：失败计数（request 为空时仅按 username 计数，不封禁）
    bump_login_failures(request, username)

    ctx = extract_request_context(request)
    LoginRecord.objects.create(
        user=None,
        username_attempted=username,
        success=False,
        fail_reason='用户不存在' if not username else '密码错误或用户不存在',
        **ctx,
    )
