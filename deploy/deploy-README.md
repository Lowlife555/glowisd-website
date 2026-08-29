# Glowisd 官网 — 腾讯云部署说明

目标服务器：腾讯云轻量 **43.135.22.140**（Ubuntu 24.04，root，ssh 免密已配）。

## 部署架构

| 组件 | 说明 |
|------|------|
| 部署目录 | `/var/www/glowisd`（git clone `https://github.com/Lowlife555/glowisd-website.git`）|
| Python 环境 | `/var/www/glowisd/venv`，装 `requirements.txt` + `gunicorn` |
| 应用进程 | gunicorn 跑 `127.0.0.1:8000`，wsgi 入口 `config.wsgi:application`，由 **pm2** 管理（app 名 `glowisd`）|
| Web 入口 | nginx 监听 `0.0.0.0:8080`，反代 `127.0.0.1:8000`，并直接 serve `/static/` 和 `/media/` |
| 数据库 | SQLite `db.sqlite3`（已 gitignore，服务器首次 `migrate` 自动生成）|
| 静态文件 | `collectstatic` 输出到 `staticfiles/`（已 gitignore）；`media/` 产品照片已在 git 仓库 |

> 雅思站点占用 80 端口，Glowisd 用独立 **8080** 端口，两者互不影响。

---

## 一、部署前：生产 settings 要改哪些（改本地 `config/settings.py` 后 commit）

当前 `config/settings.py` 是开发配置，上线前必须改：

| 项 | 现状 | 生产值 |
|----|------|--------|
| `DEBUG` | `True` | **`False`**（关闭后媒体文件由 nginx 直接 serve，无需改 urls.py）|
| `SECRET_KEY` | 硬编码的 `django-insecure-...` | **换成随机新值** |
| `ALLOWED_HOSTS` | `['*']`（已满足）| 建议日后收紧为真实域名/IP |

生成新 SECRET_KEY：

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**推荐做法（生产更干净）**：改用环境变量，避免密钥进 git 仓库：

```python
import os
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-...dev...')
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'
```

然后在 `deploy/ecosystem.config.cjs` 的 `env` 里填 `DJANGO_SECRET_KEY` 和 `DJANGO_DEBUG: 'False'`（该文件模板里已预留注释位）。`STATIC_ROOT`、`MEDIA_ROOT`、`ALLOWED_HOSTS` 均已在 settings.py 配好，无需改动。

---

## 二、服务器首次初始化（只需一次）

```bash
# 1. clone 代码
mkdir -p /var/www && cd /var/www
git clone https://github.com/Lowlife555/glowisd-website.git glowisd
cd glowisd

# 2. 生产 settings：改 DEBUG=False + 换 SECRET_KEY（见上文，改完 commit + pull 到服务器）

# 3. 系统依赖 + venv + pip 包（nginx/pm2/node/python3 已装）
apt-get update
apt-get install -y python3-pip python3-venv
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt gunicorn

# 4. 首次建库 + 收集静态
venv/bin/python manage.py migrate
venv/bin/python manage.py collectstatic --noinput
venv/bin/python manage.py createsuperuser   # 可选：后台 /admin/ 账号

# 5. pm2 启动 gunicorn + 开机自启
pm2 start deploy/ecosystem.config.cjs
pm2 save
pm2 startup   # 按提示复制执行它输出的那行命令

# 6. nginx 站点配置
cp deploy/nginx-glowisd.conf /etc/nginx/sites-available/glowisd
ln -s /etc/nginx/sites-available/glowisd /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# 7. 验证
curl -I http://127.0.0.1:8080/        # 期望 200
pm2 status                            # glowisd 应为 online
```

---

## 三、日常部署（本地开发机执行，6 步）

```powershell
powershell -File deploy/deploy_glowisd.ps1
```

脚本 6 步（每步失败即 `throw` 中止）：

1. **本地 git push** —— `git add -A && commit --allow-empty && push origin <当前分支>`
2. **服务器 git pull** —— `cd /var/www/glowisd && git pull --ff-only`
3. **依赖安装** —— 缺则 apt 装 `python3-venv/python3-pip` → 建/复用 `venv` → `pip install -r requirements.txt gunicorn`
4. **数据库迁移** —— `venv/bin/python manage.py migrate`
5. **构建** —— `venv/bin/python manage.py collectstatic --noinput`（Django 的“构建”步骤）
6. **重启 + 健康检查** —— pm2 重启 `glowisd`（首次自动 `pm2 start`）→ `curl http://127.0.0.1:8080/` 期望 200

---

## 四、常见问题

- **`pm2 describe glowisd` 找不到**：首次未执行 `pm2 start deploy/ecosystem.config.cjs`，脚本第 6 步会自动补启。
- **8080 打不开**：先 `pm2 logs glowisd` 看 gunicorn 报错，再 `nginx -t` 检查配置。
- **后台样式丢了 / 产品图裂**：确认 `collectstatic` 已跑、nginx 的 `/static/`、`/media/` `alias` 路径指向 `/var/www/glowisd/staticfiles/`、`/var/www/glowisd/media/`。
- **改了 settings.py 没生效**：gunicorn 由 pm2 管理，部署脚本第 6 步已 `restart --update-env`，无需手动 reload。
