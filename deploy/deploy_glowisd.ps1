# =============================================================
# Glowisd 官网部署脚本 — 本地开发机执行
# 每次开发完成(commit+push 之后)运行: powershell -File deploy/deploy_glowisd.ps1
# 目标: 腾讯云轻量应用服务器 43.135.22.140 (Ubuntu 24.04, root)
# 部署目录: /var/www/glowisd (git clone https://github.com/Lowlife555/glowisd-website.git)
# 进程: gunicorn (pm2 管理, 127.0.0.1:8000) + nginx (0.0.0.0:8080 与 443)
# 首次初始化见 deploy-README.md（clone/venv/nginx/pm2 配置只需一次）
# =============================================================
$ErrorActionPreference = "Stop"

$SERVER = "root@43.135.22.140"
$DEPLOY_DIR = "/var/www/glowisd"
$LOCAL_BRANCH = (git branch --show-current)

Write-Host "=== [1/9] 本地 git push ($LOCAL_BRANCH) ===" -ForegroundColor Cyan
$dirty = git status --porcelain
if ($dirty) {
    git add -A
    git commit -m "chore: deploy checkpoint"
}
git push origin $LOCAL_BRANCH
if ($LASTEXITCODE -ne 0) { throw "git push failed" }

Write-Host "=== [2/9] 服务器 git pull ===" -ForegroundColor Cyan
ssh -o ConnectTimeout=10 $SERVER "cd $DEPLOY_DIR && git pull --ff-only origin $LOCAL_BRANCH"
if ($LASTEXITCODE -ne 0) { throw "服务器 git pull failed" }

Write-Host "=== [3/9] 服务器依赖安装 (apt: python3-venv/pip → venv → pip install) ===" -ForegroundColor Cyan
# 首次会自动补装系统包 python3-venv / python3-pip（幂等，已装则跳过）
ssh $SERVER "python3 -c 'import venv, ensurepip' 2>/dev/null || apt-get install -y -q python3-venv python3-pip"
if ($LASTEXITCODE -ne 0) { throw "apt 安装 python3-venv/pip failed" }
ssh $SERVER "cd $DEPLOY_DIR && ([ -d venv ] || python3 -m venv venv) && venv/bin/pip install -q --upgrade pip && set -o pipefail && venv/bin/pip install -q -r requirements.txt 2>&1 | tail -3"
if ($LASTEXITCODE -ne 0) { throw "python 依赖安装 failed" }

Write-Host "=== [4/9] 备份数据库与当前 commit（迁移前保险） ===" -ForegroundColor Cyan
# 迁移失败/数据异常时的唯一退路：库文件 + 当前 HEAD 都留一份。
# 回滚步骤见 deploy/ROLLBACK.md；备份只保留最近 10 份，避免占满磁盘。
ssh $SERVER "cd $DEPLOY_DIR && mkdir -p backups && STAMP=`$(date +%Y%m%d-%H%M%S) && cp -a db.sqlite3 backups/db-`$STAMP.sqlite3 && git rev-parse --short HEAD > backups/prev-commit.txt && ls -1t backups/db-*.sqlite3 | tail -n +11 | xargs -r rm -f && ls -lh backups/db-`$STAMP.sqlite3 | awk '{print `$5, `$9}'"
if ($LASTEXITCODE -ne 0) { throw "数据库备份 failed（不继续迁移）" }

Write-Host "=== [5/9] 数据库迁移 (migrate) ===" -ForegroundColor Cyan
ssh $SERVER "cd $DEPLOY_DIR && set -o pipefail && venv/bin/python manage.py migrate 2>&1 | tail -8"
if ($LASTEXITCODE -ne 0) { throw "migrate failed" }

Write-Host "=== [6/9] SQLite 切 WAL（幂等，已是 WAL 则跳过） ===" -ForegroundColor Cyan
# WAL：读不被写阻塞。一次性设置，持久生效；重复跑无副作用。
ssh $SERVER "cd $DEPLOY_DIR && venv/bin/python manage.py enable_sqlite_wal 2>&1 | tail -3"
if ($LASTEXITCODE -ne 0) { Write-Host "WAL 切换失败（不致命，继续部署）" -ForegroundColor Yellow }

Write-Host "=== [7/9] 生成 WebP 图片变体（跳过已存在的，首次约 1-3 分钟） ===" -ForegroundColor Cyan
# 变体不入库（.gitignore 忽略 media/opt/），必须在服务器上生成；
# 缺失时前台自动回退原图（能跑，只是慢很多），所以这步失败不阻断部署。
# 注意：必须**不带 --stats**（--stats 只统计不生成）；生成完再统计一次看体积对比。
ssh $SERVER "cd $DEPLOY_DIR && venv/bin/python scripts/make_webp.py 2>&1 | tail -3"
if ($LASTEXITCODE -ne 0) { Write-Host "WebP 变体生成失败（不致命：前台会回退原图）" -ForegroundColor Yellow }
ssh $SERVER "cd $DEPLOY_DIR && venv/bin/python scripts/make_webp.py --stats 2>&1 | tail -2"

Write-Host "=== [8/9] 收集静态资源 (collectstatic) ===" -ForegroundColor Cyan
ssh $SERVER "cd $DEPLOY_DIR && set -o pipefail && venv/bin/python manage.py collectstatic --noinput 2>&1 | tail -3"
if ($LASTEXITCODE -ne 0) { throw "collectstatic failed" }

Write-Host "=== [9/9] 清缓存 + 重启 pm2 + 健康检查 ===" -ForegroundColor Cyan
# 清整页缓存：文件缓存重启后仍然存在，不清的话访客最多会看到 2 分钟前渲染的旧页面。
ssh $SERVER "cd $DEPLOY_DIR && venv/bin/python manage.py clear_site_cache 2>&1 | tail -2"
if ($LASTEXITCODE -ne 0) { Write-Host "清缓存失败（不致命，最多 2 分钟后自然过期）" -ForegroundColor Yellow }
# 首次: pm2 start deploy/ecosystem.config.cjs；之后: pm2 restart glowisd
# --update-env：让 gunicorn 的 worker 数等参数改动生效
ssh $SERVER "cd $DEPLOY_DIR && (pm2 describe glowisd >/dev/null 2>&1 && pm2 restart glowisd --update-env || pm2 start deploy/ecosystem.config.cjs)"
if ($LASTEXITCODE -ne 0) { throw "pm2 启动/重启 failed" }
Start-Sleep -Seconds 3
$code = ssh $SERVER "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/"
Write-Host "Glowisd HTTP 状态: $code" -ForegroundColor Green
if ($code -ne "200") { throw "Glowisd 未就绪 (HTTP $code)" }

Write-Host "=== 部署完成 ===" -ForegroundColor Green
Write-Host "提醒：nginx 配置（缓存/gzip/HTTP2）是系统级文件，需手动一次性替换：" -ForegroundColor Yellow
Write-Host "  scp deploy/nginx-glowisd.conf ${SERVER}:/etc/nginx/sites-available/glowisd" -ForegroundColor Gray
Write-Host "  scp deploy/nginx-glowisd-domain.conf ${SERVER}:/etc/nginx/sites-available/glowisd-domain" -ForegroundColor Gray
Write-Host "  ssh $SERVER 'nginx -t && systemctl reload nginx'" -ForegroundColor Gray
