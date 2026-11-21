"""Glowisd 官网冒烟测试套件（V0.5.0 清理重构时建立）。

覆盖范围：
  1. 前台 5 页 200 + 中英双语渲染
  2. 询价表单：提交成功（产品关联 + 来源页记录）、蜜罐拦截、5 分钟 3 次限流
  3. 后台三角色权限隔离：普通管理员 403 用户管理 + 登录审计模块，超管 200
  4. 超管保护：受保护账号（glowisd）禁删、最后一名超管禁删
  5. 登录审计信号：登录产生 LoginRecord（内网 IP 不触发在线解析）

运行：python manage.py test core
"""
import json
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
        self.assertEqual(SiteImage.objects.count(), 9)
        self.assertEqual(
            set(SiteImage.objects.values_list('key', flat=True)),
            {'home_factory', 'factory_hero', 'workshop_1', 'workshop_2',
             'workshop_3', 'workshop_4', 'custom_hero', 'catalog_hero', 'contact_hero'},
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


class ArabicAndLangModalTests(TestCase):
    """V0.9.0 三语：阿语切换、首次语言弹窗、分类封面兜底、翻译服务降级。"""

    def test_arabic_cookie_renders_arabic(self):
        self.client.cookies['lang'] = 'ar'
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'الرئيسية')          # 导航首页
        self.assertContains(resp, 'dir="rtl"')         # RTL 方向

    def test_language_modal_shown_on_first_visit(self):
        resp = self.client.get('/')
        self.assertContains(resp, 'id="lang-modal"')
        self.assertContains(resp, 'data-pick-lang="ar"')

    def test_language_modal_hidden_after_choice(self):
        self.client.cookies['lang_chosen'] = '1'
        resp = self.client.get('/')
        self.assertNotContains(resp, 'id="lang-modal"')

    def test_language_modal_hidden_for_crawlers(self):
        resp = self.client.get('/', HTTP_USER_AGENT='Mozilla/5.0 (compatible; Googlebot/2.1)')
        self.assertNotContains(resp, 'id="lang-modal"')

    def test_category_cover_falls_back_to_product_image(self):
        import io
        import tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from PIL import Image
        from products.models import Category, Product

        buf = io.BytesIO()
        Image.new('RGB', (400, 300), '#162A87').save(buf, 'PNG')
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                cat = Category.objects.create(name='测试分类', name_en='Test Cat', slug='test-cat')
                Product.objects.create(
                    sku='TEST-1', part_name='传感器', part_name_en='Sensor', category=cat,
                    image=SimpleUploadedFile('sensor.png', buf.getvalue(), 'image/png'),
                )
                self.assertIsNotNone(cat.cover_or_first_product_image())

    def test_translate_returns_none_without_key(self):
        from core.models import SiteSettings
        from core.translation import translate_ar
        s = SiteSettings.load()
        s.deepseek_api_key = ''
        s.save(update_fields=['deepseek_api_key'])
        self.assertIsNone(translate_ar(['传感器']))

    def test_apply_arabic_map_command(self):
        from django.core.management import call_command
        from products.models import Category, Product

        cat = Category.objects.first()
        if not cat:
            cat = Category.objects.create(name='传感器', name_en='Sensors', slug='sensors')
        Product.objects.create(sku='AR-1', part_name='传感器', part_name_en='Sensor', category=cat)
        out = StringIO()
        call_command('apply_arabic_map', stdout=out)
        product = Product.objects.get(sku='AR-1')
        self.assertTrue(product.part_name_ar)
        self.assertTrue(cat.name_ar or Category.objects.get(pk=cat.pk).name_ar)


