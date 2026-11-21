"""整页缓存的「代号」机制：后台一改内容，前台立刻失效。

为什么不直接 cache.clear()：cache 里还存着登录限流计数（login_fail / login_block），
清空会顺带解除封禁，属于误伤。

做法（O(1)，不用遍历键）：
- cache 里存一个自增数字 `page:gen`；
- 整页缓存键前缀带上这个代号 `page:{gen}:...`；
- 后台保存任何前台内容模型时 `invalidate_page_cache()` 把代号 +1，
  旧条目再也不会被命中（等 TTL 自然过期回收），新请求重新渲染。

副作用可忽略：每次保存多写一次 cache；
但好处是「后台改完立刻生效」，不再依赖 120 秒 TTL 兜底。
"""

from django.core.cache import cache

GENERATION_KEY = 'page:gen'


def page_generation():
    """取当前代号；首次访问时初始化。读失败一律退化为 1（宁可不命中缓存，也不能出错）。"""
    try:
        value = cache.get(GENERATION_KEY)
        if value is None:
            cache.set(GENERATION_KEY, 1, None)
            return 1
        return int(value)
    except Exception:                      # 缓存后端故障时不能让整站 500
        return 1


def invalidate_page_cache():
    """让所有已缓存的整页失效（后台保存内容模型时调用）。"""
    try:
        cache.incr(GENERATION_KEY)
    except Exception:
        try:
            cache.set(GENERATION_KEY, page_generation() + 1, None)
        except Exception:
            pass
