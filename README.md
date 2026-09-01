# Glowisd 官网（V0.5.1）

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
| 前端 | Vue 3（CDN 全局构建） | 语言切换 / 移动导航 / 询价表单（无构建步骤） |
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
│   ├── models.py        #   HeroSlide(轮播图) / LoginRecord(登录记录)
│   ├── signals.py       #   登录成功/失败信号 → 自动写登录记录
│   ├── audit.py         #   审计上下文：UA解析 + IP双引擎地区解析（离线ip2region/在线ip-api.com/代理标注）
│   ├── tests.py         #   冒烟测试套件（前台5页/双语/询价/权限隔离/超管保护）
│   ├── admin.py         #   轮播图/登录记录/操作日志的后台注册
│   └── templatetags/    #   后台统计/异常高亮模板标签
├── products/            # 产品模块
│   ├── models.py        #   Category(产品线) / Product(产品) / ContactMessage(询价)
│   ├── admin.py         #   产品/分类/询价后台（图片缩略图、首页推荐勾选）
│   ├── management/      #   数据命令：seed_data / import_pdf / import_annotations / import_product_names
│   └── fixtures/        #   PDF 提取数据 + 品名 OCR 数据（JSON）
├── accounts/            # 管理员角色体系（V0.3.4 新增）
│   ├── models.py        #   AdminProfile（OneToOne User：role 角色 / phone / must_change_password）
│   ├── admin.py         #   CustomUserAdmin（角色管理/超管保护/编辑页重设计/重置密码 action）
│   ├── utils.py         #   is_super_admin(user) 判断
│   ├── management/      #   ensure_super_admin（初始化超管+补角色）
│   └── templates/       #   管理员编辑页模板（内嵌最近登录记录）
├── templates/           # 前台 HTML（base.html + core/ 4页 + products/ 列表详情 + admin/ 后台覆盖）
├── static/              # 静态资源（css/style.css + js/app.js + Vue 全局构建 + logo/favicon）
├── media/               # 运行时上传（products/ 182张产品图 + hero/ 轮播图）
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
| `products.Product` | sku/part_name(_en)/pn/brand/weight/warranty/description(_en)/category/image/featured/is_watermarked | 产品（182 个，中英文品名齐全）；`featured=True` 首页推荐展示；`is_watermarked` 标记图片已打水印（save 钩子自动打 + 换图重打） |
| `products.ContactMessage` | name/company/email/phone/country/category/message/is_read/status(新/已联系/已报价/已成交/已流失)/quote_amount/lost_reason/inquired_product(FK)/source_page | 前台询价留言（跟进状态管理 + 产品自动关联 + 来源页面记录） |
| `core.HeroSlide` | image/title_zh/title_en/sort_order/is_active | 首页轮播图（后台上传） |
| `core.LoginRecord` | user/username_attempted/login_time/ip_address(仅存不展示)/region/device_type/os_name/browser/user_agent(仅存)/success/fail_reason | 登录审计（成功+失败都记录；页面零 IP 显示） |
| `accounts.AdminProfile` | user(OneToOne)/role/phone/must_change_password/created_at | 管理员角色：super_admin 超管 / admin 普通 / viewer 只读 |
| `core.SiteSettings` | company_name/address/phone/email/whatsapp/factory_area/moq/about/seo(中英)/watermark_enabled/watermark_width_pct/watermark_opacity/watermark_margin | 站点设置单例（后台一处修改全站生效；水印参数可配置） |

---

## 四、权限体系（V0.3.4）

| 角色 | 权限 |
|------|------|
| **超级管理员**（super_admin，如 glowisd） | 全部：产品/分类/询价/轮播 + 管理员列表 + 登录记录 + 操作日志；可重置他人密码 |
| **普通管理员**（admin） | 产品/分类/询价/轮播管理；**看不到**用户管理和审计模块（侧边栏隐藏 + 直接访问 403） |
| **只读管理员**（viewer） | 预留角色（当前界面与 admin 相同，后续可细化只读） |

**超管保护规则**：禁止删除自己；禁止把最后一个超管降级/删除；编辑他人时角色下拉只出现"普通/只读"（不能把别人提为超管）；新增管理员默认普通角色。

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

## 六、版本历史（摘要）

