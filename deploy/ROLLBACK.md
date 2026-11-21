# Glowisd 上线回滚手册

> 什么时候用：部署后站点 500 / 页面空白 / 数据不对 / 想退回上一个版本。
> 部署脚本第 4 步已经自动备份「数据库 + 上一个 commit」，这里就是怎么用那份备份。

## 0. 先判断坏在哪一层

```bash
ssh root@43.135.22.140
cd /var/www/glowisd

pm2 logs glowisd --lines 50 --nostream    # 有没有 traceback
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/   # 后端直连
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/   # 绕过 nginx
curl -sI https://glowisd.cn/ | head -3                            # 域名链路
```

| 现象 | 多半是 | 跳到 |
|---|---|---|
| 502 / 504 | gunicorn 没起来或超时 | §2、§3 |
| 500 + traceback | 代码/迁移问题 | §2、§3 |
| 200 但样式错乱、图片 404 | 静态资源 / WebP 变体没生成 | §5 |
| 200 但内容是旧的 | 整页缓存没清 | §5 |
| 页面挂到别的版本 | 拉到错的 commit | §2 |

## 1. 备份在哪

```
/var/www/glowisd/backups/
├── db-20261122-015443.sqlite3   # 每次部署第 4 步自动生成，只留最近 10 份
└── prev-commit.txt              # 部署前的 commit（回滚代码用）
```

查看：`ssh root@43.135.22.140 'cd /var/www/glowisd && ls -lht backups | head'`

## 2. 只回滚代码（数据没动过，最常用）

```bash
cd /var/www/glowisd
git log --oneline -3                       # 确认要退到哪个
PREV=$(cat backups/prev-commit.txt); echo "退回到 $PREV"
git reset --hard "$PREV"
python3 -m venv --help >/dev/null 2>&1 || true
venv/bin/pip install -q -r requirements.txt     # 依赖也退回去
venv/bin/python manage.py clear_site_cache      # 清整页缓存，否则还是旧页面
pm2 restart glowisd --update-env
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/
```

## 3. 连数据库一起回滚（迁移出问题 / 数据被改坏）

**顺序很重要**：必须先停进程再换库文件，否则 WAL 会覆盖回去。

```bash
cd /var/www/glowisd
pm2 stop glowisd

# 1) 先留存现场（万一还要救数据）
cp -a db.sqlite3 "db.broken-$(date +%Y%m%d-%H%M%S).sqlite3"

# 2) 恢复备份
BAK=$(ls -1t backups/db-*.sqlite3 | head -1); echo "恢复 $BAK"
cp -a "$BAK" db.sqlite3

# 3) 关键：删掉旧的 WAL/SHM，否则 sqlite 会用残留日志把库改回去
rm -f db.sqlite3-wal db.sqlite3-shm

# 4) 代码也退回到同一时刻
git reset --hard "$(cat backups/prev-commit.txt)"

# 5) 起服务 + 清缓存
venv/bin/python manage.py clear_site_cache
pm2 start glowisd 2>/dev/null || pm2 restart glowisd --update-env
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/
```

恢复后确认数据：`venv/bin/python manage.py shell -c "from products.models import Product; print(Product.objects.count())"`
（正常应为 159 个产品；预览库是它的副本）

## 4. 回滚 nginx 配置

nginx 配置是系统级文件，部署脚本不动它，只有你手动 `scp` 替换过才需要回滚。

```bash
ls -l /etc/nginx/sites-available/glowisd*
# 如果之前备份过：
# cp /etc/nginx/sites-available/glowisd.bak-<时间> /etc/nginx/sites-available/glowisd
nginx -t && systemctl reload nginx
```

> 注意：新版配置用了 `gzip`、`/media/opt/` 30 天缓存、`http2`。如果回滚到旧配置，
> 只是少这些优化，不会导致 500 —— **不需要为了回滚而回滚 nginx**。

## 5. 只修「静态资源 / 缓存」这类小问题（不用整体回滚）

```bash
cd /var/www/glowisd
venv/bin/python scripts/make_webp.py --stats      # 看变体数量（正常 ~584）
venv/bin/python scripts/make_webp.py              # 缺就补生成
venv/bin/python manage.py collectstatic --noinput
venv/bin/python manage.py clear_site_cache
pm2 restart glowisd --update-env
```

## 6. 最坏情况：代码库整个重来

```bash
cd /var/www
mv glowisd glowisd.broken-$(date +%Y%m%d%H%M%S)
git clone https://github.com/Lowlife555/glowisd-website.git glowisd
cd glowisd
python3 -m venv venv && venv/bin/pip install -q -r requirements.txt
# 恢复最近一份备份库（从旧目录里拿）
cp -a ../glowisd.broken-*/backups/db-*.sqlite3 ./db.sqlite3   # 选最新那份
rm -f db.sqlite3-wal db.sqlite3-shm
venv/bin/python manage.py migrate
venv/bin/python manage.py collectstatic --noinput
venv/bin/python scripts/make_webp.py
pm2 restart glowisd --update-env || pm2 start deploy/ecosystem.config.cjs
```

## 7. 回滚后必查的 5 项

```bash
curl -s -o /dev/null -w '后端 %{http_code}\n' http://127.0.0.1:8080/
curl -s https://glowisd.cn/ | grep -o 'V0\.[0-9]*\.[0-9]*' | head -1     # 页脚版本号要对
curl -sI https://glowisd.cn/static/css/style.css | grep -i cache-control  # 有 max-age 说明 nginx 缓存生效
ssh root@43.135.22.140 'pm2 list | grep glowisd'                          # 3 个 worker 都在
ssh root@43.135.22.140 'cd /var/www/glowisd && ls media/opt/products | wc -l'  # 约 584
```

五项都对 → 回滚完成。
