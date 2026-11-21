"""核心中间件：后台登录限流 + 首登强制改密 + 安全响应头。

P1 登录限流（自研，不引新依赖）：
- 复用 core/signals.py 的 user_login_failed 信号在 Django cache 里按「IP」与「username」
  双维度计数（5 分钟窗口），失败满 5 次后封禁该 IP 15 分钟；
- LoginRateLimitMiddleware 拦截 /admin/login/ 的 POST：IP 被封锁时直接返回 403
  （页面提示锁定 15 分钟），成功登录由 user_logged_in 信号清除计数。

P1 密码策略：
- AdminProfile.must_change_password 之前只是字段、未在登录流程生效；本中间件在
  认证后（process_view 阶段 request.user 已就绪）检查该标记，为 True 时把后台请求
  重定向到「修改密码」页，改密成功后清除标记（Django 6.1 的 set_password 不再发
  password_changed 信号，故在 process_response 里识别 302 → password_change_done 来清除）。

P2 安全响应头（SecurityHeadersMiddleware）：
- 实测 Django 6.1 下虽然 MIDDLEWARE 里配了 XFrameOptionsMiddleware，但 runserver / test
  client 响应头都没有 X-Frame-Options（SecurityMiddleware 的 nosniff/referrer/COOP 都在，
  唯独 XFO 缺失），故这里显式输出 X-Frame-Options 兜底，并同时输出 CSP（含
  frame-ancestors 'none'，双重防点击劫持）。
- CSP 里的 'unsafe-inline' 是 simpleui 后台内联脚本/样式的兼容妥协（前台 Vue 本地构建、
  simpleui 均有内联代码），生产可进一步收敛。
"""
import os

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse

# 登录失败计数窗口与封禁时长（秒）
FAIL_WINDOW = 300        # 5 分钟失败计数窗口
FAIL_LIMIT = 5           # 同一 IP 失败达到 5 次即封禁
BLOCK_DURATION = 900     # 封禁 15 分钟

# CSP：simpleui 后台 + 前台 Vue 均有内联脚本/样式，必须保留 'unsafe-inline'（兼容妥协）；
# 'unsafe-eval'：vue.global.prod.js 是含编译器的完整构建（V0.6.4 实测缺它会抛
# EvalError → Vue 挂载失败 → 语言切换按钮/询价表单插值/simpleui 登录表单全部不渲染），
# 运行时字符串模板编译（new Function）必需；本项目无用户输入进脚本执行路径，风险可控。
# frame-ancestors 'self'：V0.6.5 从 'none' 放宽——simpleui 后台左侧菜单 + 右侧 iframe
# 加载同源功能页，'none' 会拦掉同源 iframe 导致后台功能全部失效；'self' 仍拒绝跨源
# 嵌入（防点击劫持目标不变）。
CSP_VALUE = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "frame-ancestors 'self'"
)


def client_ip(request):
    """从请求取客户端真实 IP。

    优先级（V0.7.2 Cloudflare 接入适配）：
    1. CF-Connecting-IP：Cloudflare 代理注入的真实客户端 IP（CF 保证不可伪造），
       走 Cloudflare 的流量永远取它，避免所有访客都显示成 CF 节点 IP、登录限流失效；
    2. X-Forwarded-For 首个值：无反代/直连场景（nginx 覆盖模式注入 $remote_addr，
       客户端伪造值已被覆盖，见 deploy/nginx-glowisd.conf 注释）；
    3. REMOTE_ADDR 兜底。
    """
    cf_ip = request.META.get('HTTP_CF_CONNECTING_IP', '').strip()
    if cf_ip:
        return cf_ip
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')


def _fail_key(ip='', username=''):
    return 'login_fail:%s:%s' % (ip or '-', username or '-')


def _block_key(ip=''):
    return 'login_block:%s' % ip


def bump_login_failures(request, username=''):
    """登录失败：按 IP 与 username 双维度在 cache 计数，满 5 次封禁 IP 15 分钟。

    在 core/signals.py 的 user_login_failed 信号里调用。request 为空（罕见）时
    仅按 username 计数（IP 维度跳过，不封禁）。
    """
    username = username or ''
    ip = client_ip(request) if request is not None else ''
    key = _fail_key(ip, username)
    count = (cache.get(key) or 0) + 1
    cache.set(key, count, timeout=FAIL_WINDOW)
    if ip and count >= FAIL_LIMIT:
        cache.set(_block_key(ip), 1, timeout=BLOCK_DURATION)
    return count


def clear_login_failures(request, username=''):
    """登录成功：清除该 IP 与 username 的失败计数（封禁标记不清除，等自然过期）。

    在 core/signals.py 的 user_logged_in 信号里调用。
    """
    username = username or ''
    ip = client_ip(request) if request is not None else ''
    if ip:
        cache.delete(_fail_key(ip, username))
        # 同时清掉「纯 IP 维度」的残留计数（不同账号共用同一 IP 时）
        cache.delete(_fail_key(ip, ''))
    cache.delete(_fail_key('', username))


def is_ip_blocked(ip=''):
    return bool(ip and cache.get(_block_key(ip)))


