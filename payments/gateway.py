"""支付通道适配层。

当前内置 Stripe（一次接入覆盖银行卡 Visa / MasterCard / 银联、支付宝、微信支付）。
新增通道（Airwallex / Adyen / 支付宝官方等）只需在这里加一个适配函数，
视图层不关心具体通道。
"""

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.urls import reverse

from .models import STRIPE_PAYMENT_METHOD_TYPES


def stripe_configured():
    return bool(getattr(settings, 'STRIPE_SECRET_KEY', ''))


def stripe_key_mode():
    """密钥模式：live=真实收款，test=测试模式，''=未配置。"""
    key = getattr(settings, 'STRIPE_SECRET_KEY', '') or ''
    if key.startswith('sk_live_') or key.startswith('rk_live_'):
        return 'live'
    if key.startswith('sk_test_') or key.startswith('rk_test_'):
        return 'test'
    return 'live' if key else ''


def probe_stripe():
    """后台「检测连接」：调一次只读接口，验证密钥能否连上 Stripe。

    返回账户摘要；密钥无效/网络不通时抛出异常，由调用方展示错误。
    """
    stripe = _stripe()
    account = stripe.Account.retrieve()
    return {
        'id': account.get('id', ''),
        'country': account.get('country', ''),
        'default_currency': (account.get('default_currency') or '').upper(),
        'business_type': account.get('business_type', ''),
        'mode': stripe_key_mode(),
    }


def _stripe():
    """延迟导入：未安装/未配置时不影响其他功能。"""
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def create_checkout_session(order, product, request):
    """为订单创建 Stripe Checkout 会话，返回 (session_id, redirect_url)。

    说明：
    - 银行卡类（Visa/MasterCard/银联）统一走 `card`，具体卡组织由 Stripe 账户设置决定；
    - 支付宝走 `alipay`；微信支付走 `wechat_pay`（web 端）。
    """
    stripe = _stripe()

    method_types = STRIPE_PAYMENT_METHOD_TYPES.get(order.method, ['card'])
    unit_minor = int((Decimal(order.unit_price) * 100).to_integral_value(rounding=ROUND_HALF_UP))

    product_name = f'{order.sku} · {order.product_name}'.strip(' ·') or order.sku
    success_url = request.build_absolute_uri(
        reverse('payment_success', args=[order.order_no])
    ) + '?session_id={CHECKOUT_SESSION_ID}'
    cancel_url = request.build_absolute_uri(reverse('payment_cancel', args=[order.order_no]))

    params = {
        'mode': 'payment',
        'payment_method_types': method_types,
        'line_items': [{
            'price_data': {
                'currency': order.currency.lower(),
                'product_data': {
                    'name': product_name,
                    'description': f'Unit price {order.unit_price_display}',
                },
                'unit_amount': unit_minor,
            },
            'quantity': order.quantity,
        }],
        'success_url': success_url,
        'cancel_url': cancel_url,
        'client_reference_id': order.order_no,
        'metadata': {'order_no': order.order_no, 'sku': order.sku},
    }
    if order.customer_email:
        params['customer_email'] = order.customer_email
    if order.method == 'wechat':
        # 微信支付在 Checkout 里需要显式声明 web 客户端
        params['payment_method_options'] = {'wechat_pay': {'client': 'web'}}

    session = stripe.checkout.Session.create(**params)
    return session.id, session.url


def retrieve_checkout_session(session_id):
    stripe = _stripe()
    return stripe.checkout.Session.retrieve(session_id)


def construct_webhook_event(payload, sig_header):
    stripe = _stripe()
    return stripe.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET,
    )
