from django.contrib.auth.models import User


def is_super_admin(user):
    """判断用户是否拥有「超级管理员」角色。

    无 admin_profile（未初始化角色）时返回 False，不抛异常。
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    profile = getattr(user, 'admin_profile', None)
    if profile is None:
        return False
    return profile.role == 'super_admin'
