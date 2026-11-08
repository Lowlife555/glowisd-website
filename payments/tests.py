from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from products.models import PLACEHOLDER_PRICE, Category, Product

from .models import BankAccount, Order, PaymentSettings


def enable_online():
    cfg = PaymentSettings.load()
    cfg.online_enabled = True
    cfg.save()
    return cfg


class PaymentFlowTests(TestCase):
    """线下汇款（默认模式）：开关关闭在线收款时，客户只能按银行账户转账。"""

    def setUp(self):
        self.category = Category.objects.create(
            name='传感器', name_en='Sensors', slug='sensors-test',
        )
        self.product = Product.objects.create(
            sku='TEST-1', part_name='测试件', part_name_en='Test Part',
            category=self.category, price=Decimal('268.00'), currency='USD',
        )
        self.placeholder = Product.objects.create(
            sku='TEST-2', part_name='未定价件', category=self.category,
        )
        self.account = BankAccount.objects.create(
            label_zh='中国银行对公账户', label_en='Bank of China (corporate)',
            bank_name='中国银行常州分行', account_name='常州 Glowisd 科技有限公司',
            account_number='5123 4567 8901 2345', swift_code='BKCHCNBJ95B',
            currency='USD', is_active=True, sort_order=1,
        )

    def _post(self, **overrides):
        payload = {
            'name': 'Hans Müller',
            'email': 'hans@example.com',
            'quantity': '2',
            'method': 'bank_transfer',
            'country': 'Germany',
            'phone': '+49 170 0000',
            'note': '',
        }
        payload.update(overrides)
        return self.client.post(reverse('payment_start', args=[self.product.pk]), payload)

    def test_placeholder_price_defaults_to_99999(self):
        self.assertEqual(self.placeholder.price, PLACEHOLDER_PRICE)
        self.assertTrue(self.placeholder.is_placeholder_price)

    def test_placeholder_product_cannot_checkout(self):
        resp = self.client.get(reverse('payment_start', args=[self.placeholder.pk]))
        self.assertRedirects(
            resp,
            reverse('product_detail', args=[self.placeholder.pk]) + '?price=required',
        )

    def test_detail_shows_placeholder_price_without_buy_button(self):
        resp = self.client.get(reverse('product_detail', args=[self.placeholder.pk]))
        self.assertContains(resp, '99,999')
        self.assertNotContains(resp, reverse('payment_start', args=[self.placeholder.pk]))

    def test_detail_shows_order_button_for_priced_product(self):
        resp = self.client.get(reverse('product_detail', args=[self.product.pk]))
        self.assertContains(resp, reverse('payment_start', args=[self.product.pk]))
        self.assertContains(resp, '$268.00')
        self.assertContains(resp, 'bank transfer')

    def test_checkout_page_shows_bank_transfer_only(self):
        resp = self.client.get(reverse('payment_start', args=[self.product.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '银行转账')
        self.assertContains(resp, self.account.account_number)
        self.assertContains(resp, self.account.swift_code)
        # 没有在线收款时不展示 Visa / 支付宝等在线方式
        self.assertNotContains(resp, '支付宝 Alipay')

    def test_offline_order_is_created_and_redirects_to_success(self):
        resp = self._post()
        order = Order.objects.get()
        self.assertEqual(resp.status_code, 302)
        self.assertIn(order.order_no, resp['Location'])
        self.assertEqual(order.amount, Decimal('536.00'))
        self.assertEqual(order.currency, 'USD')
        self.assertEqual(order.method, 'bank_transfer')
        self.assertEqual(order.provider, 'manual')
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.sku, 'TEST-1')
        self.assertEqual(order.customer_email, 'hans@example.com')

    def test_invalid_email_rejected_without_order(self):
        resp = self._post(email='not-an-email')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_online_method_rejected_when_offline_mode(self):
        resp = self._post(method='visa')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_quantity_out_of_range_rejected(self):
        resp = self._post(quantity='0')
        self.assertEqual(resp.status_code, 400)
        resp = self._post(quantity='1000')
        self.assertEqual(resp.status_code, 400)

    def test_success_page_shows_bank_details(self):
        self._post()
        order = Order.objects.get()
        resp = self.client.get(reverse('payment_success', args=[order.order_no]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, order.order_no)
        self.assertContains(resp, '$536.00')
        self.assertContains(resp, self.account.account_number)
        self.assertContains(resp, self.account.account_name)

    def test_mark_paid_is_idempotent(self):
        self._post()
        order = Order.objects.get()
        self.assertTrue(order.mark_paid())
        self.assertFalse(order.mark_paid())
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertIsNotNone(order.paid_at)

    def test_cancel_marks_pending_order_cancelled(self):
        self._post()
        order = Order.objects.get()
        self.client.get(reverse('payment_cancel', args=[order.order_no]))
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')


class PaymentModeTests(TestCase):
    """后台「收款设置」开关直接决定前台收款方式。"""

    def setUp(self):
        self.category = Category.objects.create(name='线缆', name_en='Cables', slug='cables-test')
        self.product = Product.objects.create(
            sku='TEST-5', part_name='线缆', category=self.category, price=Decimal('99.99'),
        )
        self.account = BankAccount.objects.create(
            bank_name='ICBC', account_name='Glowisd', account_number='6222 0000 1111 2222',
            currency='CNY',
        )

    def test_default_settings_are_offline(self):
        cfg = PaymentSettings.load()
        self.assertFalse(cfg.online_enabled)
        self.assertTrue(cfg.offline_enabled)

    def test_both_switches_off_shows_unavailable(self):
        cfg = PaymentSettings.load()
        cfg.online_enabled = False
        cfg.offline_enabled = False
        cfg.save()
        resp = self.client.get(reverse('payment_start', args=[self.product.pk]))
        self.assertContains(resp, 'Online ordering is not open')
        # 不再显示提交按钮，改为联系入口
        self.assertNotContains(resp, 'Place order')

    @override_settings(STRIPE_SECRET_KEY='sk_test_dummy')
    def test_online_enabled_lists_five_methods(self):
        enable_online()
        resp = self.client.get(reverse('payment_start', args=[self.product.pk]))
        for label in ('Visa', 'MasterCard', 'UnionPay', '支付宝', '微信支付'):
            self.assertContains(resp, label)

    @override_settings(STRIPE_SECRET_KEY='')
    def test_online_enabled_without_key_falls_back_to_offline(self):
        enable_online()
        resp = self.client.get(reverse('payment_start', args=[self.product.pk]))
        self.assertContains(resp, '银行转账')
        self.assertNotContains(resp, '支付宝 Alipay')

    def test_inactive_account_hidden(self):
        self.account.is_active = False
        self.account.save()
        resp = self.client.get(reverse('payment_start', args=[self.product.pk]))
        self.assertNotContains(resp, self.account.account_number)

    def test_accounts_ordered_by_sort_then_id(self):
        second = BankAccount.objects.create(
            bank_name='Bank B', account_name='B', account_number='B-2', sort_order=-1,
        )
        resp = self.client.get(reverse('payment_start', args=[self.product.pk]))
        accounts = list(resp.context['bank_accounts'])
        self.assertEqual(accounts[0], second)
        self.assertIn(self.account, accounts)

    def test_settings_is_singleton(self):
        cfg = PaymentSettings.load()
        cfg.online_enabled = True
        cfg.save()
        self.assertEqual(PaymentSettings.objects.count(), 1)
        self.assertEqual(PaymentSettings.load().pk, 1)


class StripeIntegrationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='线缆', name_en='Cables', slug='cables-test')
        self.product = Product.objects.create(
            sku='TEST-3', part_name='线缆', category=self.category, price=Decimal('99.99'),
        )
        enable_online()

    def _post(self, method):
        return self.client.post(reverse('payment_start', args=[self.product.pk]), {
            'name': 'Ali', 'email': 'ali@example.com', 'quantity': '1', 'method': method,
        })

    @override_settings(STRIPE_SECRET_KEY='sk_test_dummy', STRIPE_WEBHOOK_SECRET='whsec_dummy')
    @patch('payments.gateway._stripe')
    def test_stripe_checkout_maps_methods(self, fake_stripe):
        stripe_api = fake_stripe.return_value
        stripe_api.checkout.Session.create.return_value = MagicMock(
            id='cs_test_123', url='https://checkout.stripe.com/c/pay/cs_test_123',
        )

        for method, expected_type in (
            ('visa', 'card'), ('mastercard', 'card'), ('unionpay', 'card'),
            ('alipay', 'alipay'), ('wechat', 'wechat_pay'),
        ):
            with self.subTest(method=method):
                resp = self._post(method)
                self.assertEqual(resp.status_code, 302)
                self.assertTrue(resp['Location'].startswith('https://checkout.stripe.com'))
                kwargs = stripe_api.checkout.Session.create.call_args.kwargs
                self.assertEqual(kwargs['payment_method_types'], [expected_type])
                self.assertEqual(kwargs['line_items'][0]['price_data']['unit_amount'], 9999)
                order = Order.objects.latest('created_at')
                self.assertEqual(order.provider, 'stripe')
                self.assertEqual(order.provider_ref, 'cs_test_123')

    @override_settings(STRIPE_SECRET_KEY='sk_test_dummy', STRIPE_WEBHOOK_SECRET='whsec_dummy')
    @patch('payments.gateway._stripe')
    def test_wechat_pay_uses_web_client(self, fake_stripe):
        stripe_api = fake_stripe.return_value
        stripe_api.checkout.Session.create.return_value = MagicMock(id='cs_x', url='https://x')
        self._post('wechat')
        kwargs = stripe_api.checkout.Session.create.call_args.kwargs
        self.assertEqual(kwargs['payment_method_options'], {'wechat_pay': {'client': 'web'}})

    @override_settings(STRIPE_SECRET_KEY='sk_test_dummy', STRIPE_WEBHOOK_SECRET='whsec_dummy')
    @patch('payments.gateway._stripe')
    def test_stripe_failure_marks_order_failed(self, fake_stripe):
        fake_stripe.return_value.checkout.Session.create.side_effect = RuntimeError('boom')
        resp = self._post('visa')
        self.assertEqual(resp.status_code, 502)
        order = Order.objects.get()
        self.assertEqual(order.status, 'failed')

    @override_settings(STRIPE_SECRET_KEY='sk_test_dummy', STRIPE_WEBHOOK_SECRET='')
    def test_webhook_requires_secret(self):
        resp = self.client.post(reverse('stripe_webhook'), data='{}',
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    @override_settings(STRIPE_SECRET_KEY='sk_test_dummy', STRIPE_WEBHOOK_SECRET='whsec_dummy')
    @patch('payments.gateway.construct_webhook_event')
    def test_webhook_marks_order_paid(self, construct):
        order = Order.objects.create(
            product=self.product, sku='TEST-3', product_name='线缆', quantity=1,
            unit_price=Decimal('99.99'), amount=Decimal('99.99'), currency='USD',
            method='alipay', status='pending', provider='stripe', provider_ref='cs_1',
        )
        construct.return_value = {
            'type': 'checkout.session.completed',
            'data': {'object': {'id': 'cs_1', 'payment_status': 'paid',
                                'metadata': {'order_no': order.order_no}}},
        }
        resp = self.client.post(reverse('stripe_webhook'), data='{}',
                                content_type='application/json',
                                HTTP_STRIPE_SIGNATURE='sig')
        self.assertEqual(resp.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')


class AdminPricingTests(TestCase):
    """后台实时改价 + 收款设置页 + 订单列表。"""

    def setUp(self):
        from django.contrib.auth.models import User

        self.category = Category.objects.create(name='手柄', name_en='Handles', slug='handles-test')
        self.product = Product.objects.create(
            sku='TEST-9', part_name='手柄', category=self.category, price=Decimal('99999.00'),
        )
        self.user = User.objects.create_superuser('admin', 'admin@example.com', 'pw-test-123')
        self.client.force_login(self.user)
        PaymentSettings.load()

    def test_changelist_renders_inline_price_editor(self):
        resp = self.client.get('/admin/products/product/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="form-0-price"')
        self.assertContains(resp, '定价状态')

    def test_order_admin_lists_orders(self):
        order = Order.objects.create(
            product=self.product, sku='TEST-9', product_name='手柄', quantity=1,
            unit_price=Decimal('120.00'), amount=Decimal('120.00'), currency='USD',
            method='alipay', provider='manual',
        )
        resp = self.client.get('/admin/payments/order/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, order.order_no)

    def test_payment_settings_changelist_redirects_to_singleton(self):
        resp = self.client.get('/admin/payments/paymentsettings/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/admin/payments/paymentsettings/1/change/', resp['Location'])

    @override_settings(STRIPE_SECRET_KEY='sk_test_dummy')
    def test_payment_settings_page_has_switches_and_accounts(self):
        resp = self.client.get('/admin/payments/paymentsettings/1/change/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '启用在线收款')
        self.assertContains(resp, '启用线下汇款')
        self.assertContains(resp, '收款账户')
        self.assertContains(resp, '检测 Stripe 连接')

    def test_bank_account_admin_lists_and_creates(self):
        resp = self.client.get('/admin/payments/bankaccount/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '收款账户')
        add = self.client.get('/admin/payments/bankaccount/add/')
        self.assertEqual(add.status_code, 200)
        self.assertContains(add, '银行账号')

    @override_settings(STRIPE_SECRET_KEY='')
    def test_probe_without_key_returns_error_message(self):
        resp = self.client.get('/admin/payments/paymentsettings/probe-stripe/', follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'STRIPE_SECRET_KEY')

    @override_settings(STRIPE_SECRET_KEY='sk_test_dummy')
    @patch('payments.gateway.probe_stripe')
    def test_probe_success_shows_account(self, probe):
        probe.return_value = {
            'id': 'acct_test_1', 'country': 'HK', 'default_currency': 'USD',
            'business_type': 'company', 'mode': 'test',
        }
        resp = self.client.get('/admin/payments/paymentsettings/probe-stripe/', follow=True)
        self.assertContains(resp, 'acct_test_1')
        self.assertContains(resp, 'HK')


class ProductCatalogTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='线缆', name_en='Cables', slug='cables-test')
        for i in range(30):
            Product.objects.create(sku=f'P-{i:03d}', part_name=f'件{i}', category=self.category)

    def test_list_is_paginated(self):
        resp = self.client.get(reverse('product_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['products']), 24)
        self.assertEqual(resp.context['total_count'], 30)

    def test_second_page(self):
        resp = self.client.get(reverse('product_list'), {'page': 2})
        self.assertEqual(len(resp.context['products']), 6)

    def test_home_hides_empty_and_uncategorized_categories(self):
        empty = Category.objects.create(name='空', name_en='Empty', slug='empty-test')
        unclassified = Category.objects.create(name='未分类', name_en='Uncategorized',
                                               slug='uncategorized')
        Product.objects.create(sku='P-U1', part_name='未归类', category=unclassified)
        resp = self.client.get(reverse('home'))
        slugs = [c['slug'] for c in resp.context['cat_cards']]
        self.assertIn('cables-test', slugs)
        self.assertNotIn('empty-test', slugs)
        self.assertNotIn('uncategorized', slugs)
        self.assertTrue(empty)
