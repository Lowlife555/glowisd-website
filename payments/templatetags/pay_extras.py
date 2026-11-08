from django import template

register = template.Library()


@register.filter
def status_label(order, lang='zh'):
    """订单状态本地化：{{ order|status_label:lang }}"""
    return order.status_label(lang)


@register.filter
def method_label(order, lang='zh'):
    """支付方式本地化：{{ order|method_label:lang }}"""
    return order.method_label(lang)
