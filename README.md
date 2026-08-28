# Glowisd 官网（V0.1.1）

摊铺机传感器、线缆及配件制造商官网。中英双语多页面网站。

## 技术栈
- 后端：Django 6.1 + django-simpleui（中文后台）
- 前端：Vue 3（全局构建：语言切换 / 移动导航 / 询价表单）
- 数据库：SQLite
- 风格：高端轻奢工业风，严格无动画

## 快速开始
```bash
pip install django django-simpleui pillow
python manage.py migrate
python manage.py seed_data      # 初始化 9 分类 + 10 示例产品
python manage.py import_pdf     # 导入产品目录 PDF 的 150 张产品照片
python manage.py runserver
```

## 页面
| 路由 | 页面 |
|------|------|
| / | 首页 |
| /products/ | 产品中心（分类筛选 + 搜索 + 详情） |
| /factory/ | 工厂 |
| /custom/ | 定制 |
| /contact/ | 联系（询价表单） |

## 后台
- 地址：/admin/（simpleui 中文界面）
- 超级管理员：lowlife

## 版本
V0.1.1（技术栈：Next.js → Django + Vue）