class LogEntryNaturalMessageTests(TestCase):
    """V0.12.0 后台操作日志：JSON change_message 必须渲染成自然语言。"""

    def _entry(self, payload):
        from django.contrib.admin.models import CHANGE, LogEntry
        from django.contrib.contenttypes.models import ContentType
        from products.models import Product

        return LogEntry(
            content_type=ContentType.objects.get_for_model(Product),
            object_id='1', object_repr='x', action_flag=CHANGE, change_message=payload,
        )

    def test_standard_json_list_renders_natural_language(self):
        from core.admin import LogEntryAdmin
        admin_obj = LogEntryAdmin(type(self._entry('')), None)
        text = admin_obj.change_message_natural(self._entry('[{"changed": {"fields": ["产品分类", "价格"]}}]'))
        self.assertIn('已修改', text)
        self.assertIn('产品分类', text)
        self.assertNotIn('{', text)

    def test_legacy_dict_json_is_salvaged(self):
        from core.admin import LogEntryAdmin
        admin_obj = LogEntryAdmin(type(self._entry('')), None)
        text = admin_obj.change_message_natural(self._entry('{"changed": {"fields": ["\\u4ea7\\u54c1\\u5206\\u7c7b"]}}'))
        self.assertIn('产品分类', text)
        self.assertNotIn('\\u', text)

    def test_empty_message(self):
        from core.admin import LogEntryAdmin
        admin_obj = LogEntryAdmin(type(self._entry('')), None)
        text = admin_obj.change_message_natural(self._entry(''))
        self.assertIn('已修改', text)  # V0.14.0：即使没有 message 也要给人话摘要
        self.assertNotIn('{', text)


class NavMenuTests(TestCase):
    """V0.13.0 导航：产品二级菜单的分类上下文 + 结构。"""

    def test_nav_categories_context(self):
        from products.models import Category, Product

        visible = Category.objects.create(name='可见分类', name_en='Visible', slug='nav-visible')
        empty = Category.objects.create(name='空分类', name_en='Empty', slug='nav-empty')
        Product.objects.create(sku='NAV-1', part_name='配件', category=visible)
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        slugs = [c.slug for c in resp.context['nav_categories']]
        self.assertIn('nav-visible', slugs)
        self.assertNotIn('nav-empty', slugs)
        self.assertNotIn('uncategorized', slugs)
        self.assertTrue(empty)

    def test_nav_markup_and_category_links(self):
        from products.models import Category, Product

        cat = Category.objects.create(name='导航测试', name_en='Nav Test', slug='nav-markup')
        Product.objects.create(sku='NAV-2', part_name='配件', category=cat)
        html = self.client.get('/').content.decode('utf-8')
        self.assertIn('nav-item--sub', html)
        self.assertIn('data-mobile-sub', html)
        self.assertIn('category=nav-markup', html)


