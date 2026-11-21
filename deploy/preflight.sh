#!/usr/bin/env bash
# Glowisd 部署预检（只读，不改动任何文件与进程）
# 用法：ssh root@43.135.22.140 'bash -s' < deploy/preflight.sh
#       或放到服务器上：bash deploy/preflight.sh
#
# 检查：运行时版本 / Pillow WebP 支持 / 待执行迁移 / 磁盘与内存 / 目录可写性 /
#       SQLite 日志模式 / 当前 gunicorn 参数 / git 工作区是否干净
# 任何一项 FAIL 都会在末尾汇总；WARN 不阻断部署但需要知道。

set -u
DIR=/var/www/glowisd
PY="$DIR/venv/bin/python"
FAIL=0
WARN=0

ok()   { printf '  \033[32m OK \033[0m %s\n' "$1"; }
warn() { printf '  \033[33mWARN\033[0m %s\n' "$1"; WARN=$((WARN+1)); }
bad()  { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAIL=$((FAIL+1)); }

echo "== 1. 运行时 =="
[ -d "$DIR" ] && ok "部署目录存在 $DIR" || bad "部署目录不存在"
[ -x "$PY" ] && ok "$("$PY" -V 2>&1)" || { bad "venv python 不可用"; exit 1; }
NGX=$(nginx -v 2>&1 | sed 's#.*/##')
ok "nginx $NGX"
command -v pm2 >/dev/null && ok "pm2 $(pm2 -v 2>/dev/null | tail -1)" || bad "pm2 未安装"

echo "== 2. Pillow WebP 支持（图片变体依赖） =="
WEBP=$("$PY" -c "from PIL import features; print(features.check('webp'))" 2>/dev/null)
[ "$WEBP" = "True" ] && ok "Pillow webp = True" || bad "Pillow 不支持 WebP，make_webp.py 会失败"

echo "== 3. 待执行迁移 =="
UN=$(cd "$DIR" && "$PY" manage.py showmigrations 2>/dev/null | grep -c '\[ \]')
[ "$UN" = "0" ] && ok "没有待执行迁移" || warn "有 $UN 个未执行迁移（部署时会 migrate）"

echo "== 4. 磁盘与内存 =="
DF=$(df -P "$DIR" | awk 'NR==2 {print $4/1024/1024}')
awk -v g="$DF" 'BEGIN { if (g > 1) exit 0; else exit 1 }' && ok "可用磁盘 ${DF} GB (需>1GB：图片变体约 9MB)" || bad "磁盘不足：${DF} GB"
MEMF=$(free -m | awk 'NR==2 {print $7}')
[ "$MEMF" -gt 400 ] && ok "可用内存 ${MEMF} MB" || warn "可用内存仅 ${MEMF} MB（3 worker 需 ~350MB）"

echo "== 5. 目录与权限 =="
for d in "$DIR/media" "$DIR/staticfiles" "$DIR/media/opt"; do
  if [ -d "$d" ]; then
    [ -w "$d" ] && ok "可写 $d" || bad "不可写 $d"
  else
    [ "$d" = "$DIR/media/opt" ] && warn "$d 不存在（部署脚本会创建）" || bad "$d 不存在"
  fi
done
"$PY" -c "import os,sys; sys.exit(0 if os.access('$DIR', os.W_OK) else 1)" && ok "部署目录可写（.django-cache 会建在这里）" || bad "部署目录不可写"

echo "== 6. SQLite =="
JM=$("$PY" - <<'PYEOF'
import os, sqlite3
p = '/var/www/glowisd/db.sqlite3'
print('missing' if not os.path.exists(p) else sqlite3.connect(p).execute('PRAGMA journal_mode').fetchone()[0])
PYEOF
)
case "$JM" in
  wal) ok "journal_mode = wal" ;;
  missing) bad "db.sqlite3 不存在" ;;
  *) warn "journal_mode = $JM（部署脚本会切到 wal）" ;;
esac
SZ=$(du -m "$DIR/db.sqlite3" 2>/dev/null | awk '{print $1}')
ok "数据库 ${SZ:-?} MB"

