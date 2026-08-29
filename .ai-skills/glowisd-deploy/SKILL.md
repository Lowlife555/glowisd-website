---
name: glowisd-deploy
description: "Glowisd 腾讯云部署经验与踩坑记录。Use when deploying the Django site to Tencent Cloud Lighthouse, writing deploy scripts, troubleshooting nginx/pm2/gunicorn, or opening firewall ports. 部署:安全组放行/nginx/pm2/ssh deploy key/私有仓库 clone。"
---

# Glowisd 腾讯云部署指南(踩坑沉淀)

> 适用:Claude Code / dsh 执行部署任务时。基于 2026-08-28/29 实际部署验证。

## 部署拓扑(已验证)

```
腾讯云轻量服务器 43.135.22.140
├── nginx :8080 → gunicorn (Django 6.1)
├── pm2: glowisd (gunicorn) + ielts-server 共存
├── 代码: /root/glowisd-website (git clone, ssh 免密)
└── 数据库: SQLite 单文件 db.sqlite3
```

## 关键步骤与踩坑

### 1. 私有仓库部署(必踩坑)
- GitHub 私有仓库 **不能 https clone**(要密码),必须 ssh
- 服务器生成 ssh key → 加入 GitHub 的 Deploy Keys → `git clone git@github.com:Lowlife555/glowisd-website.git`
- **ssh 首次连接要接受 host key**:先 `ssh-keyscan github.com >> ~/.ssh/known_hosts`,否则 clone 卡死
- 部署脚本顺序(已验证):clone → venv → pip install → migrate → seed → gunicorn/pm2 → nginx

### 2. 外网不通 = 腾讯云安全组(最常踩)
- 服务器内部 `curl localhost:8080` 200,但外网不通 → **不是服务器问题,是腾讯云控制台安全组未放行**
- 必须在腾讯云控制台手动操作:防火墙/安全组 → 添加规则 → TCP 8080 → 来源 0.0.0.0/0
- **AI 无法代替用户在控制台操作** → 立即停下来,通过微信简报让用户操作,不要反复排查服务器
- 诊断命令:本地 `curl localhost:8080` + 外网 `curl 公网IP:8080` 对比,一分钟定位

### 3. 生产安全(部署前必改)
- `DEBUG=False`、`SECRET_KEY` 用环境变量、`ALLOWED_HOSTS` 收窄
- nginx 只监听需要的端口;不需要的端口别开

### 4. 与旧服务共存
- 服务器上已有 ielts-training 服务(8080 已被规划或共用),pm2 可多进程共存,互不影响
- 部署前先 `pm2 ls` 看现有服务,别盲目 kill

### 5. 上线验证清单
- [ ] 服务器本地 health 200
- [ ] 外网 `http://IP:PORT/` 200
- [ ] 后台 `/admin` 302 跳登录
- [ ] 手机流量(非本 WiFi)可访问
- [ ] 版本号按 glowisd-versioning 规则打 tag
