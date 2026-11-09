import logging
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.context_processors import get_lang
from core.models import SiteSettings
from products.models import Product

from . import gateway
from .models import (
    BankAccount, CARD_METHODS, OFFLINE_METHOD, Order, PaymentMethod, PaymentSettings,
)

logger = logging.getLogger(__name__)

#: 下单频率限制：同一 IP 每小时最多 20 单（防刷单）
ORDER_RATE_WINDOW = 3600
ORDER_RATE_MAX = 20

MAX_QUANTITY = 999

METHOD_LABELS = {
    PaymentMethod.VISA: ('Visa', '信用卡 / 借记卡', 'Credit / debit card'),
    PaymentMethod.MASTERCARD: ('MasterCard', '信用卡 / 借记卡', 'Credit / debit card'),
    PaymentMethod.UNIONPAY: ('银联 UnionPay', '银行卡', 'Bank card'),
    PaymentMethod.ALIPAY: ('支付宝 Alipay', '扫码支付', 'Scan to pay'),
    PaymentMethod.WECHAT: ('微信支付 WeChat Pay', '扫码支付', 'Scan to pay'),
}

METHOD_ORDER = [
    PaymentMethod.VISA,
    PaymentMethod.MASTERCARD,
    PaymentMethod.UNIONPAY,
    PaymentMethod.ALIPAY,
    PaymentMethod.WECHAT,
]


def _client_ip(request):
    cf = request.META.get('HTTP_CF_CONNECTING_IP')
    if cf:
        return cf.strip()
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '') or 'unknown'


def _rate_limited(request):
    key = f'order_rate:{_client_ip(request)}'
    count = cache.get(key, 0)
    if count >= ORDER_RATE_MAX:
        return True
    cache.set(key, count + 1, ORDER_RATE_WINDOW)
    return False


def payment_mode(product):
    """当前该产品实际生效的收款模式（由后台「收款设置」决定）。

    - online：在线收款（Stripe 已配密钥 + 后台开启）
    - external：产品单独配置了外部支付链接
    - offline：线下汇款（银行转账，后台维护收款账户）
    - unavailable：既没在线、也没线下 → 只能联系客服
    """
    if product.payment_link:
        return 'external'
    cfg = PaymentSettings.load()
    if cfg.online_enabled and gateway.stripe_configured():
        return 'online'
    if cfg.offline_enabled:
        return 'offline'
    return 'unavailable'


def _methods_context(request, product):
    """按当前模式给出可选的支付方式，以及前端据此展示说明的 channel。"""
    lang = get_lang(request)
    mode = payment_mode(product)

    if mode == 'offline':
        return [{
            'value': OFFLINE_METHOD,
            'label': '银行转账 / Bank transfer',
            'sub': ('汇至下方账户，到账后发货' if lang == 'zh' else 'Transfer to the account below'),
            'is_card': False,
        }], 'offline'

    if mode == 'unavailable':
        return [], 'unavailable'

    methods = []
    for value in METHOD_ORDER:
        label, sub_zh, sub_en = METHOD_LABELS[value]
        methods.append({
            'value': value,
            'label': label,
            'sub': sub_en if lang == 'en' else sub_zh,
            'is_card': value in CARD_METHODS,
        })
    return methods, ('external' if mode == 'external' else 'stripe')


def active_bank_accounts():
    return list(BankAccount.objects.filter(is_active=True))


def _native_payment_note(site_settings, lang):
    return site_settings.payment_note_en if lang == 'en' else site_settings.payment_note_zh


def _page_context(request, product, site_settings, channel, **extra):
    lang = get_lang(request)
    methods, _channel = _methods_context(request, product)
    cfg = PaymentSettings.load()
    ctx = {
        'active': 'products',
        'product': product,
        'methods': methods,
        'channel': channel,
        'online_pay': channel == 'stripe',
        'offline': channel == 'offline',
        'bank_accounts': active_bank_accounts() if channel == 'offline' else [],
        'offline_title': cfg.title(lang),
        'offline_intro': cfg.intro(lang),
        'max_quantity': MAX_QUANTITY,
        'payment_note': _native_payment_note(site_settings, lang),
    }
    ctx.update(extra)
    return ctx