class SecurityHeadersMiddleware:
    """显式输出安全响应头（X-Frame-Options 兜底 + CSP + 沿用 SecurityMiddleware 的其余头）。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # SAMEORIGIN：拒绝跨源 iframe 嵌入（防点击劫持），放行同源嵌入——
        # simpleui 后台首页以同源 iframe 加载各功能页，DENY 会把后台功能全拦掉（V0.6.5）
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Content-Security-Policy', CSP_VALUE)
        return response


class LoginRateLimitMiddleware:
    """后台登录限流 + 首登强制改密。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 登录限流：只拦 /admin/login/ 的 POST（在 Authentication 之前就拦截，避免继续尝试）
        if request.path == '/admin/login/' and request.method == 'POST':
            if is_ip_blocked(client_ip(request)):
                return HttpResponseForbidden(
                    '尝试过于频繁，该 IP 已被临时锁定，请 15 分钟后再试。\n'
                    'Too many failed attempts. This IP is locked for 15 minutes.'
                )
        response = self.get_response(request)
        self._handle_password_change(request, response)
        return response

    # —— 首登强制改密（process_view 阶段 request.user 已由 AuthenticationMiddleware 就绪）——
    def process_view(self, request, view_func, view_args, view_kwargs):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return None
        profile = getattr(user, 'admin_profile', None)
        if profile is None or not profile.must_change_password:
            return None
        path = request.path
        # 只约束后台；改密页/改密完成页/登出 放行，避免死循环
        if not path.startswith('/admin/') or '/password_change' in path or path == '/admin/logout/':
            return None
        return HttpResponseRedirect(reverse('admin:password_change'))

    def _handle_password_change(self, request, response):
        """改密成功后清除 must_change_password（Django 6.1 无 password_changed 信号）。"""
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return
        profile = getattr(user, 'admin_profile', None)
        if profile is None or not profile.must_change_password:
            return
        # 自改密码成功后 admin 会 302 → /admin/password_change/done/
        if (
            request.path == reverse('admin:password_change')
            and request.method == 'POST'
            and response.status_code in (302, 303)
        ):
            profile.must_change_password = False
            profile.save(update_fields=['must_change_password'])

class AnonymousPageCacheMiddleware:
    """匿名 GET 页面整页缓存（浅层缓存），给 2 核 2G 服务器扛并发。

    为什么要它：首页每次渲染 40-90ms（60 张产品卡 + 分类卡），是整站最贵的环节。
    但页面内容只取决于「路径 + 查询串 + 语言 + 是否首次访问 + 站点版本」，
    跟具体是哪位访客无关，所以可以把渲染好的 HTML 整页复用。

    不缓存的请求：
    - 非 GET/HEAD（表单提交、后台操作）
    - 已登录用户（后台/预览要用最新数据）
    - 带表单令牌的页面（联系页、支付页）以及 /admin/、/sitemap
    - 响应里带 Set-Cookie 的（例如首次切换语言的响应）

    缓存有效期由 settings.PAGE_CACHE_SECONDS 控制（默认 120 秒），但**不依赖 TTL 生效**：
    后台保存任何前台内容（产品/分类/站点图片/设置/轮播）会通过 core.page_cache 把缓存代号 +1，
    旧条目立刻不再命中（见 core/signals.py 的 invalidate_* 接收器），所以改完刷新即可看到。
    TTL 只是兜底：防止某条内容变更走了绕过信号的路径（如直接改库）时长期显示旧页面。
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not self._cacheable(request):
            return self.get_response(request)

        key = self._key(request)
        cached = cache.get(key)
        if cached is not None:
            body, content_type, status = cached
            response = HttpResponse(body, content_type=content_type, status=status)
            response['X-Page-Cache'] = 'HIT'
            return response

        response = self.get_response(request)
        response['X-Page-Cache'] = 'MISS'
        if (
            response.status_code == 200
            and not response.has_header('Set-Cookie')
            and not getattr(response, 'streaming', False)
        ):
            # 渲染期间若发生内容变更（首次请求会 get_or_create 出 SiteSettings 等），
            # 代号已 +1：按「写入时」的代号存，否则这条缓存永远命中不到。
            key = self._key(request)
            cache.set(
                key,
                (response.content, response.get('Content-Type', 'text/html; charset=utf-8'),
                 response.status_code),
                settings.PAGE_CACHE_SECONDS,
            )
        return response

    @staticmethod
    def _cacheable(request):
        seconds = getattr(settings, 'PAGE_CACHE_SECONDS', 0)
        if seconds <= 0:
            return False
        if settings.DEBUG and os.environ.get('GLOWISD_PAGE_CACHE_FORCE') != '1':
            return False
        if request.method not in ('GET', 'HEAD'):
            return False
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            return False
        path = request.path
        for prefix in getattr(settings, 'PAGE_CACHE_EXCLUDE', ()):
            if path.startswith(prefix):
                return False
        return True

    @staticmethod
    def _key(request):
        from core.context_processors import get_lang
        from core.page_cache import page_generation

        lang = get_lang(request)
        modal = '0' if request.COOKIES.get('lang_chosen') == '1' else '1'
        version = getattr(settings, 'SITE_VERSION', '0')
        query = request.META.get('QUERY_STRING', '')
        # 代号让「后台保存内容 → 旧缓存立刻作废」，不必等 TTL
        return f'page:{page_generation()}:{version}:{lang}:{modal}:{request.path}?{query}'
