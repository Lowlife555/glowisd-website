"""登录审计上下文：UA 解析 + IP 双引擎地区解析 + 请求上下文提取。

从 core/signals.py 拆出（V0.5.0 结构优化，行为完全一致）：
signals.py 只保留信号接收器，审计上下文逻辑统一在此维护。

IP 解析策略（双引擎）：
- 私有/内网 IP → 空（不外发查询）
- 中国大陆（非港澳台）→ 离线 ip2region（省·市，准确、零延迟、无网络依赖）
- 海外 / 港澳台 / 离线库无结果 → 在线 ip-api.com（国家·州·市 城市级中文），
  失败或超时回退离线结果（region 永不空白）
"""
import json
import os
import urllib.request

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


# ---------------------------------------------------------------------------
# 在线 IP 解析（ip-api.com，免费版 HTTP，45 次/分钟，城市级，中文）
# 用于海外/港澳台 IP 的精确解析；失败/超时回退离线 ip2region 结果
# ---------------------------------------------------------------------------
_ONLINE_TIMEOUT_SEC = 3

# 疑似代理/VPN/数据中心关键词（匹配 isp/org，小写）
_PROXY_KEYWORDS = (
    'proxy', 'vpn', 'hosting', 'cloud', 'datacenter', 'data center',
    'zouter', 'm247', 'digitalocean', 'ovh', 'hetzner', 'linode', 'vultr',
    'cloudflare', 'fastly', 'akamai', 'amazon', 'google', 'microsoft',
    'alibaba', 'tencent', 'huawei', 'oracle', 'ibm', '数据', '代理', '机房', '机柜',
)

# ip2region 离线库把港澳台归入「中国」国别，但只有省级精度 → 识别后走在线解析
_CN_SPECIAL_REGIONS = ('香港', '澳门', '台湾', 'Hong Kong', 'Macao', 'Macau', 'Taiwan')


def _resolve_offline(ip):
    """ip2region 离线解析：返回 (region_str, country)。失败返回 ('', '')。"""
    searcher = _get_searcher()
    if searcher is None:
        return '', ''
    try:
        region = searcher.search(ip)
    except Exception:  # noqa: BLE001 - 查询失败留空
        return '', ''
    if not region:
        return '', ''
    # ip2region v4 返回格式：国家|省份|城市|运营商|国家码（如 中国|江苏省|常州市|电信|CN）
    parts = str(region).split('|')
    country = _clean_region_part(parts[0] if len(parts) > 0 else '')
    province = _clean_region_part(parts[1] if len(parts) > 1 else '')
    city = _clean_region_part(parts[2] if len(parts) > 2 else '')
    if province and city:
        region_str = f'{province}·{city}'
    else:
        region_str = province or city or ''
    return region_str, country


def _looks_like_proxy(text):
    """isp/org 文本命中代理/数据中心关键词 → 判定疑似代理出口。"""
    t = (text or '').lower()
    return any(k in t for k in _PROXY_KEYWORDS)


def _resolve_online(ip):
    """ip-api.com 在线解析：返回 (region_str, is_proxy)；失败返回 (None, False)。"""
    url = 'http://ip-api.com/json/%s?lang=zh-CN' % ip
    req = urllib.request.Request(url, headers={'User-Agent': 'glowisd-admin/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=_ONLINE_TIMEOUT_SEC) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception:  # noqa: BLE001 - 网络异常/超时回退离线
        return None, False
    if not isinstance(data, dict) or data.get('status') != 'success':
        return None, False
    country = (data.get('country') or '').strip()
    region_name = (data.get('regionName') or '').strip()
    city = (data.get('city') or '').strip()
    parts = []
    for p in (country, region_name, city):
        p = p.strip()
        if p and p not in parts:
            parts.append(p)
    region_str = '·'.join(parts)
    is_proxy = _looks_like_proxy('%s %s' % (data.get('isp') or '', data.get('org') or ''))
    return (region_str or None), is_proxy


def _is_private_ip(ip):
    """私有/保留 IP（内网、回环）→ 不外发在线查询。"""
    if ip.startswith(('127.', '10.', '192.168.', '0.', '169.254.')):
        return True
    if ip.startswith('172.'):
        try:
            second = int(ip.split('.')[1])
            return 16 <= second <= 31
        except (ValueError, IndexError):
            return False
    return False


def _resolve_region(ip):
    """把 IP 解析成登录地区，返回 (region, is_proxy)。"""
    if not ip or _is_private_ip(ip):
        return '', False
    offline_region, country = _resolve_offline(ip)
    is_cn_mainland = country == '中国' and offline_region and not any(
        s in offline_region for s in _CN_SPECIAL_REGIONS
    )
    if is_cn_mainland:
        return offline_region, False
    online_region, is_proxy = _resolve_online(ip)
    if online_region:
        return online_region, is_proxy
    return offline_region, False


def extract_request_context(request):
    """从 request 提取登录上下文（IP、UA、设备类型、系统、浏览器、地区）。

    成功/失败登录共用，避免重复解析逻辑。request 为 None 时返回空上下文。
    """
    if not request:
        return {
            'ip_address': None,
            'user_agent': '',
            'device_type': '',
            'os_name': '',
            'browser': '',
            'region': '',
            'is_proxy': False,
        }
    # 生产环境经 nginx 反代，真实 IP 在 X-Forwarded-For 头
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
    raw_ua = request.META.get('HTTP_USER_AGENT', '')[:500]

    device_type, os_name, browser = _parse_user_agent(raw_ua)
    region, is_proxy = _resolve_region(ip) if ip else ('', False)

    return {
        'ip_address': ip or None,
        'user_agent': raw_ua,
        'device_type': device_type,
        'os_name': os_name,
        'browser': browser,
        'region': region,
        'is_proxy': is_proxy,
    }