def payment_start(request, pk):
    """产品的固定支付链接：/pay/<pk>/ —— 可直接发给客户下单。"""
    product = get_object_or_404(Product, pk=pk)

    if not PaymentSettings.prices_visible():
        # 后台关闭了价格显示：不进入收银台，回详情页走询价
        return HttpResponseRedirect(reverse('product_detail', args=[product.pk]))

    if product.is_placeholder_price:
        # 未定价产品：不进入收银台，引导回详情页询价
        return HttpResponseRedirect(
            reverse('product_detail', args=[product.pk]) + '?price=required'
        )

    site_settings = SiteSettings.load()
    mode = payment_mode(product)
    methods_channel = {
        'online': 'stripe', 'external': 'external',
        'offline': 'offline', 'unavailable': 'unavailable',
    }[mode]
    lang = get_lang(request)

    if request.method != 'POST':
        return render(request, 'payments/pay.html',
                      _page_context(request, product, site_settings, methods_channel))

    error = ''
    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    phone = request.POST.get('phone', '').strip()[:50]
    country = request.POST.get('country', '').strip()[:100]
    note = request.POST.get('note', '').strip()[:500]
    method = request.POST.get('method', '').strip()

    # 蜜罐字段：机器人填了隐藏字段 → 静默拒绝
    if request.POST.get('website'):
        error = '提交失败，请重试。' if lang == 'zh' else 'Submission failed. Please try again.'
    if not error and _rate_limited(request):
        error = '下单过于频繁，请稍后再试。' if lang == 'zh' else \
            'Too many orders. Please try again later.'
    if not error and mode in ('online', 'external'):
        allowed_methods = set(METHOD_ORDER)
    elif not error and mode == 'offline':
        allowed_methods = {OFFLINE_METHOD}
        if method and method != OFFLINE_METHOD:
            allowed_methods = set()
        method = OFFLINE_METHOD
    else:
        allowed_methods = set()
        error = ('该产品暂未开放在线下单，请先联系我们。'
                 if lang == 'zh' else
                 'This product is not open for online ordering yet. Please contact us.')
    if not error and method not in allowed_methods:
        error = '请选择支付方式。' if lang == 'zh' else 'Please choose a payment method.'
    if not error and not name:
        error = '请填写联系人姓名。' if lang == 'zh' else 'Please enter your name.'
    if not error and not email:
        error = '请填写邮箱，用于接收订单与支付回执。' if lang == 'zh' else \
            'Please enter your email for the receipt.'
    if not error and '@' not in email:
        error = '邮箱格式不正确。' if lang == 'zh' else 'Please enter a valid email address.'

    try:
        quantity = int(request.POST.get('quantity') or 1)
    except (TypeError, ValueError):
        quantity = 0
    if not error and not 1 <= quantity <= MAX_QUANTITY:
        error = '购买数量不正确。' if lang == 'zh' else 'Invalid quantity.'
    if not error and quantity == 0:
        quantity = 1

    if error:
        return render(request, 'payments/pay.html', _page_context(
            request, product, site_settings, methods_channel,
            form_error=error,
            form={'name': name, 'email': email, 'phone': phone,
                  'country': country, 'note': note, 'method': method,
                  'quantity': quantity or 1},
        ), status=400)

    unit_price = Decimal(product.price)
    amount = unit_price * quantity

    with transaction.atomic():
        order = Order.objects.create(
            product=product,
            sku=product.sku,
            product_name=product.display_name(lang),
            quantity=quantity,
            unit_price=unit_price,
            amount=amount,
            currency=product.currency,
            method=method,
            customer_name=name,
            customer_email=email,
            customer_phone=phone,
            customer_country=country,
            note=note,
            status='pending',
            provider='manual',
        )

    # 1) 产品配了外部支付链接 → 直接跳转
    if mode == 'external':
        order.provider = 'external_link'
        order.save(update_fields=['provider'])
        return HttpResponseRedirect(product.payment_link)

    # 2) 已开启在线收款 + 已配 Stripe 密钥 → 在线收银台
    if mode == 'online':
        try:
            session_id, redirect_url = gateway.create_checkout_session(order, product, request)
        except Exception as exc:  # 通道异常不能把客户晾在空白页
            logger.exception('Stripe Checkout 创建失败 order=%s', order.order_no)
            order.status = 'failed'
            order.note = (order.note + f' | stripe_error: {exc}')[:500]
            order.save(update_fields=['status', 'note'])
            return render(request, 'payments/pay.html', _page_context(
                request, product, site_settings, methods_channel,
                form_error=(
                    '在线支付通道暂时不可用，请稍后重试。'
                    if lang == 'zh' else
                    'Online payment is temporarily unavailable. Please try again later.'
                ),
                form={'name': name, 'email': email, 'phone': phone,
                      'country': country, 'note': note, 'method': method,
                      'quantity': quantity},
            ), status=502)

        order.provider = 'stripe'
        order.provider_ref = session_id
        order.save(update_fields=['provider', 'provider_ref'])
        return HttpResponseRedirect(redirect_url)

    # 3) 未配置任何通道 → 人工确认（订单照样入库，客服跟进收款）
    return HttpResponseRedirect(order.get_success_url())


def payment_success(request, order_no):
    order = get_object_or_404(Order, order_no=order_no)

    # 从 Stripe 回跳时，服务端再核对一次支付状态（不依赖前端）。
    session_id = request.GET.get('session_id', '')
    if (not order.is_paid and order.provider == 'stripe'
            and session_id and gateway.stripe_configured()):
        try:
            session = gateway.retrieve_checkout_session(session_id)
            if session.get('payment_status') == 'paid':
                order.mark_paid(provider_ref=session.get('id', ''))
        except Exception:
            logger.exception('Stripe 回跳校验失败 order=%s', order.order_no)

    return render(request, 'payments/success.html', {
        'active': 'products',
        'order': order,
        'bank_accounts': active_bank_accounts() if order.method == OFFLINE_METHOD else [],
        'offline_title': PaymentSettings.load().title(get_lang(request)),
        'offline_intro': PaymentSettings.load().intro(get_lang(request)),
    })


def payment_cancel(request, order_no):
    order = get_object_or_404(Order, order_no=order_no)
    if order.status == 'pending':
        order.status = 'cancelled'
        order.save(update_fields=['status'])
    return render(request, 'payments/cancel.html', {
        'active': 'products',
        'order': order,
    })


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Stripe 支付结果回调（生产环境务必配置 STRIPE_WEBHOOK_SECRET）。"""
    if not gateway.stripe_configured() or not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponseBadRequest('webhook not configured')

    payload = request.body
    sig_header = request.headers.get('Stripe-Signature', '')
    try:
        event = gateway.construct_webhook_event(payload, sig_header)
    except Exception as exc:
        logger.warning('Stripe webhook 验签失败: %s', exc)
        return HttpResponseBadRequest('invalid signature')

    if event.get('type') == 'checkout.session.completed':
        session = event['data']['object']
        order_no = (session.get('metadata') or {}).get('order_no')
        if order_no:
            order = Order.objects.filter(order_no=order_no).first()
            if order and session.get('payment_status') == 'paid':
                order.mark_paid(provider_ref=session.get('id', ''))

    return HttpResponse(status=200)
