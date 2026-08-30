from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import LoginRecord


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """管理员登录后台时，记录 IP 与设备信息。"""
    if not user or not request:
        return
    # 生产环境经 nginx 反代，真实 IP 在 X-Forwarded-For 头
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
    ua = request.META.get('HTTP_USER_AGENT', '')[:500]
    LoginRecord.objects.create(user=user, ip_address=ip or None, user_agent=ua)
