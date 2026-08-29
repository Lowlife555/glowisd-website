# =============================================================
# Glowisd 官网部署脚本 — 本地开发机执行
# 每次开发完成(commit+push 之后)运行: powershell -File deploy/deploy_glowisd.ps1
# 目标: 腾讯云轻量应用服务器 43.135.22.140 (Ubuntu 24.04, root)
# 部署目录: /var/www/glowisd (git clone https://github.com/Lowlife555/glowisd-website.git)
# 进程: gunicorn (pm2 管理, 127.0.0.1:8000) + nginx (0.0.0.0:8080)
# 首次初始化见 deploy-README.md（clone/venv/nginx/pm2 配置只需一次）
# =============================================================
$ErrorActionPreference = "Stop"

$SERVER = "root@43.135.22.140"
$DEPLOY_DIR = "/var/www/glowisd"
$LOCAL_BRANCH = (git branch --show-current)

Write-Host "=== [1/6] 本地 git push ($LOCAL_BRANCH) ===" -ForegroundColor Cyan
git add -A
git commit -m "chore: deploy checkpoint" --allow-empty | Out-Null
git push origin $LOCAL_BRANCH
if ($LASTEXITCODE -ne 0) { throw "git push failed" }

Write-Host "=== [2/6] 服务器 git pull ===" -ForegroundColor Cyan
ssh -o ConnectTimeout=10 $SERVER "cd $DEPLOY_DIR && git pull --ff-only origin $LOCAL_BRANCH"
if ($LASTEXITCODE -ne 0) { throw "服务器 git pull failed" }

Write-Host "=== [3/6] 服务器依赖安装 (apt: python3-venv/pip → venv → pip install) ===" -ForegroundColor Cyan
# 首次会自动补装系统包 python3-venv / python3-pip（幂等，已装则跳过）
ssh $SERVER "python3 -c 'import venv, ensurepip' 2>/dev/null || apt-get install -y -q python3-venv python3-pip"
if ($LASTEXITCODE -ne 0) { throw "apt 安装 python3-venv/pip failed" }
ssh $SERVER "cd $DEPLOY_DIR && ([ -d venv ] || python3 -m venv venv) && venv/bin/pip install -q --upgrade pip && set -o pipefail && venv/bin/pip install -q -r requirements.txt gunicorn 2>&1 | tail -3"
if ($LASTEXITCODE -ne 0) { throw "python 依赖安装 failed" }

Write-Host "=== [4/6] 数据库迁移 (migrate) ===" -ForegroundColor Cyan
ssh $SERVER "cd $DEPLOY_DIR && set -o pipefail && venv/bin/python manage.py migrate 2>&1 | tail -8"
if ($LASTEXITCODE -ne 0) { throw "migrate failed" }

Write-Host "=== [5/6] 收集静态资源 (collectstatic) ===" -ForegroundColor Cyan
ssh $SERVER "cd $DEPLOY_DIR && set -o pipefail && venv/bin/python manage.py collectstatic --noinput 2>&1 | tail -3"
if ($LASTEXITCODE -ne 0) { throw "collectstatic failed" }

Write-Host "=== [6/6] 重启 pm2 + 健康检查 ===" -ForegroundColor Cyan
# 首次: pm2 start deploy/ecosystem.config.cjs；之后: pm2 restart glowisd
ssh $SERVER "cd $DEPLOY_DIR && (pm2 describe glowisd >/dev/null 2>&1 && pm2 restart glowisd --update-env || pm2 start deploy/ecosystem.config.cjs)"
if ($LASTEXITCODE -ne 0) { throw "pm2 启动/重启 failed" }
Start-Sleep -Seconds 3
$code = ssh $SERVER "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/"
Write-Host "Glowisd HTTP 状态: $code" -ForegroundColor Green
if ($code -ne "200") { throw "Glowisd 未就绪 (HTTP $code)" }

Write-Host "=== 部署完成 ===" -ForegroundColor Green
