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
from django.core.cache import cache
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse

# 登录失败计数窗口与封禁时长（秒）
FAIL_WINDOW = 300        # 5 分钟失败计数窗口
FAIL_LIMIT = 5           # 同一 IP 失败达到 5 次即封禁
BLOCK_DURATION = 900     # 封禁 15 分钟

# CSP：simpleui 后台 + 前台 Vue 均有内联脚本/样式，必须保留 'unsafe-inline'（兼容妥协）；
# 'unsafe-eval'：vue.global.prod.js 是含编译器的完整构建（V0.6.4 实测缺它会抛
# EvalError → Vue 挂载失败 → 语言切换按钮/询价表单插值/simpleui 登录表单全部不渲染），
# 运行时字符串模板编译（new Function）必需；本项目无用户输入进脚本执行路径，风险可控。
CSP_VALUE = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "frame-ancestors 'none'"
)


def client_ip(request):
    """从请求取客户端 IP。

    信任模型：本函数取 X-Forwarded-For 首个值，前提是前端反代必须用【覆盖模式】
    注入 XFF（deploy/nginx-glowisd.conf 使用 `proxy_set_header X-Forwarded-For $remote_addr;`）。
    若用追加模式（$proxy_add_x_forwarded_for），客户端伪造的 XFF 会被拼在最前，
    攻击者每发一次请求换一个假 IP 即可绕过登录限流——部署时务必核对 nginx 配置。
    直连（无反代）时走 REMOTE_ADDR。
    """
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
        response.headers.setdefault('X-Frame-Options', 'DENY')
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