echo "== 6b. 生效的 Django 设置 =="
CFG=$("$PY" - <<'PYEOF'
import os, sys
sys.path.insert(0, '/var/www/glowisd'); os.chdir('/var/www/glowisd')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django; django.setup()
from django.conf import settings
print(settings.DEBUG)
print(len(settings.SECRET_KEY))
print(getattr(settings, 'SESSION_COOKIE_SECURE', False))
print(getattr(settings, 'SECURE_HSTS_SECONDS', 0))
print(getattr(settings, 'PAGE_CACHE_SECONDS', 'unset'))
print(settings.CACHES['default']['BACKEND'].rsplit('.', 1)[-1])
PYEOF
)
DBG=$(echo "$CFG" | sed -n 1p); KEYLEN=$(echo "$CFG" | sed -n 2p); SC=$(echo "$CFG" | sed -n 3p)
HSTS=$(echo "$CFG" | sed -n 4p); PCS=$(echo "$CFG" | sed -n 5p); CB=$(echo "$CFG" | sed -n 6p)
[ "$DBG" = "False" ] && ok "DEBUG = False" || bad "DEBUG = True，生产环境必须关掉"
[ "$KEYLEN" -ge 50 ] && ok "SECRET_KEY 长度 $KEYLEN" || warn "SECRET_KEY 只有 $KEYLEN 位，建议换成长随机值"
[ "$SC" = "True" ] && ok "SESSION_COOKIE_SECURE = True" || warn "SESSION_COOKIE_SECURE = False（HTTPS 已启用，但如有 http://IP:8080 的旧入口先别开，否则后台登录会掉线）"
[ "$HSTS" != "0" ] && ok "HSTS = $HSTS 秒" || warn "未启用 HSTS（SECURE_HSTS_SECONDS=0）"
echo "     整页缓存：PAGE_CACHE_SECONDS=$PCS，后端=$CB"
[ "$CB" = "FileBasedCache" ] && ok "缓存后端为文件缓存（多 worker 共享）" || warn "缓存后端是 $CB —— 多 worker 下整页缓存命中率会大幅下降"
echo "== 6c. 迁移前备份 =="
BK=$(ssh_dummy=1; cd_ok=1; ls -1t "$DIR"/backups/db-*.sqlite3 2>/dev/null | head -1)
if [ -n "$BK" ]; then
  AGE=$(( ( $(date +%s) - $(stat -c %Y "$BK") ) / 86400 ))
  ok "最近备份 $(basename "$BK")（${AGE} 天前），共 $(ls -1 "$DIR"/backups/db-*.sqlite3 2>/dev/null | wc -l) 份"
  [ "$AGE" -gt 7 ] && warn "备份已 ${AGE} 天，部署第 4 步会自动再备份一份"
else
  warn "还没有任何数据库备份 —— 部署脚本第 4 步会先备份再迁移（首次部署属正常）"
fi
echo "== 7. 当前进程参数 =="
ARGS=$(pm2 describe glowisd 2>/dev/null | grep -m1 'script args' | sed 's/^[^│]*│[^│]*│//; s/│$//')
if [ -n "$ARGS" ]; then
  echo "     $ARGS"
  echo "$ARGS" | grep -q -- '--workers 3' && ok "已是 3 worker" || warn "当前不是 3 worker（部署后会生效）"
  echo "$ARGS" | grep -q -- '--threads' && ok "已启用线程" || warn "当前没有 --threads（gthread 并发不足）"
else
  warn "读不到 pm2 进程参数"
fi

echo "== 8. git 工作区 =="
# 只有「已跟踪文件被改」才会和 git pull 冲突；后台传的图片、venv 等都是未跟踪文件，不影响
TRACKED_DIRTY=$(cd "$DIR" && git status --porcelain 2>/dev/null | grep -vc '^??')
UNTRACKED=$(cd "$DIR" && git status --porcelain 2>/dev/null | grep -c '^??')
if [ "$TRACKED_DIRTY" = "0" ]; then
  ok "没有已跟踪文件被改动，git pull 安全（未跟踪文件 $UNTRACKED 个：后台图片/venv 等）"
else
  warn "有 $TRACKED_DIRTY 个已跟踪文件被改动，git pull 可能冲突，先 git diff 看一眼"
  cd "$DIR" && git status --porcelain | grep -v '^??' | head -5
fi

echo
echo "================== 汇总 =================="
echo "FAIL: $FAIL   WARN: $WARN"
[ "$FAIL" = "0" ] && echo "预检通过，可以执行部署。" || echo "存在 FAIL 项，先修再部署。"
exit "$([ "$FAIL" = "0" ] && echo 0 || echo 1)"
