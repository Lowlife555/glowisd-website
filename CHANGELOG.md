# CHANGELOG

Glowisd 官网版本历史（V0.1.0–V0.9.0，按日期倒序）。版本规则：`Va.b.c` 十进制递增（a=重构、b=新功能、c=修复），每次需求变更或修复必升版本。

## V0.9.0（2026-11-08）

- **定价体系**：`Product` 新增 `price`（默认 99999 防拍价）/`currency`（USD/CNY/EUR/GBP）/`payment_link`（外部收款页，可选）。未定价产品全站展示 99999 且隐藏购买按钮，只保留「联系确认价格」；后台改成真实价格后前台立即出现「立即购买」
- **后台实时改价**：产品列表 `list_editable` 直接改售价与币种，保存即生效；新增「定价状态」筛选（待定价 / 可下单）；编辑页自动生成该产品的支付链接（`https://glowisd.cn/pay/<id>/`，可直接发给客户）
- **在线支付（Visa / MasterCard / 银联 / 支付宝 / 微信支付）**：新增 `payments` app。每个已定价产品有固定收银台 `/pay/<id>/`：选择支付方式 + 填写联系方式 → 生成订单 → 跳转 Stripe Checkout 真实收款（银行卡 / 支付宝 / 微信支付，含 `checkout.session.completed` webhook 验签与服务端回跳核对）；未配置 `STRIPE_SECRET_KEY` 时自动降级为「人工确认下单」，订单照样入库
- **订单管理**：`payments.Order`（订单号 `GW日期-随机码`、产品名/单价快照、金额币种、支付方式、状态、通道流水号、客户信息、支付时间），后台「订单与收款 → 订单」列表可直接改状态，改成「已支付」自动写入支付时间
- **收银台/结果页**：双语收银台（订单摘要 + 五种方式选择 + 联系方式 + 金额随数量实时计算）、支付成功/待支付、支付取消页面；`noindex` 防止搜索引擎收录交易页；下单按 IP 限流（20 单/小时）+ 蜜罐字段
- **视觉调整**：产品卡与详情页新增价格行/购买区；产品列表改为 24 款/页分页（原 182 款一页到底约 1.6 万像素）；首页分类卡片隐藏 0 款与「未分类」（避免一屏「0 款」的空卡片）；手机端产品卡与分类卡改双列（页面长度减半）；页头/页脚 logo 用 `mix-blend-mode: multiply` 融入浅色背景，去掉白底方块
- **配置**：`settings.py` 支持读取项目根目录 `.env`（Stripe 密钥不进 git）；`SITE_VERSION` 0.8.0 → 0.9.0；新增 `payments` app、simpleui 菜单「订单与收款」；`requirements.txt` 增加 `stripe==16.1.0`
- **测试**：新增 21 条（定价默认值/未定价拦截/收银台五方式/下单与快照/校验与限流/成功页/幂等标记已付/取消/Stripe 方式映射与微信 web client/webhook 验签与标记/后台列表改价/订单后台/分页/首页分类过滤），全站 46 条全绿

## V0.8.0（2026-09-03）

- 站点图片后台可替换：新增 `SiteImage` 模型（7 个固定槽位：首页工厂区块、工厂页厂房全景、车间照片 1-4、定制页服务图），后台「站点设置 → 站点图片」上传即替换前台展示，支持中英图片说明（alt/SEO）；未上传自动回退占位图
- 后台界面可用性收紧：站点图片槽位由系统预设，隐藏「增加/删除」（防重复槽位与误删）；列表显示图片预览与「未上传」状态
- 测试新增 3 条（槽位完整性、上传后前台渲染、无图回退占位图），共 25 条全绿

## V0.7.2（2026-09-03）

- Cloudflare 接入适配：真实 IP 提取优先 `CF-Connecting-IP`（core/middleware.py client_ip + core/audit.py），保证走 CF 后登录限流按真实客户端 IP 计数、登录审计显示真实地区，而不是所有访客都变成 CF 节点 IP

## V0.7.1（2026-09-03）

- 后台管理界面标题：浏览器标签页名称改为「Glowisd站点管理员」，页头改为「Glowisd 站点管理」

## V0.7.0（2026-09-03）

- SEO 收录基础设施：新增 `/sitemap.xml`（django.contrib.sitemaps：5 个静态页 + 182 个产品详情页，含 lastmod）+ `/robots.txt`（允许全部爬虫 + 声明 Sitemap 地址）；配合百度/Google/必应站长平台提交后可被搜索引擎收录

