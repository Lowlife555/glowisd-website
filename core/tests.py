"""Glowisd 官网冒烟测试套件（V0.5.0 清理重构时建立）。

覆盖范围：
  1. 前台 5 页 200 + 中英双语渲染
  2. 询价表单：提交成功（产品关联 + 来源页记录）、蜜罐拦截、5 分钟 3 次限流
  3. 后台三角色权限隔离：普通管理员 403 用户管理 + 登录审计模块，超管 200
  4. 超管保护：受保护账号（glowisd）禁删、最后一名超管禁删
  5. 登录审计信号：登录产生 LoginRecord（内网 IP 不触发在线解析）

运行：python manage.py test core
"""
from datetime import datetime, timezone as dt_timezone
from io import StringIO

from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import AdminProfile
from core.models import LoginRecord, SiteImage
from products.models import Category, ContactMessage, Product


class FrontendPagesTests(TestCase):
    """前台 5 页 + 双语渲染。"""

    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(name='传感器', name_en='Sensors', slug='sensors')
        cls.product = Product.objects.create(
            sku='GW-TEST-001', pn='PN-001', part_name='测试传感器', part_name_en='Test Sensor',
            category=cat, image='',
        )

    def test_five_pages_zh(self):
        self.client.cookies['lang'] = 'zh'
        urls = [
            '/', '/products/', f'/products/{self.product.pk}/',
            '/factory/', '/custom/', '/contact/',
        ]
        for url in urls:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200, f'{url} 应返回 200')

    def test_five_pages_en(self):
        self.client.cookies['lang'] = 'en'
        urls = [
            '/', '/products/', f'/products/{self.product.pk}/',
            '/factory/', '/custom/', '/contact/',
        ]
        for url in urls:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200, f'{url} 应返回 200')

    def test_bilingual_rendering(self):
        self.client.cookies['lang'] = 'zh'
        zh_home = self.client.get('/').content.decode('utf-8')
        self.assertIn('产品', zh_home)
        self.assertIn('保留所有权利', zh_home)

        self.client.cookies['lang'] = 'en'
        en_home = self.client.get('/').content.decode('utf-8')
        self.assertIn('Products', en_home)
        self.assertIn('All rights reserved', en_home)

    def test_product_detail_renders_sku(self):
        resp = self.client.get(f'/products/{self.product.pk}/')
        self.assertContains(resp, 'GW-TEST-001')


class ContactFormTests(TestCase):
    """询价表单：提交 / 蜜罐 / 限流 / 产品关联。"""

    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(name='传感器', name_en='Sensors', slug='sensors')
        cls.product = Product.objects.create(
            sku='GW-INQ-001', pn='PN-002', part_name='询价测试', part_name_en='Inquiry Test',
            category=cat, image='',
        )

    def _payload(self, **kw):
        data = {
            'name': '测试客户',
            'email': 'test@example.com',
            'message': '请报价，数量 100 件。',
            'company': '测试公司',
            'phone': '13800000000',
            'country': '中国',
            'category': '',
            'product': '',
        }
        data.update(kw)
        return data

    def test_submit_success_with_product_link(self):
        resp = self.client.post('/contact/', self._payload(product='GW-INQ-001'))
        self.assertRedirects(resp, '/contact/?ok=1')
        msg = ContactMessage.objects.get(name='测试客户')
        self.assertEqual(msg.inquired_product_id, self.product.pk)
        self.assertEqual(msg.source_page, 'product_detail:GW-INQ-001')
        self.assertEqual(msg.status, 'new')

    def test_submit_without_product_records_contact_page(self):
        self.client.post('/contact/', self._payload())
        msg = ContactMessage.objects.get(name='测试客户')
        self.assertEqual(msg.source_page, 'contact_page')
        self.assertIsNone(msg.inquired_product_id)

    def test_honeypot_silently_ignored(self):
        before = ContactMessage.objects.count()
        resp = self.client.post('/contact/', self._payload(website='spam-bot-fill'))
        self.assertRedirects(resp, '/contact/?ok=1')
        self.assertEqual(ContactMessage.objects.count(), before, '蜜罐提交不应入库')

    def test_rate_limit_3_per_5min(self):
        for i in range(3):
            resp = self.client.post('/contact/', self._payload(email=f'user{i}@example.com'))
            self.assertEqual(resp.status_code, 302, f'第 {i + 1} 次提交应成功')
        resp = self.client.post('/contact/', self._payload(email='user4@example.com'))
        self.assertEqual(resp.status_code, 429, '第 4 次提交应触发限流 429')
        self.assertEqual(ContactMessage.objects.count(), 3, '限流后不应再入库')


