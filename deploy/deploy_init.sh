#!/bin/bash
# Glowisd 官网 — 腾讯云服务器首次初始化脚本（root 执行一次）
# 用法: ssh root@43.135.22.140 "bash -s" < deploy/deploy_init.sh
set -e
echo "=== [1/8] clone 代码 ==="
cd /var/www
if [ -d glowisd/.git ]; then
  echo "glowisd 已 clone，跳过"
else
  rm -rf glowisd
  ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null || true
  git clone git@github.com:Lowlife555/glowisd-website.git glowisd
fi
cd glowisd

echo "=== [2/8] Python venv ==="
[ -d venv ] || python3 -m venv venv

echo "=== [3/8] 安装依赖（requirements.txt 含 gunicorn）==="
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt

echo "=== [4/8] 数据库迁移 ==="
venv/bin/python manage.py migrate

echo "=== [5/8] 初始化产品数据（9分类+10示例+183 PDF产品）==="
venv/bin/python manage.py seed_data
venv/bin/python manage.py import_pdf

echo "=== [6/8] 超级管理员（密码从环境变量读取，不入库）==="
if [ -z "$DJANGO_SUPERUSER_PASSWORD" ]; then
  echo "错误：请先设置环境变量 DJANGO_SUPERUSER_PASSWORD 再运行本脚本"
  echo "  示例：export DJANGO_SUPERUSER_PASSWORD='你的密码'"
  exit 1
fi
DJANGO_SUPERUSER_PASSWORD=$DJANGO_SUPERUSER_PASSWORD venv/bin/python manage.py createsuperuser --username lowlife --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}" --noinput 2>/dev/null || echo "lowlife 已存在，跳过"

echo "=== [7/8] 收集静态 + 启动 pm2 + nginx ==="
venv/bin/python manage.py collectstatic --noinput
pm2 describe glowisd >/dev/null 2>&1 && pm2 restart glowisd || pm2 start deploy/ecosystem.config.cjs
pm2 save >/dev/null 2>&1
cp deploy/nginx-glowisd.conf /etc/nginx/sites-available/glowisd
ln -sf /etc/nginx/sites-available/glowisd /etc/nginx/sites-enabled/glowisd
nginx -t
systemctl reload nginx

echo "=== [8/8] 健康检查 ==="
sleep 3
echo -n "Glowisd 8080 HTTP: "
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/
pm2 status | grep glowisd || true
