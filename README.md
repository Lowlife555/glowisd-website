# Glowisd Website (V0.8.0)

**Changzhou Glowisd Science And Technology Co.,Ltd** official website —— a manufacturer of electronic control systems, sensors, cables and accessories for construction machinery (pavers).

Clients served: Chinese mainland + Middle East / Central Asia / Europe. Bilingual (Chinese/English), responsive (mobile / tablet / desktop).

- Live site: http://43.135.22.140:8080
- Admin panel: http://43.135.22.140:8080/admin
- Code repository: GitHub private repository `Lowlife555/glowisd-website`

---

## 1. Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend framework | Django 6.1 | Python Web framework |
| Admin UI | django-simpleui | Chinese visual admin (menus/themes deeply customizable) |
| Frontend | Vue 3 (bundled global build served from `static/vendor/vue.global.prod.js`) | Language switching / mobile navigation / inquiry form (no build step) |
| Database | SQLite | Single file, no separate database service required |
| Image processing | Pillow | Product image compression/cropping |
| UA parsing | user-agents | Login audit: parse device / operating system / browser |
| IP geolocation | py-ip2region (offline) | Login audit: IP → region (data file `core/data/ip2region_v4.xdb`, no external API dependency) |
| Production deployment | gunicorn + nginx + pm2 | Tencent Cloud, port 8080 |

---

## 2. Project Architecture

```
glowisd-website/
├── config/              # Django configuration (settings.py / urls.py / wsgi)
├── core/                # Website core: home/factory/custom/contact views + hero slides + login records
│   ├── models.py        #   HeroSlide (carousel) / LoginRecord (login records) / SiteSettings (site settings singleton)
│   ├── signals.py       #   Login success/failure signals → automatically write a login record + rate-limit counting
│   ├── audit.py         #   Audit context: UA parsing + dual-engine IP region resolution (offline ip2region / online ip-api.com / proxy flagging)
│   ├── middleware.py    #   Login rate limiting + forced password change on first login + security response headers (CSP/X-Frame-Options)
│   ├── tests.py         #   Smoke test suite (5 public pages / bilingual / inquiry / permission isolation / super-admin protection / login rate limiting / security headers)
│   ├── admin.py         #   Admin registration for carousel / login records / operation logs
│   └── templatetags/    #   Admin statistics / anomaly-highlighting template tags
├── products/            # Product module
│   ├── models.py        #   Category (product line) / Product (product) / ContactMessage (inquiry)
│   ├── admin.py         #   Product/category/inquiry admin (image thumbnails, "featured on home" checkbox)
│   ├── management/      #   Data commands: seed_data / import_pdf / import_annotations / import_product_names
│   ├── fixtures/        #   PDF-extracted data + product-name OCR data (JSON)
│   └── utils/watermark.py # Product image auto-watermark helper (called from the save hook)
├── accounts/            # Admin role system (added in V0.3.4)
│   ├── models.py        #   AdminProfile (OneToOne User: role / phone / must_change_password)
│   ├── admin.py         #   CustomUserAdmin (role management / super-admin protection / edit page redesign / reset-password action)
│   ├── utils.py         #   is_super_admin(user) check
│   ├── management/      #   ensure_super_admin (initialise the super admin + backfill roles)
│   └── templates/       #   Admin edit page templates (with recent login records embedded)
├── templates/           # Public HTML (base.html + 4 core pages + products list/detail + admin/ overrides)
├── static/              # Static assets (css/style.css + js/app.js + Vue global build + logo/favicon)
├── media/               # Runtime uploads (products/ 183 product images + hero/ carousel images)
├── deploy/              # Deployment scripts (deploy_glowisd.ps1 / deploy_init.sh / nginx / pm2 ecosystem)
├── scripts/             # Utility scripts (one-off historical scripts archived in scripts/archive/)
└── manage.py
```

**Responsibility boundaries of the four apps** (read this first when an AI takes over):
- `core` = public website pages + carousel + **login records (audit)**
- `products` = products/categories/inquiries (public pages + admin management)
- `accounts` = **admin role system** (AdminProfile + user-management admin)
- `config` = Django global configuration (including the SIMPLEUI_CONFIG menu)

---

## 3. Data Models (core)

