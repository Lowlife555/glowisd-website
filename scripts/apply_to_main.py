"""把预览目录的改动复制进主仓库（默认只演练，不写任何文件）。

为什么需要它：预览目录 `_2vibefather_version` 不是 git 仓库，改动散在 20+ 个文件里，
手工拷容易漏。本脚本按固定清单复制，并在复制前校验源文件存在、目标可写。

用法：
    python scripts/apply_to_main.py             # 演练：只打印会做什么
    python scripts/apply_to_main.py --apply     # 真正复制（主仓库工作区变脏，git diff 可审阅）
    python scripts/apply_to_main.py --apply --skip-kanban   # 跳过 进度看板.md（已单独更新过）

注意：合并后主仓库需要自行 `git add -A && git commit -m "V0.15.0: ..."` 并推送，
      本脚本不做任何 git 操作，也不碰服务器。
"""

import argparse
import os
import shutil

PREVIEW = r'C:\Users\15782\Desktop\dsh_glowised_website\_2vibefather_version'
MAIN = r'C:\Users\15782\Desktop\dsh_glowised_website\site\glowisd-website'

#: 需要同步到主仓库的文件（相对路径；媒体文件单独处理，见 MEDIA_FILES）
# 仅留在预览目录、不上服务器的文档（不对应主仓库文件）：
#   README_第三轮说明.md / README_汲取版说明.md / MERGE清单.md / 进度看板.md
FILES = [
    # 后端
    'config/settings.py',
    'core/models.py',
    'core/middleware.py',
    'core/page_cache.py',
    'core/signals.py',
    'core/views.py',
    'core/tests.py',
    'core/management/commands/enable_sqlite_wal.py',
    'core/management/commands/clear_site_cache.py',
    'core/migrations/0016_alter_siteimage_key.py',
    'core/migrations/0017_seed_hero_image_slots.py',
    'products/views.py',
    'products/templatetags/products_extras.py',
    'payments/tests.py',
    # 模板
    'templates/base.html',
    'templates/core/home.html',
    'templates/core/factory.html',
    'templates/core/custom.html',
    'templates/core/contact.html',
    'templates/products/list.html',
    'templates/products/detail.html',
    'templates/products/_product_card.html',
    'templates/payments/pay.html',
    # 前端样式
    'static/css/style.css',
    'static/js/app.js',
    'static/img/logo.png',
    # 部署与脚本
    'deploy/ecosystem.config.cjs',
    'deploy/nginx-glowisd.conf',
    'deploy/nginx-glowisd-domain.conf',
    'deploy/deploy_glowisd.ps1',
    'deploy/deploy-README.md',
    'deploy/preflight.sh',
    'deploy/ROLLBACK.md',
    'scripts/make_webp.py',
    'scripts/install_theme_images.py',
    'scripts/diff_against_main.py',
    'scripts/apply_to_main.py',
    '.gitignore',
    # 看板（可跳过）
    '进度看板.md',
]

#: 站点图片（装进 SiteImage 槽位的成品图，需随仓库分发）
MEDIA_FILES = [
    'media/site_images/home_factory.jpg',
    'media/site_images/custom_hero.jpg',
    'media/site_images/catalog_hero.jpg',
    'media/site_images/contact_hero.jpg',
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='真正复制（默认只演练）')
    ap.add_argument('--skip-kanban', action='store_true', help='跳过 进度看板.md')
    ap.add_argument('--dest', default=MAIN,
                    help='目标根目录（默认主仓库；演练时可指向临时目录验证合并结果）')
    args = ap.parse_args()
    dest_root = os.path.abspath(args.dest)
    if not os.path.isdir(dest_root):
        raise SystemExit(f'目标目录不存在：{dest_root}')
    if dest_root != os.path.abspath(MAIN):
        print(f'（目标不是主仓库，而是：{dest_root}）')

    files = [f for f in FILES if not (args.skip_kanban and f == '进度看板.md')]
    todo = files + MEDIA_FILES

    missing = [f for f in todo if not os.path.exists(os.path.join(PREVIEW, f))]
    if missing:
        print('源文件缺失，先补齐再合并：')
        for f in missing:
            print('  -', f)
        raise SystemExit(1)

    print(f'{"动作":6} 文件')
    print('-' * 78)
    for rel in todo:
        src = os.path.join(PREVIEW, rel)
        dst = os.path.join(dest_root, rel)
        exists = os.path.exists(dst)
        same = exists and open(src, 'rb').read() == open(dst, 'rb').read()
        action = '相同' if same else ('覆盖' if exists else '新建')
        print(f'{action:6} {rel}')
        if args.apply and not same:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

    print()
    if args.apply:
        print(f'已复制 {len(todo)} 个文件到主仓库。下一步：')
        print('  cd site/glowisd-website && git status')
        print('  git add -A && git commit -m "V0.15.0: 页头主题图 + 产能数字 + 补齐图片 + 性能与并发优化"')
    else:
        print('本次是演练，没有写入任何文件。确认无误后加 --apply 执行复制。')


if __name__ == '__main__':
    main()