## V0.6.5（2026-09-03）

- **修复后台功能全部失效**：V0.6.1 的 CSP `frame-ancestors 'none'` + `X-Frame-Options: DENY` 拒绝一切 iframe 嵌入，而 simpleui 后台架构 = 左侧菜单 + 右侧同源 iframe 加载功能页 → 后台所有功能页被拦（console：Framing 'https://glowisd.cn/' violates CSP frame-ancestors 'none'）。修复：`frame-ancestors 'self'` + `X-Frame-Options: SAMEORIGIN`（同源嵌入放行，跨源嵌入依旧拒绝，防点击劫持目标不变）

## V0.6.4（2026-09-03）

- **修复 CSP 拦截 Vue 运行时报错**：V0.6.1 的 CSP `script-src 'self' 'unsafe-inline'` 缺少 `'unsafe-eval'`，vue.global.prod.js（含编译器完整构建）运行时编译字符串模板需 `new Function`，被 CSP 拦截抛 `Uncaught EvalError` → Vue 挂载失败，导致前台语言切换按钮消失、询价表单 `{{ }}` 插值未渲染、后台 simpleui 登录表单（el-input）空白。修复：`script-src` 增加 `'unsafe-eval'`（本项目无用户输入进脚本执行路径，风险可控）
- 顺手修 `/favicon.ico` 404：`config/urls.py` 加重定向到 `/static/favicon.ico`，static 根补 favicon.ico 文件

## V0.6.3（2026-09-03）

- ALLOWED_HOSTS 常驻放行 localhost/127.0.0.1（修复 V0.6.2 收窄后服务器本地健康检查 400），testserver 仅 DEBUG 放行

## V0.6.2（2026-09-03）

- glowisd.cn 域名上线：nginx 域名块 80/443 + Let's Encrypt 证书 + ALLOWED_HOSTS 收窄 + SECURE_PROXY_SSL_HEADER/CSRF_TRUSTED_ORIGINS；新增 deploy/nginx-glowisd-domain.conf

## V0.6.1（2026-09-03）

- P1 后台登录限流：`core/middleware.py::LoginRateLimitMiddleware` 拦截 `/admin/login/` 的 POST，同一 IP 5 分钟窗口内失败满 5 次封禁 15 分钟（第 6 次起 403）；复用 `user_login_failed` 信号按 IP + username 双维度计数，`user_logged_in` 成功登录清除计数
- P1 首登强制改密：`AdminProfile.must_change_password` 在登录流程真正生效——认证后重定向到改密页、改密成功清除标记；`ensure_super_admin` 新账号自动开启该标记，堵住「初始密码=用户名」弱口令
- P2 安全响应头：显式 `X-Frame-Options: DENY` + `Content-Security-Policy`（`frame-ancestors 'none'`，simpleui 兼容保留 `'unsafe-inline'`）+ nosniff + `Referrer-Policy: same-origin`；HSTS 生产环境变量开关；nginx 注释建议 `server_tokens off` / `proxy_hide_header Server`
- P3 依赖安全审计：`pip-audit` 扫描 requirements.txt 全量锁定依赖，无已知 CVE，报告见 `deploy/dependency-audit-2026-09.md`
- 测试：core 测试套件 18 → 22 项（新增登录限流/成功清除计数/安全响应头/首登改密）

## V0.6.0（2026-09-01）

- 角色体系精简（后台不再新增 viewer，历史 viewer 可批量转 admin）+ README 四组菜单重写 + CHANGELOG 拆分 + .env.example + 产品图数量口径统一
- ip2region 下载链接验证有效

## V0.5.2（2026-09-01）

- 收尾清理 + 回归：真正删除 settings.py MAILERS 死配置（V0.5.0 清单遗漏）+ 删除 .gitignore 6 条失效规则 + 部署脚本对齐 ensure_super_admin + deploy_glowisd.ps1 条件提交（无改动不产生空提交）+ 时区回归测试（formatted_time/__str__/CSV 北京时间 + date_hierarchy 分组结论）

## V0.5.1（2026-09-01）

- 登录记录时间显示修复：DB 按 UTC 存储（USE_TZ=True），列表页时间列与模型 __str__ 未转时区导致少 8 小时，统一 timezone.localtime 转北京时间（Asia/Shanghai）；历史记录自动显示正确，CSV 导出/编辑页原本已正确

## V0.5.0（2026-09-01）

