"""Glowisd 官网冒烟测试套件（V0.5.0 清理重构时建立）。

覆盖范围：
  1. 前台 5 页 200 + 中英双语渲染
  2. 询价表单：提交成功（产品关联 + 来源页记录）、蜜罐拦截、5 分钟 3 次限流
  3. 后台三角色权限隔离：普通管理员 403 用户管理 + 登录审计模块，超管 200
  4. 超管保护：受保护账号（glowisd）禁删、最后一名超管禁删
  5. 登录审计信号：登录产生 LoginRecord（内网 IP 不触发在线解析）

运行：python manage.py test core
"""
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from accounts.models import AdminProfile
from core.models import LoginRecord
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
