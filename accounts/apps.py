from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = '账户与权限'

    def ready(self):
        # 接管 User 后台：替换 django.contrib.auth 默认注册的 UserAdmin，
        # 并卸载默认 Group 后台（侧边栏不再显示「组」菜单）。
        from django.contrib import admin
        from django.contrib.admin.sites import AlreadyRegistered, NotRegistered
        from django.contrib.auth.models import Group, User

        from .admin import CustomUserAdmin

        try:
            admin.site.unregister(User)
        except NotRegistered:
            pass
        try:
            admin.site.register(User, CustomUserAdmin)
        except AlreadyRegistered:
            pass

        try:
            admin.site.unregister(Group)
        except NotRegistered:
            pass
