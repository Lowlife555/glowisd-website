"""比对「预览目录」与「主仓库」，输出真实改动文件清单（用于合并）。

只比对源码类文件（.py/.html/.css/.js/.md/.conf/.cjs/.txt/.ps1/.sh）；
media/、db.sqlite3、__pycache__、node_modules、docs/screenshots 不参与比对；
static/ 下的 .css/.js 必须参与（style.css、app.js 都是核心改动，之前误排除了）。

用法：
    python scripts/diff_against_main.py            # 打印清单
    python scripts/diff_against_main.py --write    # 同时写入 MERGE清单.md
"""

import argparse
import hashlib
import os

PREVIEW = r'C:\Users\15782\Desktop\dsh_glowised_website\_2vibefather_version'
MAIN = r'C:\Users\15782\Desktop\dsh_glowised_website\site\glowisd-website'

EXTS = {'.py', '.html', '.css', '.js', '.md', '.conf', '.cjs', '.txt', '.ps1', '.sh', '.gitignore'}
SKIP_DIRS = {'__pycache__', '.git', 'node_modules', 'venv', 'media', 'staticfiles', '.django-cache',
             'shots-vibefather', 'screenshots-v0.14.2'}


def walk(root):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            name = fn.lower()
            if ext not in EXTS and name != '.gitignore':
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace('\\', '/')
            with open(full, 'rb') as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    pv = walk(PREVIEW)
    mn = walk(MAIN)

    added = sorted(k for k in pv if k not in mn)
    removed = sorted(k for k in mn if k not in pv)
    changed = sorted(k for k in pv if k in mn and pv[k] != mn[k])

    lines = []
    lines.append(f'# 预览目录 → 主仓库 合并清单')
    lines.append('')
    lines.append(f'- 预览：`{PREVIEW}`')
    lines.append(f'- 主仓库：`{MAIN}`')
    lines.append(f'- 新增 {len(added)} 个 / 修改 {len(changed)} 个 / 主仓库独有（不处理）{len(removed)} 个')
    lines.append('')
    lines.append('## 新增文件（预览有、主仓库没有）')
    lines.append('')
    for k in added:
        lines.append(f'- `{k}`')
    lines.append('')
    lines.append('## 修改文件（两边都有，内容不同）')
    lines.append('')
    for k in changed:
        lines.append(f'- `{k}`')
    lines.append('')
    lines.append('## 主仓库独有（预览里没有，合并时不动）')
    lines.append('')
    for k in removed:
        lines.append(f'- `{k}`')

    text = '\n'.join(lines) + '\n'
    print(text)
    if args.write:
        out = os.path.join(PREVIEW, 'MERGE清单.md')
        with open(out, 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)
        print(f'\n已写入 {out}')


if __name__ == '__main__':
    main()