| Model | Key fields | Notes |
|-------|-----------|-------|
| `products.Category` | name/name_en/slug/sort_order | Product line (sensors/cables/handles/displays/junction boxes/screed arms/circuit boards/membrane switches/kits/uncategorized) |
| `products.Product` | sku/part_name(_en)/pn/brand/weight/warranty/description(_en)/category/image/featured/is_watermarked | Product (182 items: 178 with images + 4 without, complete Chinese and English names); `featured=True` shows it in the home page recommendations; `is_watermarked` marks the image as already watermarked (applied automatically by the save hook + re-applied when the image is replaced) |
| `products.ContactMessage` | name/company/email/phone/country/category/message/is_read/status(new/contacted/quoted/won/lost)/quote_amount/lost_reason/inquired_product(FK)/source_page | Public inquiry messages (follow-up status management + automatic product association + source page recording) |
| `core.HeroSlide` | image/title_zh/title_en/sort_order/is_active | Home page carousel (uploaded from the admin) |
| `core.LoginRecord` | user/username_attempted/login_time/ip_address(stored only, never displayed)/region/is_proxy(suspected proxy egress)/device_type/os_name/browser/user_agent(stored only)/success/fail_reason | Login audit (both successes and failures are recorded; zero IP display on pages) |
| `accounts.AdminProfile` | user(OneToOne)/role/phone/must_change_password/created_at | Admin roles: super_admin / admin regular / viewer read-only |
| `core.SiteSettings` | company_name/address/phone/email/whatsapp/factory_area/moq/about/seo(Chinese & English)/watermark_enabled/watermark_width_pct/watermark_opacity/watermark_margin | Site settings singleton (change it once in the admin and it applies site-wide; watermark parameters are configurable) |

---

## 4. Permission System

| Role | Permissions |
|------|-------------|
| **Super admin** (super_admin, e.g. glowisd) | Everything: products/categories/inquiries/carousel + admin list + login records + operation logs; can reset other people's passwords |
| **Regular admin** (admin) | Products/categories/inquiries/carousel management; **cannot see** user management and the audit module (hidden from the sidebar + 403 on direct access) |
| **Read-only admin** (viewer) | Removed (no longer created from V0.6.0 onwards, historical viewers were converted to admin in bulk) |

**Super-admin protection rules**: deleting yourself is forbidden; demoting/deleting the last super admin is forbidden; when editing someone else the role dropdown only offers "regular" (you cannot promote others to super admin); newly added admins default to the regular role.

---

## 5. Features

**Public site (bilingual Chinese/English, 5 pages)**:
- Home: hero carousel + company name (large, gold) + big headline + product line categories + featured products block (Featured) + shop by product line + advantages + factory/customization CTA + company profile
- Product list: category filtering + SKU/P/N search + product cards (images displayed in full)
- Product detail: parameter table (SKU/P/N/brand/weight/warranty/category) + description + related products + inquiry entry
- Factory / Customization / Contact (inquiry form: honeypot + session rate limiting)

**Admin (simpleui in Chinese, grouped menu)**:
- Home dashboard: 6 statistic cards (total products / unread inquiries in red and clickable / added this week / profiles to complete / inquiries this month / active product lines) + recent inquiry activity + automatic to-do detection
- Product management: products (thumbnails / part numbers / "featured on home" checkbox / watermarked flag / re-watermark action + automatic watermarking on upload + completeness progress bar on the edit page), product categories, home carousel, **data quality check** (7 clickable statistics with pre-filtering)
- Customer messages: inquiries (five-state colored status labels / filtering / change status directly from the list / quote amount / lost reason / country statistics panel)
- Site settings: company info in Chinese and English / contact details / SEO / watermark parameters (singleton, synced to the public site)
- Admin center (super admin only): admin list (colored role labels / status / region of last login / reset password / last 10 login records embedded in the edit page), login records (4 statistic cards + yellow highlighting for anomalous logins + CSV export + failure reasons), operation logs

---

## 6. Current Version Summary