- 纯清理型重构：P0 物理删除残留（node_modules 173MB/prisma/两个图片备份目录 11MB/favicon_backup/db 水印备份/accounts.views 样板/3 个空 tests.py/发现 MAILERS 死配置）；P1 requirements.txt 全版本锁定（含 gunicorn）+ 新增 14 项冒烟测试套件 core/tests.py + 修复 watermark 死引用注释；P2 登录审计拆出 core/audit.py + 一次性脚本归档 scripts/archive/

## V0.4.2（2026-09-01）

- 登录地点双引擎解析：大陆走离线 ip2region（省·市），海外/港澳台走在线 ip-api.com（国家·州·市 城市级中文，3 秒超时+离线兜底）；新增 is_proxy 字段，ISP 命中代理/数据中心关键词时登录记录红色标「⚠️代理」；修复香港机场 IP 被离线库误判成 Delhi·Delhi

## V0.4.1（2026-09-01）

- 缓存根治 cache busting：SITE_VERSION 常量+context processor，前台所有静态/媒体资源 URL 加 `?v=版本`（logo/favicon/css/js/产品图/轮播图），footer 版本号动态显示；修复老设备强缓存不过期导致刷不到新图

## V0.4.0（2026-09-01）

- 水印位置改左上角（183 张图从 git 原图恢复后全量重打，SiteSettings 默认 top_left+数据迁移）+ 全站缓存策略修复（nginx 30 天强缓存 → no-cache+ETag/304，更新后访客立即可见）

## V0.3.8（2026-09-01）

- 产品图自动打水印：is_watermarked 字段+save()自动触发（换图检测防重复）+ watermark_all 批量命令 + 178 张图打水印（宽18%/不透明75%/右下角25px）

## V0.3.7（2026-08-31）

- 产品数据质量检查页（7 项统计+预筛选+编辑页完整度进度条）+ SiteSettings 单例站点设置（公司信息中英/SEO/WhatsApp+前台模板去硬编码）

## V0.3.6（2026-08-31）

- 询价管理升级：status 五态（新/已联系/已报价/已成交/已流失）+ 报价金额 + 流失原因 + 产品关联 + 来源页面 + 状态彩色标签 + 国家统计

## V0.3.5（2026-08-31）

- 后台首页重设计（6 统计卡片+询价动态+待办事项，移除最近动作）+ 操作日志入管理员中心 + 中文版首页公司名改英文同步

## V0.3.4（2026-08-31）

- 后台管理员界面四阶段迭代：accounts 角色体系（超管/管理员/只读）+ 登录追踪（成功/失败记录）+ 编辑页重设计（去技术字段+内嵌登录记录+重置密码）+ 菜单三组重组 + 统计卡片/异常高亮/CSV 导出

## V0.3.0（2026-08-31）

- 超管体系：权限收口（用户/组/登录记录/日志仅超管可见+普通管理员 403）+ 登录审计增强（设备/OS/浏览器/地区解析，列表隐藏 IP）+ 超管保护（禁删自己/最后超管）

## V0.2.2（2026-08-31）

- 后台轮播图列表缩略图修复

## V0.2.1（2026-08-31）

- 版本规则强化（每次修复必升版）+ 版本号 V0.2.0→V0.2.1 + 后台排版修复 + 右上角用户名菜单「退出登录」改「切换账号」+ 用户编辑页小部件修复

## V0.2.0（2026-08-29）

- 首页推荐产品区块 + 产品线分区陈列 + 后台增强（图片预览/分类产品数）+ 160 品名 OCR 导入 + 英文版全站去中文

## V0.1.8（2026-08-29）

- 产品图最终重裁居中占 90% + footer 黑灰恢复 + favicon 多尺寸 + nginx CSRF 修复

## V0.1.2（2026-08-29）

- 腾讯云部署脚本 + 生产安全配置（gunicorn/nginx 8080，SECRET_KEY/DEBUG 环境变量）+ 同步公司信息 + 产品件号 GW 改写 + 品名识别 + 产品图重裁 + logo 取色 + SVG 图标 + 配色深蓝金重构 + 首页 Hero 6 图轮播

## V0.1.1（2026-08-28）

- 技术栈改 Django + simpleui + Vue 3（5 页面 + 中英双语 + 询价 + 183 产品照片）

## V0.1.0（2026-08-28）

- Glowisd 官网雏形（Next.js）— 中英双语 / 产品目录 / 询价表单 / 后台管理（含安全底线）