| 版本 | 核心改动 |
|------|---------|
| V0.1.0–V0.1.7 | Next.js 雏形 → Django 重构 → 部署/公司信息/件号 GW/产品图裁剪/配色/Hero 轮播 |
| V0.1.8 | 产品图居中占 90% + footer 黑灰 + favicon |
| V0.2.0 | 首页推荐 + 产品线陈列 + 后台增强 + 160 品名 OCR + 英文版去中文 |
| V0.2.1–V0.2.2 | 版本纪律强化 + 后台排版修复 + 轮播图缩略图 |
| V0.3.0 | 超管体系初版：权限收口 + 登录审计（IP 隐藏/设备地区解析）+ 超管保护 |
| V0.3.4 | 后台四阶段重构：accounts 角色体系（三角色）+ 失败登录记录 + 编辑页重设计（内嵌登录记录/重置密码）+ 菜单三组重组 + 统计卡片/异常高亮/CSV |
| V0.3.5 | 后台首页仪表盘（6 统计卡片+询价动态+待办）+ 操作日志入管理员中心 + 中文版公司名英文同步 |
| V0.3.6 | 询价管理升级：status 五态+报价金额+流失原因+产品关联+来源页面+状态彩色标签+国家统计 |
| V0.3.7 | 产品数据质量检查页（7 项统计+预筛选+完整度进度条）+ SiteSettings 站点设置（前台去硬编码） |
| **V0.3.8** | 产品图自动打水印：is_watermarked+save()自动触发（换图防重复）+watermark_all 批量命令+178 张图打水印（宽18%/不透明75%/右下角25px，vision 采样） |
| **V0.4.0** | 水印位置改左上角（183 张图从 git 原图恢复后全量重打，SiteSettings 默认 top_left+数据迁移）+ 全站缓存策略修复（nginx 30 天强缓存 → no-cache+ETag/304，更新后访客立即可见） |
| **V0.4.1** | 缓存根治 cache busting：SITE_VERSION 常量+context processor，前台所有静态/媒体资源 URL 加 `?v=版本`（logo/favicon/css/js/产品图/轮播图），footer 版本号动态显示；修复老设备强缓存不过期导致刷不到新图 |
| **V0.4.2** | 登录地点双引擎解析：大陆走离线 ip2region（省·市），海外/港澳台走在线 ip-api.com（国家·州·市 城市级中文，3 秒超时+离线兜底）；新增 is_proxy 字段，ISP 命中代理/数据中心关键词时登录记录红色标"⚠️代理"；修复香港机场 IP 被离线库误判成 Delhi·Delhi |
| **V0.5.0** | 纯清理型重构：P0 物理删除残留（node_modules 173MB/prisma/两个图片备份目录 11MB/favicon_backup/db 水印备份/accounts.views 样板/3 个空 tests.py/MAILERS 死配置）；P1 requirements.txt 全版本锁定（含 gunicorn），部署脚本只依赖 requirements.txt，新增 14 项冒烟测试套件（core/tests.py：前台 5 页双语/询价蜜罐限流/三角色权限隔离/超管保护/菜单可见性），修复 watermark 死引用注释；P2 登录审计拆出 core/audit.py（信号与解析分离），一次性脚本归档 scripts/archive/ |
| **V0.5.1** | 登录记录时间显示修复：DB 按 UTC 存储（USE_TZ=True），列表页时间列与模型 __str__ 未转时区导致少 8 小时，统一 timezone.localtime 转北京时间（Asia/Shanghai）；历史记录自动显示正确，CSV 导出/编辑页原本已正确 |

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

冒烟测试（前台 5 页双语 / 询价蜜罐限流 / 后台权限隔离 / 超管保护，共 14 项）：
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
| 3 | `python manage.py import_pdf` | 从 `素材/产品目录.pdf` 提取 183 张产品图 |
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

登录 `/admin`（超管 glowisd），侧边栏三组菜单：

| 菜单 | 可做什么 |
|------|----------|
| 产品管理 → 产品 | 增删改查；品名(中/英)、P/N 件号、SKU、品牌、重量、质保、描述、图片、所属分类、**首页推荐**（列表页勾选）；列表有图片缩略图 |
| 产品管理 → 产品分类 | 产品线增删改 + 排序 |
| 产品管理 → 首页轮播 | 轮播图上传/排序/启用（含缩略图） |
| 客户消息 → 询价留言 | 查看/标记已读 |
| 管理员中心 → 管理员列表 | 新增/编辑管理员；角色彩色标签；状态；上次登录地区；**重置密码** action；编辑页内嵌最近 10 次登录记录 |
| 管理员中心 → 登录记录 | 4 统计卡片（今日/活跃/失败/异常）；成功✅失败❌+失败原因；**异常登录黄色高亮**；CSV 导出（无 IP） |

**首页推荐**：产品列表勾选「首页推荐」→ 首页 Featured 区块自动展示（最多 8 个）。

---

## 十一、中英双语机制

- 语言判断：Cookie `lang`（用户手动切换）优先，其次浏览器 `Accept-Language`
- 模板写法：`{% if lang == 'en' %}English{% else %}中文{% endif %}`
- 产品名/分类名按当前语言自动取 `part_name_en` / `name_en`
- 英文版全站零中文硬编码（仅语言切换器「中 | EN」）

---

## 十二、安全特性

- 询价表单：蜜罐字段（`website`）+ 会话限流（5 分钟 3 次）
- 生产：`DEBUG=False`、`SECRET_KEY` 环境变量（服务器 .env）、nginx 反代（`$http_host` 保留端口防 CSRF）
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
2. 更新本 README（版本历史/特性）
3. 更新看板「版本迭代流程图」mermaid
4. 部署腾讯云 + 微信简报（hermes）

---

*最后更新：V0.5.1（2026-09-01）*