- **V0.8.0** (2026-09-03): Fixed CSP blocking the Vue runtime (`script-src` now includes `'unsafe-eval'`, restoring the language switching button / inquiry form / admin login form) + fixed the `/favicon.ico` 404.
- **V0.6.3** (2026-09-03): ALLOWED_HOSTS permanently allows localhost/127.0.0.1 (fixes server-local health checks).
- **V0.6.2** (2026-09-03): glowisd.cn domain + HTTPS launched (Let's Encrypt certificate, nginx domain block, ALLOWED_HOSTS narrowed).
- **V0.6.1** (2026-09-03): Security hardening (P1 admin login rate limiting + forced password change on first login, P2 security response headers CSP/X-Frame-Options/HSTS switch, P3 dependency security audit).
- **V0.6.0** (2026-09-01): Role system simplified (no new viewers from the admin, historical viewers can be converted to admin in bulk) + README rewritten around four menu groups + CHANGELOG split out + .env.example + unified product-image count convention.

> Full version history (V0.1.0–V0.8.0) is in [CHANGELOG.md](CHANGELOG.md).
>
> Version rules: `Va.b.c` increments in decimal, a=refactor, b=new feature, c=fix; every requirement change or fix must bump the version, commits start with `V X.Y.Z:` and are tagged.

---

## 7. Quick Start (local development)

```bash
pip install -r requirements.txt      # all dependencies (Django/simpleui/Pillow/user-agents/py-ip2region/gunicorn, versions pinned)
python manage.py migrate
python manage.py ensure_super_admin    # initialise the glowisd super admin + backfill AdminProfile
python manage.py runserver
# visit http://localhost:8000 (public) / http://localhost:8000/admin (admin)
```

Smoke tests (5 bilingual public pages / inquiry honeypot rate limiting / admin permission isolation / super-admin protection / login rate limiting / security response headers / forced password change on first login, 22 items in total):
```bash
python manage.py test core
```
> The tests use a separate test database and will not touch `db.sqlite3` or any product data.

Environment variables (required in production):
```bash
DJANGO_SECRET_KEY=<random key>   # in production read from /var/www/glowisd/.env on the server
DJANGO_DEBUG=False
```

---

## 8. Data Initialization (required reading for a fresh deployment)

> The production database `db.sqlite3` is gitignored; for a fresh deployment rebuild it in order:

| Step | Command | Purpose |
|------|---------|---------|
| 1 | `python manage.py migrate` | Create tables |
| 2 | `python manage.py seed_data` | Create the 10 product lines |
| 3 | `python manage.py import_pdf` | Import 183 product records from products/fixtures/extracted_products.json (including product image paths; 5 blank records were deleted in V0.1.8, so the current database holds 182 products) |
| 4 | `python manage.py import_annotations` | Import part numbers (R→GW rewrite) + product names |
| 5 | `python manage.py import_product_names` | Import 160 OCR Chinese/English product names |
| 6 | `python manage.py ensure_super_admin` | Create the glowisd super admin + AdminProfile |

**ip2region data file**: `core/data/ip2region_v4.xdb` (about 11MB, gitignored, not in the repository). The download URL is in the comments of `core/signals.py`; when it is missing the login region column is simply empty (the code degrades gracefully and does not affect login).

---

## 9. Deployment (Tencent Cloud)

- Server: 43.135.22.140 (Ubuntu, code in `/var/www/glowisd`, venv)
- Processes: gunicorn (managed by pm2, 127.0.0.1:8000) + nginx (0.0.0.0:8080)
- First deployment: `deploy/deploy_init.sh` (run on the server: clone the private repository + ssh key + venv + migrate + seed + nginx/pm2)
- Routine updates: locally run `deploy/deploy_glowisd.ps1` (push → pull → pip → migrate → collectstatic → pm2 restart → health)
- Secret: `SECRET_KEY` is read from `/var/www/glowisd/.env` on the server (never committed to git)

---

## 10. Admin User Guide

Log in at `/admin` (super admin glowisd) and you land on the **home dashboard**; the sidebar has **four menu groups and 9 items**:

**Home dashboard**: 6 statistic cards (total products / unread inquiries / added this week / profiles to complete / inquiries this month / active product lines) + recent inquiry activity + automatic to-do detection.

| Entry | What it does |
|-------|--------------|
| Product management → Products | Create/edit/delete products: name (Chinese/English), P/N part number, SKU, brand, weight, warranty, description, image, category; the list shows image thumbnails, a **featured on home** checkbox, a watermarked flag and a completeness progress bar; a **re-watermark** action; automatic watermarking on upload |
| Product management → Product categories | Create/edit/delete and order product lines |
| Product management → Home carousel | Upload / order / enable carousel images (with thumbnails) |
| Product management → Data quality check | 7 statistics (missing English product name / missing English description / missing weight / missing warranty / missing brand / uncategorized / duplicate SKU), each clickable to pre-filter the problematic products |
| Customer messages → Inquiries | Five-state management (new / contacted / quoted / won / lost) + country statistics + quote amount + lost reason + product association |
| Site settings → Site settings | Company info in Chinese and English / contact details / SEO / watermark parameters (singleton, one change applies site-wide) |
| Admin center → Admin list | Three-role colored labels + account status + region of last login + **reset password** action + the most recent login records embedded in the edit page |
| Admin center → Login records | Audit statistic cards + yellow highlighting for anomalous logins + CSV export (no IP) + ⚠️ proxy flagging |
| Admin center → Operation logs | View admin operation records |

**Featured on home**: tick "Featured on home" in the product list → the home page Featured block displays it automatically (8 at most).

---

## 11. Chinese/English Bilingual Mechanism

- Language detection: the `lang` cookie (manually switched by the user) takes priority, then the browser's `Accept-Language`
- Template pattern: `{% if lang == 'en' %}English{% else %}中文{% endif %}`
- Product names / category names automatically use `part_name_en` / `name_en` according to the current language
- The English site has zero hard-coded Chinese anywhere (only the language switcher "中 | EN")

---

## 12. Security Features

- **Admin login rate limiting** (V0.6.1): for `/admin/login/`, once the same IP reaches 5 failures within a 5-minute window → that IP is banned for 15 minutes (403 from the 6th attempt onwards); a successful login clears the counter automatically; counted in the Django cache by both IP and username (`core/middleware.py`)
- **Forced password change on first login** (V0.6.1): when `AdminProfile.must_change_password=True`, logging into the admin forces a redirect to the "change password" page and access is granted after a successful change (enabled automatically for new accounts created by `ensure_super_admin`, closing the "initial password = username" weak-credential hole)
- **Security response headers** (V0.6.1): `X-Frame-Options: DENY` + `Content-Security-Policy` (`default-src 'self'` + `frame-ancestors 'none'`, with `'unsafe-inline'` kept for simpleui compatibility) + nosniff + `Referrer-Policy: same-origin`; in production HSTS is enabled through the `DJANGO_HSTS_SECONDS` environment variable once HTTPS is in place
- **Dependency security audit** (V0.6.1): `pip-audit` scanned every pinned dependency in `requirements.txt`; the report is in `deploy/dependency-audit-2026-09.md` (no known CVEs at present)
- Inquiry form: honeypot field (`website`) + session rate limiting (3 times per 5 minutes)
- Production: `DEBUG=False`, `SECRET_KEY` from an environment variable (server .env), nginx reverse proxy (`$http_host` preserves the port to prevent CSRF), recommended `server_tokens off` / `proxy_hide_header Server` (see the comments in `deploy/nginx-glowisd.conf`)
- Admin: simpleui login authentication; login audit (success/failure records, anomalous regions highlighted); zero IP display on pages
- Super-admin protection: cannot delete yourself, cannot demote the last super admin, role dropdown prevents privilege escalation

---

## 13. AI Collaboration Architecture (multi-agent division of labour)

This project is developed by 4 AI agents working together; understand the division of labour when taking over:

| Agent | Responsibility |
|-------|----------------|
| **dsh** (commander) | Break down tasks → delegate → coordinate → review → documentation. Does not write core code directly |
| **Claude Code** | Multi-file core coding (Django admin/templates/feature modules) |
| **opencode** | Batch scripts / data processing / **image recognition** (vision model deepseek-v4-flash-vision-exp) |
| **hermes** | Independent acceptance testing / progress monitoring / WeChat push |

**Collaboration rules** (required reading for a new agent taking over):
- Single source of truth: `进度看板.md` (workspace docs, not in this repository) —— task status / delegation records / change records
- Mutually exclusive file editing: register in the "file lock registry" section of the board before editing and remove the entry when done
- Version numbering rules: the `glowisd-versioning` skill (this repository's `.ai-skills/`)
- Deployment experience: the `glowisd-deploy` skill
- Image recognition conventions: the `glowisd-vision-ocr` skill
- Visual acceptance: every frontend/UI change must be visually accepted with screenshots from a vision model

**Known pitfalls (for AI reference)**:
- `Set-Content -Encoding UTF8` adds a BOM and causes a Python SyntaxError → write without a BOM
- simpleui's `@admin.action` decorator attaches an ActionLocation enum and makes json.dumps fail → use a manual `short_description` instead
- In Django 6.1 `FilteredSelectMultiple.media` no longer emits widgets.css → it must be added manually in the change_form template (already added in this repository)
- The local clash TUN intercepts outbound SSH → turn TUN off or add a DIRECT rule for the server IP; when a GitHub push fails, HTTPS may still work

---

## 14. Maintenance Checklist (every version update)

1. Bump the version number (`Va.b.c`, decimal increment) + commit starting with `V X.Y.Z:` + tag it
2. Update the version history in CHANGELOG.md (keep in sync when the README features/user guide change)
3. Update the "version iteration flowchart" mermaid on the board
4. Deploy to Tencent Cloud + WeChat briefing (hermes)

---

*Last updated: V0.8.0 (2026-09-03)*

---

# Glowisd 官网（V0.8.0）

**常州市格勒威科学技术有限公司（CZ Glowisd Science And Technology Co.,Ltd）** 官方网站 —— 工程机械（摊铺机）电控系统、传感器、线缆及配件制造商。

服务客户：中国大陆 + 中东 / 中亚 / 欧洲。中英双语、响应式（手机 / 平板 / 电脑）。

- 线上地址：http://43.135.22.140:8080
- 后台管理：http://43.135.22.140:8080/admin
- 代码仓库：GitHub 私有仓库 `Lowlife555/glowisd-website`

---

## 一、技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端框架 | Django 6.1 | Python Web 框架 |
| 后台 UI | django-simpleui | 中文可视化后台（菜单/主题可深度定制） |
| 前端 | Vue 3（本地 vendor 全局构建，`static/vendor/vue.global.prod.js`） | 语言切换 / 移动导航 / 询价表单（无构建步骤） |
| 数据库 | SQLite | 单文件，无需独立数据库服务 |
| 图片处理 | Pillow | 产品图压缩/裁剪 |
| UA 解析 | user-agents | 登录审计：解析设备/操作系统/浏览器 |
| IP 归属 | py-ip2region（离线） | 登录审计：IP → 地区（数据文件 `core/data/ip2region_v4.xdb`，不依赖外网 API） |
| 生产部署 | gunicorn + nginx + pm2 | 腾讯云 8080 端口 |

---

## 二、项目架构

```
glowisd-website/
├── config/              # Django 配置（settings.py / urls.py / wsgi）
├── core/                # 网站核心：首页/工厂/定制/联系视图 + 轮播图 + 登录记录
│   ├── models.py        #   HeroSlide(轮播图) / LoginRecord(登录记录) / SiteSettings(站点设置单例)
│   ├── signals.py       #   登录成功/失败信号 → 自动写登录记录 + 限流计数
│   ├── audit.py         #   审计上下文：UA解析 + IP双引擎地区解析（离线ip2region/在线ip-api.com/代理标注）
│   ├── middleware.py    #   登录限流 + 首登强制改密 + 安全响应头（CSP/X-Frame-Options）
│   ├── tests.py         #   冒烟测试套件（前台5页/双语/询价/权限隔离/超管保护/登录限流/安全头）
│   ├── admin.py         #   轮播图/登录记录/操作日志的后台注册
│   └── templatetags/    #   后台统计/异常高亮模板标签
├── products/            # 产品模块
│   ├── models.py        #   Category(产品线) / Product(产品) / ContactMessage(询价)
│   ├── admin.py         #   产品/分类/询价后台（图片缩略图、首页推荐勾选）
│   ├── management/      #   数据命令：seed_data / import_pdf / import_annotations / import_product_names
│   ├── fixtures/        #   PDF 提取数据 + 品名 OCR 数据（JSON）
│   └── utils/watermark.py # 产品图自动打水印工具函数（save 钩子调用）
├── accounts/            # 管理员角色体系（V0.3.4 新增）
│   ├── models.py        #   AdminProfile（OneToOne User：role 角色 / phone / must_change_password）
│   ├── admin.py         #   CustomUserAdmin（角色管理/超管保护/编辑页重设计/重置密码 action）
│   ├── utils.py         #   is_super_admin(user) 判断
│   ├── management/      #   ensure_super_admin（初始化超管+补角色）
│   └── templates/       #   管理员编辑页模板（内嵌最近登录记录）
├── templates/           # 前台 HTML（base.html + core/ 4页 + products/ 列表详情 + admin/ 后台覆盖）
├── static/              # 静态资源（css/style.css + js/app.js + Vue 全局构建 + logo/favicon）
├── media/               # 运行时上传（products/ 183张产品图 + hero/ 轮播图）
├── deploy/              # 部署脚本（deploy_glowisd.ps1 / deploy_init.sh / nginx / pm2 ecosystem）
├── scripts/             # 工具脚本（一次性历史脚本已归档至 scripts/archive/）
└── manage.py
```

**四个 app 的职责边界**（AI 接手时先看这个）：
- `core` = 网站公开页面 + 轮播 + **登录记录（审计）**
- `products` = 产品/分类/询价（公开页 + 后台管理）
- `accounts` = **管理员角色体系**（AdminProfile + 用户管理后台）
- `config` = Django 全局配置（含 SIMPLEUI_CONFIG 菜单）

---

## 三、数据模型（核心）

| 模型 | 关键字段 | 说明 |
|------|---------|------|
| `products.Category` | name/name_en/slug/sort_order | 产品线（传感器/线缆/手柄/显示器/接线盒/找平臂/电路板/膜开关/套件/未分类） |
| `products.Product` | sku/part_name(_en)/pn/brand/weight/warranty/description(_en)/category/image/featured/is_watermarked | 产品（182 个：178 有图 + 4 无图，中英文品名齐全）；`featured=True` 首页推荐展示；`is_watermarked` 标记图片已打水印（save 钩子自动打 + 换图重打） |
| `products.ContactMessage` | name/company/email/phone/country/category/message/is_read/status(新/已联系/已报价/已成交/已流失)/quote_amount/lost_reason/inquired_product(FK)/source_page | 前台询价留言（跟进状态管理 + 产品自动关联 + 来源页面记录） |
| `core.HeroSlide` | image/title_zh/title_en/sort_order/is_active | 首页轮播图（后台上传） |
| `core.LoginRecord` | user/username_attempted/login_time/ip_address(仅存不展示)/region/is_proxy(疑似代理出口)/device_type/os_name/browser/user_agent(仅存)/success/fail_reason | 登录审计（成功+失败都记录；页面零 IP 显示） |
| `accounts.AdminProfile` | user(OneToOne)/role/phone/must_change_password/created_at | 管理员角色：super_admin 超管 / admin 普通 / viewer 只读 |
| `core.SiteSettings` | company_name/address/phone/email/whatsapp/factory_area/moq/about/seo(中英)/watermark_enabled/watermark_width_pct/watermark_opacity/watermark_margin | 站点设置单例（后台一处修改全站生效；水印参数可配置） |

---

## 四、权限体系

| 角色 | 权限 |
|------|------|
| **超级管理员**（super_admin，如 glowisd） | 全部：产品/分类/询价/轮播 + 管理员列表 + 登录记录 + 操作日志；可重置他人密码 |
| **普通管理员**（admin） | 产品/分类/询价/轮播管理；**看不到**用户管理和审计模块（侧边栏隐藏 + 直接访问 403） |
| **只读管理员**（viewer） | 已移除（V0.6.0 起后台不再新增，历史 viewer 已批量转 admin） |

**超管保护规则**：禁止删除自己；禁止把最后一个超管降级/删除；编辑他人时角色下拉只出现"普通"（不能把别人提为超管）；新增管理员默认普通角色。

---

## 五、功能特性

**前台（中英双语，5 页面）**：
- 首页：Hero 轮播 + 公司名（金色大号）+ 大标题 + 产品线分类 + 推荐产品区块（Featured）+ 按产品线陈列（Shop by Product Line）+ 优势 + 工厂/定制 CTA + 公司简介
- 产品列表：分类筛选 + SKU/P/N 搜索 + 产品卡片（图片完整显示）
- 产品详情：参数表（SKU/P/N/品牌/重量/质保/分类）+ 描述 + 相关产品 + 询价入口
- 工厂 / 定制 / 联系（询价表单：蜜罐 + 会话限流）

**后台（simpleui 中文，菜单分组）**：
- 首页仪表盘：6 统计卡片（产品总数/未读询价红色可点/本周新增/资料待完善/本月询价/活跃产品线）+ 最近询价动态 + 待办事项自动检测
- 产品管理：产品（缩略图/件号/首页推荐勾选/已打水印标记/重新打水印 action + 上传自动打水印 + 编辑页完整度进度条）、产品分类、首页轮播、**数据质量检查**（7 项统计可点击预筛选）
- 客户消息：询价留言（状态五态彩色标签/筛选/列表直接改状态/报价金额/流失原因/国家统计面板）
- 站点设置：公司信息中英/联系方式/SEO/水印参数（单例，前台同步）
- 管理员中心（仅超管）：管理员列表（角色彩色标签/状态/上次登录地区/重置密码/编辑页内嵌最近 10 次登录记录）、登录记录（4 统计卡片 + 异常登录黄色高亮 + CSV 导出 + 失败原因）、操作日志

---

## 六、当前版本摘要

- **V0.8.0**（2026-09-03）：修复 CSP 拦截 Vue 运行时（`script-src` 补 `'unsafe-eval'`，语言切换按钮/询价表单/后台登录表单恢复）+ `/favicon.ico` 404 修复。
- **V0.6.3**（2026-09-03）：ALLOWED_HOSTS 常驻放行 localhost/127.0.0.1（服务器本地健康检查修复）。
- **V0.6.2**（2026-09-03）：glowisd.cn 域名 + HTTPS 上线（Let's Encrypt 证书、nginx 域名块、ALLOWED_HOSTS 收窄）。
- **V0.6.1**（2026-09-03）：安全性开发（P1 后台登录限流 + 首登强制改密、P2 安全响应头 CSP/X-Frame-Options/HSTS 开关、P3 依赖安全审计）。
- **V0.6.0**（2026-09-01）：角色体系精简（后台不再新增 viewer，历史 viewer 可批量转 admin）+ README 四组菜单重写 + CHANGELOG 拆分 + .env.example + 产品图数量口径统一。

> 完整版本历史（V0.1.0–V0.8.0）见 [CHANGELOG.md](CHANGELOG.md)。
>
> 版本规则：`Va.b.c` 十进制递增，a=重构、b=新功能、c=修复；每次需求变更或修复必须升版本，commit 以 `V X.Y.Z:` 开头并打 tag。

---

## 七、快速开始（本地开发）

```bash
pip install -r requirements.txt      # 全部依赖（Django/simpleui/Pillow/user-agents/py-ip2region/gunicorn 已锁定版本）
python manage.py migrate
python manage.py ensure_super_admin    # 初始化 glowisd 超管 + 补 AdminProfile
python manage.py runserver
# 访问 http://localhost:8000（前台）/ http://localhost:8000/admin（后台）
```

冒烟测试（前台 5 页双语 / 询价蜜罐限流 / 后台权限隔离 / 超管保护 / 登录限流 / 安全响应头 / 首登改密，共 22 项）：
```bash
python manage.py test core
```
> 测试使用独立测试库，不会碰 `db.sqlite3` 或任何产品数据。

环境变量（生产必须）：
```bash
DJANGO_SECRET_KEY=<随机密钥>   # 生产从服务器 /var/www/glowisd/.env 读取
DJANGO_DEBUG=False
```

---

## 八、数据初始化（全新部署必读）

> 生产数据库 `db.sqlite3` 被 gitignore，全新部署按顺序重建：

| 步骤 | 命令 | 作用 |
|------|------|------|
| 1 | `python manage.py migrate` | 建表 |
| 2 | `python manage.py seed_data` | 建 10 个产品线 |
| 3 | `python manage.py import_pdf` | 从 products/fixtures/extracted_products.json 导入 183 条产品记录（含产品图路径；其中 5 条空白记录已于 V0.1.8 删除，现库 182 个产品） |
| 4 | `python manage.py import_annotations` | 导入件号（R→GW 改写）+ 品名 |
| 5 | `python manage.py import_product_names` | 导入 160 个 OCR 中英文品名 |
| 6 | `python manage.py ensure_super_admin` | 创建 glowisd 超管 + AdminProfile |

**ip2region 数据文件**：`core/data/ip2region_v4.xdb`（约 11MB，gitignore 未入库）。下载地址见 `core/signals.py` 注释；缺失时登录地区列为空（代码优雅降级，不影响登录）。

---

## 九、部署（腾讯云）

- 服务器：43.135.22.140（Ubuntu，代码 `/var/www/glowisd`，venv）
- 进程：gunicorn（pm2 管理，127.0.0.1:8000）+ nginx（0.0.0.0:8080）
- 首次部署：`deploy/deploy_init.sh`（服务器执行：clone 私有仓库 + ssh key + venv + migrate + seed + nginx/pm2）
- 日常更新：本地 `deploy/deploy_glowisd.ps1`（push → pull → pip → migrate → collectstatic → pm2 restart → health）
- 密钥：`SECRET_KEY` 从服务器 `/var/www/glowisd/.env` 读取（不进 git）

---

## 十、后台使用指南

登录 `/admin`（超管 glowisd），进入后即**首页仪表盘**，侧边栏共**四组菜单 9 项**：

**首页仪表盘**：6 统计卡片（产品总数 / 未读询价 / 本周新增 / 资料待完善 / 本月询价 / 活跃产品线）+ 最近询价动态 + 待办事项自动检测。

| 入口 | 能做什么 |
|------|----------|
| 产品管理 → 产品 | 产品增删改：品名(中/英)、P/N 件号、SKU、品牌、重量、质保、描述、图片、所属分类；列表含图片缩略图、**首页推荐**勾选、已打水印标记、完整度进度条；**重新打水印** action；上传自动打水印 |
| 产品管理 → 产品分类 | 产品线增删改 + 排序 |
| 产品管理 → 首页轮播 | 轮播图上传 / 排序 / 启用（含缩略图） |
| 产品管理 → 数据质量检查 | 7 项统计（缺英文品名 / 缺英文描述 / 缺重量 / 缺质保 / 缺品牌 / 未分类 / SKU 重复），每项可点击预筛选问题产品 |
| 客户消息 → 询价留言 | 五态管理（新 / 已联系 / 已报价 / 已成交 / 已流失）+ 国家统计 + 报价金额 + 流失原因 + 产品关联 |
| 站点设置 → 站点设置 | 公司信息中英 / 联系方式 / SEO / 水印参数（单例，改一处全站生效） |
| 管理员中心 → 管理员列表 | 三角色彩色标签 + 账号状态 + 上次登录地区 + **重置密码** action + 编辑页内嵌最近登录记录 |
| 管理员中心 → 登录记录 | 审计统计卡片 + 异常登录黄色高亮 + CSV 导出（无 IP）+ ⚠️代理标注 |
| 管理员中心 → 操作日志 | 查看后台操作记录 |

**首页推荐**：产品列表勾选「首页推荐」→ 首页 Featured 区块自动展示（最多 8 个）。

---

## 十一、中英双语机制

- 语言判断：Cookie `lang`（用户手动切换）优先，其次浏览器 `Accept-Language`
- 模板写法：`{% if lang == 'en' %}English{% else %}中文{% endif %}`
- 产品名/分类名按当前语言自动取 `part_name_en` / `name_en`
- 英文版全站零中文硬编码（仅语言切换器「中 | EN」）

---

## 十二、安全特性

- **后台登录限流**（V0.6.1）：`/admin/login/` 同一 IP 5 分钟窗口内失败满 5 次 → 封禁该 IP 15 分钟（第 6 次起 403）；登录成功自动清除计数；按 IP 与用户名双维度在 Django cache 计数（`core/middleware.py`）
- **首登强制改密**（V0.6.1）：`AdminProfile.must_change_password=True` 时登录后台后强制跳转「修改密码」页，改密成功后放行（配合 `ensure_super_admin` 新账号自动开启，堵住「初始密码=用户名」弱口令）
- **安全响应头**（V0.6.1）：`X-Frame-Options: DENY` + `Content-Security-Policy`（`default-src 'self'` + `frame-ancestors 'none'`，simpleui 兼容保留 `'unsafe-inline'`）+ nosniff + `Referrer-Policy: same-origin`；HSTS 生产 HTTPS 后经环境变量 `DJANGO_HSTS_SECONDS` 开启
- **依赖安全审计**（V0.6.1）：`pip-audit` 扫描 `requirements.txt` 全量锁定依赖，报告见 `deploy/dependency-audit-2026-09.md`（当前无已知 CVE）
- 询价表单：蜜罐字段（`website`）+ 会话限流（5 分钟 3 次）
- 生产：`DEBUG=False`、`SECRET_KEY` 环境变量（服务器 .env）、nginx 反代（`$http_host` 保留端口防 CSRF）、`server_tokens off` / `proxy_hide_header Server` 建议（见 `deploy/nginx-glowisd.conf` 注释）
- 后台：simpleui 登录鉴权；登录审计（成功/失败记录、异常地区高亮）；页面零 IP 显示
- 超管保护：禁删自己、禁降级最后超管、角色下拉防提权

---

## 十三、AI 协作架构（多 agent 分工）

本项目由 4 个 AI agent 协作开发，接手时了解分工：

| Agent | 职责 |
|-------|------|
| **dsh**（指挥官） | 拆解任务 → 委派 → 协调 → 审查 → 文档。不直接写核心代码 |
| **Claude Code** | 多文件核心编码（Django 后台/模板/功能模块） |
| **opencode** | 批量脚本 / 数据处理 / **识图**（vision 模型 deepseek-v4-flash-vision-exp） |
| **hermes** | 独立验收测试 / 进度监控 / 微信推送 |

**协作规范**（新 agent 接手必读）：
- 唯一真相源：`进度看板.md`（工作区 docs，不在本仓库）——任务状态/委派记录/变更记录
- 文件编辑互斥：编辑前在看板「文件锁登记」区登记，完成后删除
- 版本号规则：`glowisd-versioning` skill（本仓库 `.ai-skills/`）
- 部署经验：`glowisd-deploy` skill
- 识图规范：`glowisd-vision-ocr` skill
- 视觉验收：所有前端/界面改动必须用 vision 模型截图验收

**已知踩坑（供 AI 参考）**：
- `Set-Content -Encoding UTF8` 会加 BOM 导致 Python SyntaxError → 用无 BOM 写入
- simpleui 的 `@admin.action` 装饰器挂 ActionLocation 枚举导致 json.dumps 报错 → 改手动 `short_description`
- Django 6.1 的 `FilteredSelectMultiple.media` 不再输出 widgets.css → 需在 change_form 模板手动补（本仓库已补）
- 本机 clash TUN 会拦截 SSH 出站 → 关 TUN 或给服务器 IP 加 DIRECT 规则；GitHub push 失败时 HTTPS 可通

---

## 十四、维护清单（每次版本更新）

1. 升版本号（`Va.b.c` 十进制递增）+ commit 以 `V X.Y.Z:` 开头 + 打 tag
2. 更新 CHANGELOG.md 版本历史（README 特性/使用指南有变化时同步）
3. 更新看板「版本迭代流程图」mermaid
4. 部署腾讯云 + 微信简报（hermes）

---

*最后更新：V0.8.0（2026-09-03）*
