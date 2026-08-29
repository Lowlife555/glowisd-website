# Glowisd 官网（V0.2.0）

**常州 Glowisd 科技有限公司** 官方网站 —— 工程机械（摊铺机）传感器、线缆及配件制造商。

服务客户：中国大陆 + 中东 / 中亚 / 欧洲。中英双语、响应式（手机 / 平板 / 电脑均可访问）。

- 线上地址：http://43.135.22.140:8080
- 后台管理：http://43.135.22.140:8080/admin

---

## 一、当前版本 V0.2.0 特性

| 功能 | 说明 |
|------|------|
| 🏠 首页推荐产品 | 后台勾选「首页推荐」的产品，首页「Featured Products」区块优先罗列 |
| 📂 首页产品线陈列 | 首页「Shop by Product Line」按 9 大产品线分区陈列，每线前 4 款 + View all |
| 🖥 后台可视化增强 | 产品列表显示图片缩略图、分类列表显示产品数、推荐状态列表页直接勾选 |
| 🏷 产品品名补全 | 182 个产品全部有中英文品名（vision 识图生成） |
| 🌐 英文完整化 | 全站 5 页面英文版零中文残留（仅语言切换器「中 | EN」） |
| 🗂 产品线归类 | 7 大产品线已各归 2-3 个代表产品，其余待手动归类 |

---

## 二、版本历史

| 版本 | 日期 | 主要改动 |
|------|------|----------|
| V0.1.0 | 2026-08-28 | Next.js 官网雏形：中英双语 + 产品目录 + 询价表单 + 后台管理 |
| V0.1.1 | 2026-08-28 | 技术栈改 Django 6.1 + simpleui + Vue3；183 张产品照片导入 |
| V0.1.2 | 2026-08-28 | 腾讯云部署脚本 + 生产安全（gunicorn/nginx 8080，SECRET_KEY/DEBUG 环境变量） |
| V0.1.3 | 2026-08-28 | 同步公司信息（邮箱/电话/简介/工厂 1500㎡/起订量 10） |
| V0.1.4 | 2026-08-28 | 产品件号 R→GW 改写 + 18 个品名识别 |
| V0.1.5 | 2026-08-28 | 产品照片重裁（去右侧表格）+ logo 取色放大 |
| V0.1.6 | 2026-08-28 | SVG 图标 + 双语主副标题 + 深蓝金配色重构 |
| V0.1.7 | 2026-08-29 | 首页 Hero 6 图轮播（HeroSlide 模型 + 后台上传管理） |
| V0.1.8 | 2026-08-29 | 产品图最终重裁居中占 90% + footer 黑灰 + favicon 多尺寸 + nginx CSRF 修复 |
| **V0.2.0** | 2026-08-29 | 首页推荐 + 产品线陈列 + 后台增强 + 160 品名 OCR + 英文版去中文 |

---

## 三、技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端 | Django 6.1 | Python Web 框架 |
| 后台 | django-simpleui | 中文可视化后台管理 |
| 前端 | Vue 3（CDN 全局构建） | 语言切换 / 移动导航 / 询价表单 |
| 数据库 | SQLite | 单文件，无需独立数据库服务 |
| 图片 | Pillow | 产品图处理 |
| 部署 | gunicorn + nginx + pm2 | 腾讯云 8080 端口 |

---

## 四、项目结构

```
glowisd-website/
├── config/              # Django 配置（settings.py / urls.py / wsgi）
├── core/                # 首页/工厂/定制/联系视图 + HeroSlide 轮播模型
├── products/            # 产品/分类/询价模型 + 视图 + 管理命令
│   ├── models.py        #   Category(产品线) / Product(产品) / ContactMessage(询价)
│   ├── admin.py         #   后台注册（simpleui 可视化）
│   ├── management/      #   数据命令：seed_data / import_pdf / import_annotations
│   └── fixtures/        #   extracted_products.json / product_names_ocr.json
├── templates/           # HTML 模板
│   ├── base.html        #   全局布局（导航/页脚/语言切换/多尺寸 favicon）
│   ├── core/            #   home / factory / custom / contact
│   └── products/        #   list / detail
├── static/              # 静态资源
│   ├── css/style.css    #   全站样式（CSS 变量：深蓝 #162A87 + 金 #D2AE00）
│   ├── js/app.js        #   Vue3 语言切换 + 询价表单
│   ├── vendor/          #   vue.global.prod.js
│   └── img/             #   logo + 5 尺寸 favicon
├── media/               # 运行时上传
│   ├── products/        #   182 张产品图（600×430 白底居中）
│   └── hero/            #   首页轮播图
├── deploy/              # 部署脚本
│   ├── deploy_glowisd.ps1   # 本地一键部署（push→pull→migrate→collectstatic→重启）
│   ├── deploy_init.sh       # 服务器首次初始化（clone 私有仓库 + ssh）
│   ├── nginx-glowisd.conf   # nginx 8080 反代配置
│   └── ecosystem.config.cjs # pm2 进程配置
├── scripts/             # 数据提取/图片处理脚本（recrop_final.py 等）
└── manage.py            # Django 入口
```