class AdminPermissionTests(TestCase):
    """后台三角色权限隔离 + 超管保护 + 登录审计。"""

    @classmethod
    def setUpTestData(cls):
        # 受保护超管（模拟 glowisd）
        cls.super_admin = User.objects.create_superuser('glowisd', 'g@example.com', 'Sup3rPass!')
        AdminProfile.objects.create(user=cls.super_admin, role='super_admin')

        # 普通管理员：is_staff + admin 角色 + 产品/轮播/询价权限（无 auth/audit 权限）
        cls.normal_admin = User.objects.create_user('worker', 'w@example.com', 'Adm1nPass!', is_staff=True)
        AdminProfile.objects.create(user=cls.normal_admin, role='admin')
        perms = Permission.objects.filter(
            content_type__app_label__in=('products', 'core'),
            codename__in=(
                'view_product', 'change_product', 'add_product', 'delete_product',
                'view_category', 'view_contactmessage', 'change_contactmessage',
                'view_heroslide', 'change_heroslide',
            ),
        )
        cls.normal_admin.user_permissions.set(perms)

    def test_normal_admin_403_user_management_and_audit(self):
        self.client.force_login(self.normal_admin)
        for url in ('/admin/auth/user/', '/admin/core/loginrecord/', '/admin/admin/logentry/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403, f'{url} 应 403')
        # 产品管理正常可用
        self.assertEqual(self.client.get('/admin/products/product/').status_code, 200)

    def test_super_admin_can_access_management_and_audit(self):
        self.client.force_login(self.super_admin)
        for url in ('/admin/auth/user/', '/admin/core/loginrecord/', '/admin/admin/logentry/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200, f'{url} 应 200')

    def test_admin_sidebar_menu_by_role(self):
        """侧边栏菜单可见项：超管含管理员中心（登录记录），普通管理员不含。"""
        self.client.force_login(self.super_admin)
        su_home = self.client.get('/admin/').content.decode('utf-8')
        self.assertIn('/admin/core/loginrecord/', su_home, '超管菜单应含登录记录入口')

        self.client.force_login(self.normal_admin)
        na_home = self.client.get('/admin/').content.decode('utf-8')
        self.assertNotIn('/admin/core/loginrecord/', na_home, '普通管理员菜单不应含登录记录')
        self.assertNotIn('/admin/auth/user/', na_home, '普通管理员菜单不应含用户管理')

    def test_protected_super_admin_cannot_be_deleted(self):
        self.client.force_login(self.super_admin)
        resp = self.client.get(f'/admin/auth/user/{self.super_admin.pk}/delete/')
        self.assertEqual(resp.status_code, 403, 'glowisd 删除确认页应 403')
        self.assertTrue(User.objects.filter(username='glowisd').exists())

    def test_last_super_admin_cannot_be_deleted(self):
        """只剩一名超管时不可删除（即使不是受保护账号）。"""
        last_one = User.objects.create_superuser('lastone', 'l@example.com', 'Sup3rPass!')
        AdminProfile.objects.create(user=last_one, role='super_admin')
        self.client.force_login(self.super_admin)
        # 两名超管时删除其中一名（非受保护）应允许
        self.assertTrue(self.client.get(f'/admin/auth/user/{last_one.pk}/delete/').status_code == 200)
        # 只剩 glowisd 一名超管：删除请求仍被拒（受保护 + 唯一超管双重保护）
        resp = self.client.get(f'/admin/auth/user/{self.super_admin.pk}/delete/')
        self.assertEqual(resp.status_code, 403)

    def test_login_creates_audit_record_without_external_call(self):
        self.client.force_login(self.super_admin)
        self.client.get('/admin/')
        records = LoginRecord.objects.filter(username_attempted='glowisd', success=True)
        self.assertTrue(records.exists(), '登录应产生审计记录')
        rec = records.order_by('-login_time').first()
        # 测试环境 REMOTE_ADDR=127.0.0.1（私有 IP）→ 不触发在线解析，region 空、is_proxy False
        self.assertEqual(rec.region, '')
        self.assertFalse(rec.is_proxy)


class LoginRateLimitTests(TestCase):
    """P1：后台登录限流（IP 失败满 5 次封禁 15 分钟）+ 安全响应头 + 首登强制改密。"""

    def setUp(self):
        cache.clear()

    def _create_admin(self, username='rluser', password='RightPass123'):
        user = User.objects.create_user(
            username, f'{username}@example.com', password, is_staff=True, is_superuser=True,
        )
        AdminProfile.objects.create(user=user, role='super_admin')
        return user

    def test_sixth_failed_login_returns_403(self):
        """连续 5 次失败后，第 6 次 POST /admin/login/ 应被限流返回 403。"""
        self._create_admin()
        for i in range(5):
            resp = self.client.post('/admin/login/', {'username': 'rluser', 'password': f'bad{i}'})
            self.assertEqual(resp.status_code, 200, f'第 {i + 1} 次失败应仍返回登录页 200')
        resp = self.client.post('/admin/login/', {'username': 'rluser', 'password': 'bad5'})
        self.assertEqual(resp.status_code, 403, '第 6 次失败应触发限流 403')

    def test_successful_login_clears_count(self):
        """4 次失败后正确密码登录成功（清计数），后续失败不再被封禁。"""
        self._create_admin()
        for i in range(4):
            self.client.post('/admin/login/', {'username': 'rluser', 'password': f'bad{i}'})
        # 第 5 次用正确密码登录成功 → 清除计数（302 跳转后台）
        resp = self.client.post('/admin/login/', {'username': 'rluser', 'password': 'RightPass123'})
        self.assertEqual(resp.status_code, 302, '正确密码应登录成功')
        # 清计数后：再失败也不会因累计到 5 次而被封（只累计到 1）
        resp = self.client.post('/admin/login/', {'username': 'rluser', 'password': 'bad-again'})
        self.assertEqual(resp.status_code, 200, '成功登录后失败计数应已清零，不应 403')

    def test_security_headers_on_home_and_admin_login(self):
        """前台首页与 /admin/login/ 响应都应含安全响应头（同源嵌入放行以兼容 simpleui iframe）。"""
        for url in ('/', '/admin/login/'):
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.headers.get('X-Frame-Options'), 'SAMEORIGIN')
                self.assertEqual(resp.headers.get('X-Content-Type-Options'), 'nosniff')
                self.assertEqual(resp.headers.get('Referrer-Policy'), 'same-origin')
                csp = resp.headers.get('Content-Security-Policy', '')
                self.assertIn("default-src 'self'", csp)
                self.assertIn("frame-ancestors 'self'", csp)

    def test_must_change_password_redirects_and_clears(self):
        """首登强制改密：must_change_password=True 时后台重定向改密页，改密后清除标记。"""
        user = self._create_admin('forced', 'OldPass123')
        profile = user.admin_profile
        profile.must_change_password = True
        profile.save(update_fields=['must_change_password'])

        self.client.force_login(user)
        # 访问后台任意页 → 重定向到改密页
        resp = self.client.get('/admin/')
        self.assertRedirects(resp, reverse('admin:password_change'), fetch_redirect_response=False)
        # 改密页/完成页不重定向（避免死循环）
        self.assertEqual(self.client.get(reverse('admin:password_change')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:password_change_done')).status_code, 200)
        # 提交改密成功（302 → password_change_done）→ 清除标记
        resp = self.client.post(reverse('admin:password_change'), {
            'old_password': 'OldPass123',
            'new_password1': 'NewPass456!',
            'new_password2': 'NewPass456!',
        })
        self.assertEqual(resp.status_code, 302)
        profile.refresh_from_db()
        self.assertFalse(profile.must_change_password, '改密成功后应清除 must_change_password')


class ConvertViewersToAdminTests(TestCase):
    """V0.6.0：历史 viewer 批量转 admin 命令（幂等）。"""

    def test_convert_viewers_to_admin_idempotent(self):
        viewer_user = User.objects.create_user('viewer1', 'v@example.com', 'Pass!123', is_staff=True)
        viewer_profile = AdminProfile.objects.create(user=viewer_user, role='viewer')

        out = StringIO()
        call_command('convert_viewers_to_admin', stdout=out)
        viewer_profile.refresh_from_db()
        self.assertEqual(viewer_profile.role, 'admin')
        self.assertIn('已转换 1 条 viewer → admin', out.getvalue())

        out2 = StringIO()
        call_command('convert_viewers_to_admin', stdout=out2)
        viewer_profile.refresh_from_db()
        self.assertEqual(viewer_profile.role, 'admin', '再跑一次不应改变已是 admin 的角色')
        self.assertIn('已转换 0 条', out2.getvalue())
        self.assertIn('跳过', out2.getvalue())


class TimezoneTests(TestCase):
    """V0.5.1 时区修复回归：DB 按 UTC 存储（USE_TZ=True），显示须转北京时间（+8）。"""

    def test_login_record_displays_beijing_time(self):
        from django.contrib import admin
        import core.admin  # noqa: F401 — 触发 @admin.register(LoginRecord) 注册

        user = User.objects.create_user('tztest', 'tz@example.com', 'Pass!123')
        rec = LoginRecord.objects.create(user=user, username_attempted='tztest', success=True)
        # 北京时间 2026-09-01 15:46:56 = UTC 07:46:56（USE_TZ=True 时 DB 存 UTC）
        utc = datetime(2026, 9, 1, 7, 46, 56, tzinfo=dt_timezone.utc)
        # update() 绕过 auto_now_add，模拟历史记录已按 UTC 落库
        LoginRecord.objects.filter(pk=rec.pk).update(login_time=utc)
        rec.refresh_from_db()

        # 模型 __str__ 应转北京时间（V0.5.1 修复点之一）
        self.assertEqual(str(rec), 'tztest @ 2026-09-01 15:46:56')
        # 后台列表时间列 formatted_time 应转北京时间（V0.5.1 修复点之二）
        admin_instance = admin.site._registry[LoginRecord]
        self.assertEqual(admin_instance.formatted_time(rec), '2026-09-01 15:46:56')

    def test_export_login_csv_uses_beijing_time(self):
        """CSV 导出时间列须转北京时间（V0.5.1 已正确，回归防回退）。"""
        from django.contrib import admin
        import core.admin  # noqa: F401 — 触发 @admin.register(LoginRecord) 注册

        user = User.objects.create_user('csvtest', 'csv@example.com', 'Pass!123')
        rec = LoginRecord.objects.create(user=user, username_attempted='csvtest', success=True)
        utc = datetime(2026, 9, 1, 7, 46, 56, tzinfo=dt_timezone.utc)
        LoginRecord.objects.filter(pk=rec.pk).update(login_time=utc)
        rec.refresh_from_db()

        admin_instance = admin.site._registry[LoginRecord]
        resp = admin_instance.export_login_csv(None, LoginRecord.objects.filter(pk=rec.pk))
        content = resp.content.decode('utf-8')
        self.assertIn('2026-09-01 15:46:56', content, 'CSV 时间列应转北京时间')

    def test_date_hierarchy_groups_by_local_date(self):
        """已确认无此问题：date_hierarchy 按北京时间（本地日期）分组。

        UTC 2026-08-31 23:30 = 北京时间 2026-09-01 07:30，dates('login_time','day')
        实测归 2026-09-01（本地日期），而非 08-31（UTC 日期）。
        """
        user = User.objects.create_user('dhtest', 'dh@example.com', 'Pass!123')
        rec = LoginRecord.objects.create(user=user, username_attempted='dhtest', success=True)
        utc = datetime(2026, 8, 31, 23, 30, 0, tzinfo=dt_timezone.utc)
        LoginRecord.objects.filter(pk=rec.pk).update(login_time=utc)

        dates = LoginRecord.objects.filter(pk=rec.pk).dates('login_time', 'day')
        self.assertIn(datetime(2026, 9, 1).date(), list(dates),
                      'date_hierarchy 应按本地日期（北京时间）分组归 9-1')


class SiteImageTests(TestCase):
    """V0.7.3 站点图片：7 个固定槽位 + 后台上传即替换前台展示。"""

    def test_slots_seeded(self):
        self.assertEqual(SiteImage.objects.count(), 7)
        self.assertEqual(
            set(SiteImage.objects.values_list('key', flat=True)),
            {'home_factory', 'factory_hero', 'workshop_1', 'workshop_2',
             'workshop_3', 'workshop_4', 'custom_hero'},
        )

    def test_uploaded_image_renders_on_factory_page(self):
        """上传 factory_hero 后，工厂页应输出该图片 URL（不再是占位图）。"""
        import io
        import tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from PIL import Image

        buf = io.BytesIO()
        Image.new('RGB', (1600, 1000), '#162A87').save(buf, 'PNG')
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                si = SiteImage.objects.get(key='factory_hero')
                si.image.save('factory-hero.png', SimpleUploadedFile(
                    'factory-hero.png', buf.getvalue(), 'image/png'))
                resp = self.client.get('/factory/')
                self.assertContains(resp, 'site_images/factory-hero.png')
                self.assertNotContains(resp, 'Factory building — placeholder photo')

    def test_no_image_falls_back_to_placeholder(self):
        """未上传图片的槽位，前台应显示占位图。"""
        resp = self.client.get('/factory/')
        self.assertContains(resp, 'placeholder-factory.svg')