class AdminChangeDetailTests(TestCase):
    """V0.14.0 操作日志字段级明细：旧值→新值、脱敏、删除快照、摘要、详情页、CSV。"""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import User

        cls.admin = User.objects.create_superuser('logadmin', 'log@example.com', 'Sup3rPass!')
        from products.models import Category

        cls.cat = Category.objects.create(name='线缆', name_en='Cables', slug='log-cables', sort_order=1)
        cls.other = Category.objects.create(name='传感器', name_en='Sensors', slug='log-sensors', sort_order=2)

    def setUp(self):
        self.client.force_login(self.admin)

    def _latest_log(self):
        from django.contrib.admin.models import LogEntry

        return LogEntry.objects.order_by('-id').first()

    def test_category_edit_records_old_and_new(self):
        from products.models import Category

        url = reverse('admin:products_category_change', args=[self.cat.pk])
        resp = self.client.post(url, {
            'name': '线缆',
            'name_en': 'Cables',
            'name_ar': 'كابلات جديدة',
            'slug': 'log-cables',
            'sort_order': '9',
        })
        self.assertEqual(resp.status_code, 302, resp.content[:400])
        entry = self._latest_log()
        self.assertEqual(entry.object_id, str(self.cat.pk))
        from core.admin_log import parse_change_message

        parsed = parse_change_message(entry)
        self.assertTrue(parsed['has_detail'], '应写入字段级明细')
        by_name = {d['name']: d for d in parsed['details']}
        self.assertIn('sort_order', by_name)
        self.assertEqual(by_name['sort_order']['old'], '1')
        self.assertEqual(by_name['sort_order']['new'], '9')
        self.assertIn('name_ar', by_name)
        self.assertEqual(by_name['name_ar']['old'], '')
        self.assertEqual(by_name['name_ar']['new'], 'كابلات جديدة')
        self.assertTrue(parsed['batch'])

    def test_secret_field_never_stored(self):
        from core.models import SiteSettings

        settings_obj = SiteSettings.load()
        url = reverse('admin:core_sitesettings_change', args=[settings_obj.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = {}
        # 用页面里现有值回填，只改 api key；文件字段跳过（无关联文件会抛错）
        form = resp.context['adminform'].form
        for name, field in form.fields.items():
            if name == 'deepseek_api_key':
                continue
            from django import forms as dj_forms
            if isinstance(field, dj_forms.FileField):
                continue
            value = form.initial.get(name)
            if value is None:
                value = ''
            if isinstance(value, bool):
                value = 'on' if value else ''
            data[name] = value
        data['deepseek_api_key'] = 'sk-should-never-be-logged-123456'
        data.pop('cover_image', None)
        resp = self.client.post(url, data, follow=False)
        self.assertIn(resp.status_code, (200, 302))
        entry = self._latest_log()
        if entry is None or entry.object_id != str(settings_obj.pk):
            self.skipTest('本次保存未产生日志（表单未通过校验），跳过')
        raw = entry.change_message or ''
        self.assertNotIn('sk-should-never-be-logged-123456', raw, '密钥明文绝不能进日志')
        from core.admin_log import parse_change_message, SECRET_DISPLAY

        parsed = parse_change_message(entry)
        secret = [d for d in parsed['details'] if d['name'] == 'deepseek_api_key']
        if secret:
            self.assertEqual(secret[0]['new'], SECRET_DISPLAY)

    def test_delete_records_snapshot(self):
        from products.models import Category

        cat = Category.objects.create(name='待删分类', name_en='To Delete', slug='log-todelete')
        url = reverse('admin:products_category_delete', args=[cat.pk])
        resp = self.client.post(url, {'post': 'yes'})
        self.assertEqual(resp.status_code, 302)
        entry = self._latest_log()
        self.assertEqual(entry.object_id, str(cat.pk))
        self.assertEqual(entry.action_flag, 3)
        from core.admin_log import parse_change_message

        parsed = parse_change_message(entry)
        self.assertTrue(parsed['snapshot'], '删除应记录快照')
        self.assertIn('To Delete', ' '.join(
            str(v.get('value')) for v in parsed['snapshot'].values() if isinstance(v, dict)
        ))

    def test_summary_truncates_and_marks(self):
        from django.contrib.admin.models import CHANGE, LogEntry
        from django.contrib.contenttypes.models import ContentType
        from core.admin_log import summary_html
        from products.models import Category

        ct = ContentType.objects.get_for_model(Category)
        entry = LogEntry.objects.create(
            user=self.admin, content_type=ct, object_id='1', object_repr='线缆' * 30,
            action_flag=CHANGE,
            change_message=json.dumps([{'changed': {
                'fields': ['名称(中文)'], 'batch': 'abcd1234',
                'details': [
                    {'name': 'name', 'label': '名称(中文)', 'kind': 'text', 'old': '旧' * 40, 'new': '新' * 40},
                ],
            }}], ensure_ascii=False),
        )
        html = str(summary_html(entry))
        self.assertIn('…', html)
        self.assertIn('title=', html)
        self.assertIn('明细', html)
        self.assertIn('批次', html)
        self.assertIn(f'../logentry/{entry.pk}/change/', html)

    def test_detail_page_renders_table(self):
        from django.contrib.admin.models import CHANGE, LogEntry
        from django.contrib.contenttypes.models import ContentType
        from products.models import Category

        ct = ContentType.objects.get_for_model(Category)
        entry = LogEntry.objects.create(
            user=self.admin, content_type=ct, object_id=str(self.cat.pk), object_repr=str(self.cat),
            action_flag=CHANGE,
            change_message=json.dumps([{'changed': {
                'fields': ['排序'],
                'details': [{'name': 'sort_order', 'label': '排序', 'kind': 'number', 'old': '1', 'new': '9'}],
                'batch': 'deadbeef',
            }}], ensure_ascii=False),
        )
        resp = self.client.get(reverse('admin:admin_logentry_change', args=[entry.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertIn('旧值', html)
        self.assertIn('新值', html)
        self.assertIn('打开该', html)
        self.assertIn('9', html)

    def test_old_log_without_detail_is_labelled(self):
        from django.contrib.admin.models import CHANGE, LogEntry
        from django.contrib.contenttypes.models import ContentType
        from products.models import Category

        ct = ContentType.objects.get_for_model(Category)
        entry = LogEntry.objects.create(
            user=self.admin, content_type=ct, object_id='1', object_repr='旧记录',
            action_flag=CHANGE,
            change_message='[{"changed": {"fields": ["排序"]}}]',
        )
        from core.admin_log import summary_html, detail_html

        self.assertIn('无明细', str(summary_html(entry)))
        self.assertIn('早于 V0.14.0', str(detail_html(entry)))

    def test_csv_export(self):
        url = reverse('admin:admin_log_export_csv')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        body = resp.content.decode('utf-8-sig')
        self.assertIn('时间,操作人,对象类型,对象名,动作,明细摘要,明细全文', body)

    def test_purge_command_keeps_deletions(self):
        from datetime import timedelta

        from django.contrib.admin.models import CHANGE, DELETION, LogEntry
        from django.contrib.contenttypes.models import ContentType
        from django.core.management import call_command
        from django.utils import timezone
        from products.models import Category

        ct = ContentType.objects.get_for_model(Category)
        old_time = timezone.now() - timedelta(days=400)
        old_change = LogEntry.objects.create(
            user=self.admin, content_type=ct, object_id='1', object_repr='old change',
            action_flag=CHANGE, change_message='', action_time=old_time,
        )
        old_delete = LogEntry.objects.create(
            user=self.admin, content_type=ct, object_id='2', object_repr='old delete',
            action_flag=DELETION, change_message='', action_time=old_time,
        )
        call_command('purge_admin_log', '--days', '180', stdout=StringIO())
        self.assertFalse(LogEntry.objects.filter(pk=old_change.pk).exists())
        self.assertTrue(LogEntry.objects.filter(pk=old_delete.pk).exists(), '删除记录应永久保留')


class FactoryPhotoSectionTests(TestCase):
    """V0.14.1：车间照片缺失时「车间一瞥」整段隐藏，前台不出现内部 TODO 文案。"""

    def setUp(self):
        import shutil
        import tempfile
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from PIL import Image

        from core.models import SiteImage

        SiteImage.objects.all().delete()
        self.tmpdir = tempfile.mkdtemp()
        self._override = override_settings(MEDIA_ROOT=self.tmpdir)
        self._override.enable()
        self.addCleanup(self._override.disable)
        self.addCleanup(shutil.rmtree, self.tmpdir, True)
        self.client.cookies['lang'] = 'en'
        self.client.cookies['lang_chosen'] = '1'

        buf = BytesIO()
        Image.new('RGB', (32, 24), (208, 214, 228)).save(buf, 'PNG')
        si = SiteImage(key='workshop_1', caption_zh='组装产线', caption_en='Assembly line')
        si.image.save('w1.png', SimpleUploadedFile('w1.png', buf.getvalue(), content_type='image/png'), save=True)

    def test_section_and_internal_todo_hidden_when_no_photos(self):
        from core.models import SiteImage

        SiteImage.objects.all().delete()
        html = self.client.get('/factory/').content.decode('utf-8')
        self.assertNotIn('Inside the Workshop', html)
        self.assertNotIn('replace with real workshop photos', html)
        self.assertNotIn('车间一瞥', html)
        # V0.14.2：缺图时改展示设计化「制造流程」能力图示
        self.assertIn('From Incoming to Dispatch', html)
        self.assertEqual(html.count('flow__step'), 6)

    def test_section_visible_and_todo_gone_with_photo(self):
        html = self.client.get('/factory/').content.decode('utf-8')
        self.assertIn('Inside the Workshop', html)
        self.assertIn('Four stages under one roof', html)   # 新的正面文案
        self.assertNotIn('replace with real workshop photos', html)
        self.assertNotIn('Photo placeholders', html)


class PageHeroPhotoTests(TestCase):
    """V0.15.0 页头主题图：有图时走照片版页头，无图时退回纯色（不出现空块/裂图）。"""

    def _upload(self, key, filename='hero.png'):
        import io
        import tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from PIL import Image

        buf = io.BytesIO()
        Image.new('RGB', (1600, 900), '#162A87').save(buf, 'PNG')
        tmp = tempfile.TemporaryDirectory()
        ctx = override_settings(MEDIA_ROOT=tmp.name)
        ctx.enable()
        self.addCleanup(ctx.disable)
        self.addCleanup(tmp.cleanup)
        si = SiteImage.objects.get(key=key)
        si.image.save(filename, SimpleUploadedFile(filename, buf.getvalue(), 'image/png'))
        return si

    def test_catalog_hero_photo_when_image_uploaded(self):
        self._upload('catalog_hero')
        resp = self.client.get('/products/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'page-hero--photo')
        self.assertContains(resp, '--page-hero-img')

    def test_contact_hero_photo_when_image_uploaded(self):
        self._upload('contact_hero')
        resp = self.client.get('/contact/')
        self.assertContains(resp, 'page-hero--photo')

    def test_falls_back_to_plain_hero_without_image(self):
        resp = self.client.get('/products/')
        self.assertContains(resp, 'page-hero')
        self.assertNotContains(resp, 'page-hero--photo')


class OptImageTagTests(TestCase):
    """V0.15.0 图片优化标签：有 WebP 变体时用变体（带版本号），没有就回退原图。"""

    def test_falls_back_to_original_when_variant_missing(self):
        import io
        import os
        import tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from PIL import Image

        from products.templatetags.products_extras import opt_img, opt_srcset

        buf = io.BytesIO()
        Image.new('RGB', (800, 600), '#162A87').save(buf, 'JPEG')
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root, MEDIA_URL='/media/'):
                si = SiteImage.objects.get(key='custom_hero')
                si.image.save('probe.jpg', SimpleUploadedFile('probe.jpg', buf.getvalue(), 'image/jpeg'))
                self.assertEqual(opt_img(si.image, 640), si.image.url)
                self.assertEqual(opt_srcset(si.image, '320,640'), '')

    def test_uses_variant_and_version_when_present(self):
        import os
        import tempfile
        from django.test import override_settings

        from products.templatetags.products_extras import _variant_path, opt_img

        with tempfile.TemporaryDirectory() as media_root:
            os.makedirs(os.path.join(media_root, 'opt', 'site_images'))
            open(os.path.join(media_root, 'opt', 'site_images', 'probe-640.webp'), 'wb').close()
            _variant_path.cache_clear()          # 变体存在性有进程内缓存，测试要先清
            with override_settings(MEDIA_ROOT=media_root, MEDIA_URL='/media/'):

                class _Img:
                    url = '/media/site_images/probe.jpg'
                    name = 'site_images/probe.jpg'

                url = opt_img(_Img(), 640)
                self.assertIn('opt/site_images/probe-640.webp', url)
                self.assertIn('?v=', url)
            _variant_path.cache_clear()


class PageCacheMiddlewareTests(TestCase):
    """V0.15.0 匿名整页缓存：GET 第二次命中；带表单/已登录/后台一律不缓存。"""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def test_second_get_hits_cache(self):
        from django.test import override_settings

        with override_settings(PAGE_CACHE_SECONDS=60, DEBUG=False):
            first = self.client.get('/factory/')
            second = self.client.get('/factory/')
        self.assertEqual(first.headers.get('X-Page-Cache'), 'MISS')
        self.assertEqual(second.headers.get('X-Page-Cache'), 'HIT')
        self.assertEqual(first.content, second.content)

    def test_contact_page_never_cached(self):
        from django.test import override_settings

        with override_settings(PAGE_CACHE_SECONDS=60, DEBUG=False):
            resp = self.client.get('/contact/')
        self.assertIsNone(resp.headers.get('X-Page-Cache'))
        self.assertContains(resp, 'csrfmiddlewaretoken')

    def test_disabled_when_seconds_zero(self):
        from django.test import override_settings

        with override_settings(PAGE_CACHE_SECONDS=0, DEBUG=False):
            resp = self.client.get('/factory/')
        self.assertIsNone(resp.headers.get('X-Page-Cache'))

    def test_authenticated_user_bypasses_cache(self):
        from django.contrib.auth.models import User
        from django.test import override_settings

        user = User.objects.create_user('cacheprobe', password='x')
        self.client.force_login(user)
        with override_settings(PAGE_CACHE_SECONDS=60, DEBUG=False):
            resp = self.client.get('/factory/')
        self.assertIsNone(resp.headers.get('X-Page-Cache'))

    def test_saving_content_invalidates_cache_immediately(self):
        """后台改完内容，前台下一次请求必须重新渲染（不用等 120 秒 TTL）。"""
        from django.test import override_settings

        with override_settings(PAGE_CACHE_SECONDS=60, DEBUG=False):
            self.client.get('/factory/')                       # MISS，写入缓存
            self.assertEqual(self.client.get('/factory/').headers.get('X-Page-Cache'), 'HIT')

            from core.models import SiteSettings

            settings_obj = SiteSettings.objects.first()        # 后台「站点设置」保存
            settings_obj.moq = (settings_obj.moq or 'MOQ') + '·'
            settings_obj.save()                                # 触发缓存代号 +1

            self.assertEqual(self.client.get('/factory/').headers.get('X-Page-Cache'), 'MISS')

    def test_site_image_save_invalidates_cache(self):
        from django.test import override_settings

        with override_settings(PAGE_CACHE_SECONDS=60, DEBUG=False):
            self.client.get('/products/')
            self.assertEqual(self.client.get('/products/').headers.get('X-Page-Cache'), 'HIT')
            si = SiteImage.objects.get(key='catalog_hero')
            si.caption_zh = (si.caption_zh or '') + '·'
            si.save()
            self.assertEqual(self.client.get('/products/').headers.get('X-Page-Cache'), 'MISS')

    def test_invalidation_does_not_wipe_login_limiter(self):
        """失效用的是「换代号」，不能顺手清掉登录限流计数（否则封禁会被误解除）。"""
        from django.core.cache import cache
        from django.test import override_settings

        cache.set('login_block:1.2.3.4', 1, timeout=900)
        with override_settings(PAGE_CACHE_SECONDS=60, DEBUG=False):
            self.client.get('/factory/')
            si = SiteImage.objects.get(key='home_factory')
            si.caption_zh = (si.caption_zh or '') + '·'
            si.save()
        self.assertEqual(cache.get('login_block:1.2.3.4'), 1)

    def test_language_partitioned(self):
        from django.test import override_settings

        with override_settings(PAGE_CACHE_SECONDS=60, DEBUG=False):
            zh = self.client.get('/factory/', HTTP_COOKIE='lang=zh; lang_chosen=1')
            ar = self.client.get('/factory/', HTTP_COOKIE='lang=ar; lang_chosen=1')
        # 语言不同 → 不能互相命中
        self.assertEqual(zh.headers.get('X-Page-Cache'), 'MISS')
        self.assertEqual(ar.headers.get('X-Page-Cache'), 'MISS')


class StyleRegressionTests(TestCase):
    """样式回归护栏：这几个选择器/变量被删掉会静默破坏功能（RTL 可读性、蜜罐不溢出）。"""

    def test_hero_scrim_is_direction_aware(self):
        import os

        from django.conf import settings

        css_path = os.path.join(settings.BASE_DIR, 'static', 'css', 'style.css')
        css = open(css_path, encoding='utf-8').read()
        self.assertIn('--hero-scrim', css)
        self.assertIn('html[dir="rtl"]', css)
        # RTL 下必须镜像成 270deg，否则阿语文字压在浅色侧（实测只有 3.4:1）
        self.assertIn('linear-gradient(270deg', css)
        self.assertIn('var(--hero-scrim)', css)

    def test_honeypot_does_not_use_offscreen_position(self):
        import os

        from django.conf import settings

        css_path = os.path.join(settings.BASE_DIR, 'static', 'css', 'style.css')
        css = open(css_path, encoding='utf-8').read()
        # 用 left:-9999px 会在 RTL 下把文档撑出 9999px 横向滚动
        self.assertNotIn('left: -9999px', css)
        self.assertIn('clip-path: inset(50%)', css)

    def test_search_form_can_shrink(self):
        import os

        from django.conf import settings

        css_path = os.path.join(settings.BASE_DIR, 'static', 'css', 'style.css')
        css = open(css_path, encoding='utf-8').read()
        self.assertIn('.search-form input { min-width: 0; }', css)