---

## 五、快速开始（本地开发）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 初始化数据库（首次）
python manage.py migrate

# 3. 初始化数据（首次，见第六节）
python manage.py seed_data          # 9 产品线 + 示例产品
python manage.py import_pdf         # 从产品目录 PDF 导入 183 张产品照片
python manage.py import_annotations # 导入件号 GW + 品名

# 4. 启动开发服务器
python manage.py runserver
# 访问 http://localhost:8000
```

环境变量（可选，生产必须）：

```bash
DJANGO_SECRET_KEY=<随机密钥>
DJANGO_DEBUG=False
```

---

## 六、数据初始化（全新部署必读）

> 生产数据库 `db.sqlite3` 已被 `.gitignore` 排除，全新部署需按顺序重建数据：

| 步骤 | 命令 | 作用 |
|------|------|------|
| 1 | `python manage.py migrate` | 建表 |
| 2 | `python manage.py seed_data` | 建 9 个产品线 + 示例产品 |
| 3 | `python manage.py import_pdf` | 从 `素材/产品目录.pdf` 提取 183 张产品图 |
| 4 | `python manage.py import_annotations` | 导入件号（R→GW 改写）+ 品名 |
| 5 | 品名 OCR 导入 | 见下方命令，导入 160 个中英文品名 |

品名 OCR 导入（一次性）：

```python
python manage.py shell -c "
import json
from products.models import Product
d = json.load(open('products/fixtures/product_names_ocr.json', encoding='utf-8'))
for x in d:
    Product.objects.filter(image=x['image']).update(
        part_name=x['part_name'], part_name_en=x['part_name_en'])
"
```

---

## 七、部署（腾讯云）

- 服务器：43.135.22.140（Ubuntu，代码在 `/var/www/glowisd`）
- 进程：gunicorn（pm2 管理）+ nginx（8080 端口）
- 首次部署：`deploy/deploy_init.sh`（服务器上执行，clone 私有仓库 + ssh key）
- 日常更新：本地 `deploy/deploy_glowisd.ps1`（自动 push→pull→migrate→collectstatic→重启）

---

## 八、后台使用（管理员操作指南）

登录 `/admin`（账号 lowlife），simpleui 中文界面：

| 菜单 | 可做什么 |
|------|----------|
| **产品** | 增删改查；编辑品名(中/英)、P/N 件号、SKU、品牌、重量、质保、描述、图片、所属分类、**首页推荐**（列表页直接勾选） |
| **产品分类** | 产品线的增/删/改/排序（`排序` 数字越小越靠前）；列表显示各线产品数 |
| **首页轮播** | 首页 Hero 轮播图的上传/排序/启用停用 |
| **询价留言** | 查看/标记已读客户询价 |

**首页推荐操作**：产品列表页 → 勾选目标产品的「首页推荐」复选框 → 保存，首页即自动罗列（最多显示前 8 个）。

**产品线归类**：产品列表 → 点击产品 → 编辑「分类」下拉框 → 保存。

---

## 九、中英双语机制

- 语言判断：Cookie `lang`（用户手动切换）优先，其次浏览器 `Accept-Language`。
- 模板写法：`{% if lang == 'en' %}English{% else %}中文{% endif %}`。
- 产品名/分类名按当前语言自动取 `part_name_en` / `name_en`。
- 英文版已保证零中文硬编码（仅导航栏语言切换器「中 | EN」）。

---

## 十、页面路由

| 路由 | 页面 |
|------|------|
| `/` | 首页（Hero 轮播 + 分类 + 推荐产品 + 产品线陈列 + 优势 + 公司简介） |
| `/products/` | 产品中心（分类筛选 + SKU/P/N 搜索） |
| `/products/<id>/` | 产品详情（参数表 + 描述 + 相关产品 + 询价） |
| `/factory/` | 工厂 |
| `/custom/` | 定制 |
| `/contact/` | 联系（询价表单） |

---

## 十一、安全特性

- 询价表单：蜜罐字段（`website`）+ 会话限流（5 分钟 3 次）
- 生产：`DEBUG=False`、`SECRET_KEY` 环境变量、nginx 反代
- 后台：simpleui 登录鉴权；CSRF 修复（nginx `$http_host` 保留端口）

---

## 十二、维护说明

- 版本号规则：语义化 `Va.b.c` 十进制逐位递增（V0.1.9 → V0.2.0），每次大版本更新 README + 看板 mermaid 流程图。
- 多 agent 协作规范见 `进度看板.md`（工作区 docs，非本仓库）与 `.ai-skills/`。
- 每次版本更新需同步：README（本文档）、看板「六、版本迭代流程图」、git tag。
