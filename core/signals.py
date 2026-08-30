import os

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import LoginRecord

# ---------------------------------------------------------------------------
# UA 解析（user-agents 库）
# 依赖：pip install user-agents
# ---------------------------------------------------------------------------
try:
    from user_agents import parse as _parse_ua
except Exception:  # pragma: no cover - 库未安装时优雅降级
    _parse_ua = None


def _parse_user_agent(raw_ua):
    """返回 (device_type, os_name, browser)。解析失败或 UA 为空时各项留空字符串。"""
    device_type = os_name = browser = ''
    if raw_ua and _parse_ua is not None:
        try:
            ua = _parse_ua(raw_ua)
            if ua.is_mobile:
                device_type = '手机'
            elif ua.is_tablet:
                device_type = '平板'
            else:
                device_type = '桌面'
            os_name = ua.os.family or ''
            browser = ua.browser.family or ''
        except Exception:  # noqa: BLE001 - 解析失败留空
            device_type = os_name = browser = ''
    return device_type, os_name, browser


# ---------------------------------------------------------------------------
# IP 地区解析（py-ip2region 库 + ip2region_v4.xdb 数据文件）
# 依赖：pip install py-ip2region
# 数据文件：core/data/ip2region_v4.xdb（约 11MB）
#   获取方式：https://raw.githubusercontent.com/lionsoul2014/ip2region/master/data/ip2region_v4.xdb
#   （已加入 .gitignore，不提交；代码在数据文件缺失时优雅降级，region 留空）
# ---------------------------------------------------------------------------
_XDB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'ip2region_v4.xdb')

_searcher = None
_searcher_failed = False


def _get_searcher():
    """惰性创建 ip2region 查询对象；数据文件缺失/加载失败时返回 None。"""
    global _searcher, _searcher_failed
    if _searcher is not None:
        return _searcher
    if _searcher_failed:
        return None
    if not os.path.exists(_XDB_PATH):
        _searcher_failed = True
        return None
    try:
        import ip2region.searcher as xdb
        import ip2region.util as util

        # 整文件读入内存，避免并发登录时文件句柄 seek/read 竞态
        with open(_XDB_PATH, 'rb') as f:
            buffer = f.read()
        _searcher = xdb.new_with_buffer(util.IPv4, buffer)
    except Exception:  # noqa: BLE001 - 加载失败留空
        _searcher = None
        _searcher_failed = True
    return _searcher


def _clean_region_part(value):
    value = (value or '').strip()
    return '' if value in ('', '0', '-', 'Reserved', 'reserved') else value


def _resolve_region(ip):
    """把 IP 解析成 '省·市'，失败/无效返回空字符串。"""
    if not ip:
        return ''
    searcher = _get_searcher()
    if searcher is None:
        return ''
    try:
        region = searcher.search(ip)
    except Exception:  # noqa: BLE001 - 查询失败留空
        return ''
    if not region:
        return ''
    # ip2region v4 返回格式：国家|省份|城市|运营商|国家码（如 中国|江苏省|常州市|电信|CN）
    parts = str(region).split('|')
    province = _clean_region_part(parts[1] if len(parts) > 1 else '')
    city = _clean_region_part(parts[2] if len(parts) > 2 else '')
    if province and city:
        return f'{province}·{city}'
    return province or city or ''


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """管理员登录后台时，记录 IP、设备、系统、浏览器与登录地区。"""
    if not user or not request:
        return
    # 生产环境经 nginx 反代，真实 IP 在 X-Forwarded-For 头
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
    raw_ua = request.META.get('HTTP_USER_AGENT', '')[:500]

    device_type, os_name, browser = _parse_user_agent(raw_ua)
    region = _resolve_region(ip) if ip else ''

    LoginRecord.objects.create(
        user=user,
        ip_address=ip or None,
        user_agent=raw_ua,
        device_type=device_type,
        os_name=os_name,
        browser=browser,
        region=region,
    )
