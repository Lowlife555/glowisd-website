"""后台操作日志的字段级明细（V0.14.0）。

目标：不只记录"改了哪个字段"，而是记录"旧值 → 新值"，让人一眼看懂这次操作到底改了什么；
明细太长时列表页截断，点进详情页看完整表格。

实现要点
--------
* 明细复用 ``LogEntry.change_message``（JSON，TextField 无长度限制），不建新表、不需要迁移。
* 与 Django 原生结构共存，``LogEntry.get_change_message()`` 仍然可用：

  - 修改：``[{"changed": {"fields": [...], "details": [...], "batch": "ab12cd34"}}]``
  - 新增：``[{"added": {"details": [...], "batch": "..."}}]``
  - 删除：``[{"deleted": {"snapshot": {...}, "batch": "..."}}]``（Django 删除日志原本 message 为空）

  旧日志只有 ``fields`` 没有 ``details``，照旧能读，详情页会标注「早于 V0.14.0，无旧值明细」。

* **保存永远不被日志拖垮**：所有明细构造都包在 try/except 里，失败静默降级。
* 敏感字段（密钥/密码/银行卡号/IBAN/SWIFT 等）一律显示「已修改（不显示内容）」，明文绝不落库。
"""
import json
import re

from django.contrib.admin.models import DELETION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db.models import Model
from django.utils.html import format_html
from django.utils.safestring import mark_safe

# ---------------------------------------------------------------------------
# 1. 敏感字段识别 + 值序列化
# ---------------------------------------------------------------------------

# 字段名命中这些片段即视为敏感：值不落库（存脱敏占位），详情页也不显示
SECRET_HINTS = (
    'password', 'passwd', 'secret', 'token', 'api_key', 'apikey', 'key',
    'account_number', 'iban', 'swift', 'bank_address', 'card', 'cvv', 'ssn',
    'credential', 'private',
)

SECRET_DISPLAY = '已修改（不显示内容）'

# 列表摘要的字符上限（超出截断为 …，悬停看全文）
SUMMARY_LIMIT = 60
# 旧值/新值各自的最大长度
VALUE_LIMIT = 60


def is_secret_field(name, label=''):
    haystack = f'{name or ""} {label or ""}'.lower()
    return any(hint in haystack for hint in SECRET_HINTS)


def _clip(text, limit=VALUE_LIMIT):
    text = '' if text is None else str(text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + '…'


def _display(value):
    """把任意字段值变成可显示的短字符串，返回 (text, kind)。"""
    from django.core.files.uploadedfile import UploadedFile
    from django.db.models.fields.files import FieldFile

    if value is None or value == '':
        return '', 'empty'
    # 布尔
    if isinstance(value, bool):
        return ('是' if value else '否'), 'bool'
    # 关系对象（必须在文件判断之前：Model 可能也有 .name 属性）
    if isinstance(value, Model):
        return _clip(str(value)), 'fk'
    # 图片/文件：FieldFile 或刚上传的 UploadedFile，只留文件名
    if isinstance(value, (FieldFile, UploadedFile)):
        name = getattr(value, 'name', '') or ''
        filename = name.rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
        kind = 'image' if re.search(r'\.(png|jpe?g|gif|webp|svg|bmp|avif)$', filename, re.I) else 'file'
        return filename, kind
    # 多对多 queryset / 列表
    if hasattr(value, '__iter__') and not isinstance(value, (str, bytes, dict)):
        try:
            names = [_clip(str(item), 30) for item in value]
            return '、'.join(names) if names else '', 'm2m'
        except TypeError:
            pass
    # 日期/时间/金额等直接 str
    text = _clip(value)
    kind = 'text'
    if re.match(r'^-?\d+(\.\d+)?$', text):
        kind = 'number'
    return text, kind


def _resolve_related(field, value):
    """外键 initial 是主键，转成 display 名称（失败则原样）。"""
    if not getattr(field, 'is_relation', False) or value in (None, ''):
        return value
    try:
        if isinstance(value, Model):
            return value
        return field.related_model._default_manager.filter(pk=value).first() or value
    except Exception:  # noqa: BLE001
        return value


def _field_for(model, name):
    try:
        return model._meta.get_field(name)
    except Exception:  # noqa: BLE001
        return None


def _collect_details(admin_obj, form, add=False):
    """从已校验表单里提炼字段级旧值→新值。任何异常都不影响保存。"""
    details = []
    model = admin_obj.model
    try:
        changed = list(form.changed_data)
    except Exception:  # noqa: BLE001
        return details
    if add:
        # 新增：只挑"有值的普通字段"，避免把二十几个空字段全塞进来
        try:
            names = [
                n for n in getattr(form, 'cleaned_data', {}) or {}
                if n not in ('password1', 'password2')
            ]
        except Exception:  # noqa: BLE001
            names = changed
        changed = names[:12]
    for name in changed:
        try:
            field = _field_for(model, name)
            form_field = (getattr(form, 'fields', {}) or {}).get(name)
            label = ''
            if form_field is not None:
                label = str(getattr(form_field, 'label', '') or name)
            elif field is not None:
                label = str(getattr(field, 'verbose_name', '') or name)
            label = label or name

            if is_secret_field(name, label):
                details.append({
                    'name': name, 'label': label, 'kind': 'secret',
                    'old': '' if add else SECRET_DISPLAY,
                    'new': SECRET_DISPLAY,
                })
                continue

            raw_old = None
            raw_new = None
            try:
                if not add and name in (getattr(form, 'initial', {}) or {}):
                    raw_old = form.initial.get(name)
                if name in (getattr(form, 'cleaned_data', {}) or {}):
                    raw_new = form.cleaned_data.get(name)
            except Exception:  # noqa: BLE001
                pass

            if field is not None and getattr(field, 'is_relation', False):
                raw_old = _resolve_related(field, raw_old)
                raw_new = _resolve_related(field, raw_new)

            # 新上传的文件：cleaned_data 里是 UploadedFile（名字还是原文件），
            # 保存后的真实文件名在实例上 —— 统一换成实例字段，缩略图才拼得对。
            from django.core.files.uploadedfile import UploadedFile

            if isinstance(raw_new, UploadedFile):
                instance_value = getattr(getattr(form, 'instance', None), name, None)
                if instance_value is not None:
                    raw_new = instance_value

            old_text, old_kind = _display(raw_old)
            new_text, new_kind = _display(raw_new)
            kind = new_kind if new_kind != 'empty' else old_kind
            if add:
                old_text = ''
            # 未变化的字段不必罗列（新增时除外）
            if not add and old_text == new_text:
                continue
            item = {
                'name': name, 'label': label, 'kind': kind,
                'old': old_text, 'new': new_text,
            }
            # 图片/文件额外记完整相对路径，详情页缩略图才拼得对
            if old_kind in ('image', 'file'):
                item['old_path'] = getattr(raw_old, 'name', '') or ''
            if new_kind in ('image', 'file'):
                item['new_path'] = getattr(raw_new, 'name', '') or ''
            details.append(item)
        except Exception:  # noqa: BLE001 —— 单个字段出错不影响其它字段
            continue
    return details


# ---------------------------------------------------------------------------
# 2. 删除快照
# ---------------------------------------------------------------------------

SNAPSHOT_HINTS = ('name', 'title', 'sku', 'part_name', 'price', 'code', 'slug', 'email', 'phone')


def _snapshot(obj):
    """删除前快照：名称/件号/价格等关键字段 + 图片文件名，最多 8 项。"""
    snap = {}
    try:
        fields = list(obj._meta.concrete_fields)
    except Exception:  # noqa: BLE001
        return snap
    priority, rest = [], []
    for field in fields:
        try:
            name = field.name
            if name in ('id', 'pk') or field.primary_key:
                continue
            if is_secret_field(name, str(getattr(field, 'verbose_name', ''))):
                continue
            value = getattr(obj, name, None)
            text, kind = _display(value)
            if not text:
                continue
            label = str(getattr(field, 'verbose_name', name))
            path = getattr(value, 'name', '') if kind in ('image', 'file') else ''
            item = (label, text, kind, path)
            if any(hint in name.lower() for hint in SNAPSHOT_HINTS) or kind == 'image':
                priority.append(item)
            else:
                rest.append(item)
        except Exception:  # noqa: BLE001
            continue
    for label, text, kind, path in (priority + rest)[:8]:
        entry = {'value': text, 'kind': kind}
        if path:
            entry['path'] = path
        snap[label] = entry
    return snap


# ---------------------------------------------------------------------------
# 3. Admin mixin：写入明细 / 批次 / 删除快照
# ---------------------------------------------------------------------------

class ChangeDetailMixin:
    """给任意 ModelAdmin 挂上"字段级明细"能力。

    继承顺序：``class FooAdmin(ChangeDetailMixin, admin.ModelAdmin)``。
    不改变任何现有保存行为；明细构造失败时静默退回 Django 原生 message。
    """

    # ---- 批次：同一次请求（含批量操作）共用一个短 id ----
    @staticmethod
    def _batch_id(request):
        try:
            batch = getattr(request, '_glowisd_batch_id', None)
            if not batch:
                import uuid
                batch = uuid.uuid4().hex[:8]
                request._glowisd_batch_id = batch
            return batch
        except Exception:  # noqa: BLE001
            return ''

    # ---- 是否真的会被删除（供子类收窄，如受保护超管） ----
    def _can_actually_delete(self, obj):
        return True

    # ---- 写入明细：Django 在 save_model 之后、写日志之前调用 ----
    def construct_change_message(self, request, form, formsets, add=False):
        message = super().construct_change_message(request, form, formsets, add)
        try:
            batch = self._batch_id(request)
            if isinstance(message, list) and message and isinstance(message[0], dict):
                first = message[0]
                if add and 'added' in first:
                    first['added']['details'] = _collect_details(self, form, add=True)
                elif 'changed' in first:
                    first['changed']['details'] = _collect_details(self, form, add=False)
                if batch:
                    first['batch'] = batch
        except Exception:  # noqa: BLE001 —— 明细永远不能影响保存
            pass
        return message

    # ---- 删除：Django 在真正删除之前调用，此时对象还在库里 ----
    def log_deletions(self, request, queryset):
        try:
            ct = ContentType.objects.get_for_model(self.model)
            batch = self._batch_id(request)
            entries = []
            for obj in queryset:
                if not self._can_actually_delete(obj):
                    continue
                payload = {'snapshot': _snapshot(obj)}
                if batch:
                    payload['batch'] = batch
                entries.append(LogEntry(
                    user_id=getattr(getattr(request, 'user', None), 'pk', None),
                    content_type=ct,
                    object_id=str(obj.pk),
                    object_repr=str(obj)[:200],
                    action_flag=DELETION,
                    change_message=json.dumps([{'deleted': payload}], ensure_ascii=False),
                ))
            if entries:
                LogEntry.objects.bulk_create(entries)
        except Exception:  # noqa: BLE001 —— 明细失败时退回 Django 原生删除日志
            try:
                super().log_deletions(request, queryset)
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# 4. 读取侧：解析 / 摘要 / 详情 HTML
# ---------------------------------------------------------------------------

def parse_change_message(entry):
    """解析一条日志，返回 {details, snapshot, batch, has_detail, raw_list}。"""
    out = {'details': [], 'snapshot': {}, 'batch': '', 'has_detail': False, 'raw_list': []}
    raw = entry.change_message or ''
    if not raw:
        return out
    data = None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return out
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return out
    out['raw_list'] = data
    for item in data:
        if not isinstance(item, dict):
            continue
        if item.get('batch'):
            out['batch'] = str(item['batch'])
        for key in ('added', 'changed', 'deleted'):
            block = item.get(key)
            if not isinstance(block, dict):
                continue
            if not out['batch'] and block.get('batch'):
                out['batch'] = str(block['batch'])
            details = block.get('details')
            if isinstance(details, list):
                out['details'].extend([d for d in details if isinstance(d, dict)])
            snap = block.get('snapshot')
            if isinstance(snap, dict):
                out['snapshot'].update(snap)
    out['has_detail'] = bool(out['details'] or out['snapshot'])
    return out


def _object_label(entry):
    try:
        return entry.content_type.model_class()._meta.verbose_name
    except Exception:  # noqa: BLE001
        return '对象'


def _obj_and_short(entry):
    """对象类型 + 名称（名称过长截断）。"""
    return _object_label(entry), _clip(entry.object_repr, 40)


def _detail_pairs(details):
    """把 details 变成 [(label, old, new, kind)]。"""
    pairs = []
    for d in details:
        pairs.append((
            _clip(d.get('label') or d.get('name') or '', 24),
            _clip(d.get('old') or '', VALUE_LIMIT),
            _clip(d.get('new') or '', VALUE_LIMIT),
            d.get('kind') or 'text',
        ))
    return pairs


def _fields_from_raw(raw):
    """从脏数据（dict JSON / 非标准结构）里抽出字段名列表。"""
    if not raw:
        return []
    data = None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        data = None
    blocks = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        for key in ('changed', 'added'):
            inner = block.get(key)
            if isinstance(inner, dict):
                fields = inner.get('fields')
                if isinstance(fields, list) and fields:
                    return [str(f) for f in fields]
    # 正则兜底（含 \uXXXX 转义）
    m = re.search(r'"fields"\s*:\s*\[(.*?)\]', raw, re.S)
    if m:
        names = re.findall(r'"((?:[^"\\]|\\.)+)"', m.group(1))
        out = []
        for name in names:
            try:
                out.append(name.encode().decode('unicode_escape'))
            except (UnicodeDecodeError, UnicodeEncodeError):
                out.append(name)
        if out:
            return out
    return []


def summary_text(entry):
    """一级列表用的一句话摘要（未截断的完整版）。"""
    label, short = _obj_and_short(entry)
    parsed = parse_change_message(entry)
    flag = entry.action_flag

    if flag == DELETION:
        base = f'已删除{label}「{short}」'
        snap = parsed['snapshot']
        preferred = ('简称', '名称(中文)', '中文名', '件号', 'SKU', '售价', '价格', '名称', '英文名')
        extra = []
        for key in preferred:
            info = snap.get(key)
            if isinstance(info, dict) and info.get('value'):
                extra.append(f'{key} {info["value"]}')
        if not extra:
            for key, info in list(snap.items())[:3]:
                if isinstance(info, dict) and info.get('value'):
                    extra.append(f'{key} {info["value"]}')
        if extra:
            base += '（' + '，'.join(extra[:3]) + '）'
        return base

    if flag == 1:  # ADDITION
        base = f'已添加{label}「{short}」'
        pairs = _detail_pairs(parsed['details'])
        if pairs:
            brief = [p[0] + ('：' + p[1] if p[1] else '') for p in pairs[:3]]
            base += '（' + '；'.join(brief) + '）'
        return base

    # CHANGE
    pairs = _detail_pairs(parsed['details'])
    if pairs:
        parts = []
        for field_label, old, new, kind in pairs[:4]:
            if kind == 'secret':
                parts.append(f'{field_label} {SECRET_DISPLAY}')
            elif old and new:
                parts.append(f'{field_label}「{old}」→「{new}」')
            elif new:
                parts.append(f'{field_label} →「{new}」')
            elif old:
                parts.append(f'{field_label}「{old}」→ 空')
            else:
                parts.append(field_label)
        text = f'修改{label}「{short}」' + ('：' + '；'.join(parts) if parts else '')
        if len(pairs) > 4:
            text += f'（共 {len(pairs)} 项）'
        return text
    # 旧日志：只有字段名（Django 原生解析失败时用正则兜底，绝不放原始 JSON 出来）
    try:
        native = entry.get_change_message()
    except Exception:  # noqa: BLE001
        native = ''
    if not native or (isinstance(native, str) and native.lstrip().startswith('{')):
        fields = _fields_from_raw(entry.change_message or '')
        if fields:
            return f'已修改{label}「{short}」：' + '、'.join(fields)
    if not native:
        return f'已修改{label}「{short}」'
    return f'已修改{label}「{short}」：{native}'


def summary_html(entry):
    """一级列表单元格：可点链接 + 超长截断 + 悬停全文 + 明细/无明细标记。"""
    text = summary_text(entry)
    parsed = parse_change_message(entry)
    shown = _clip(text, SUMMARY_LIMIT)
    try:
        url = f'../logentry/{entry.pk}/change/'
        link = format_html(
            '<a href="{}" title="{}" style="display:inline-block;max-width:360px;'
            'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:bottom;">{}</a>',
            url, text, shown,
        )
    except Exception:  # noqa: BLE001
        link = mark_safe(shown)  # noqa: S308 —— 内容已由 _clip 处理，无 HTML
    badges = []
    if parsed['has_detail']:
        badges.append(
            '<span style="display:inline-block;margin-left:6px;padding:1px 6px;border-radius:8px;'
            'background:#E9EDF7;color:#3A4A7A;font-size:11px;white-space:nowrap;">明细</span>'
        )
    else:
        badges.append(
            '<span style="display:inline-block;margin-left:6px;padding:1px 6px;border-radius:8px;'
            'background:#F1F3F8;color:#98A2B8;font-size:11px;white-space:nowrap;">无明细</span>'
        )
    if parsed['batch']:
        badges.append(
            f'<span title="本批操作批次 {parsed["batch"]}" style="display:inline-block;margin-left:4px;'
            'padding:1px 6px;border-radius:8px;background:#FFF4E5;color:#8A5A00;font-size:11px;'
            'white-space:nowrap;">批次</span>'
        )
    return format_html('{}{}', link, mark_safe(''.join(badges)))  # noqa: S308


def detail_html(entry):
    """详情页：对象信息 + 字段/旧值/新值表格 + 批次 + 原始记录折叠。"""
    label, short = _obj_and_short(entry)
    parsed = parse_change_message(entry)
    rows = []

    # —— 对象行 ——
    obj_link = ''
    try:
        model = entry.content_type.model_class()
        if model is not None and entry.object_id:
            obj = model._default_manager.filter(pk=entry.object_id).first()
            if obj is not None:
                from django.urls import reverse
                url = reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_change',
                              args=[obj.pk])
                obj_link = format_html('<a href="{}" target="_blank">打开该{} ↗</a>', url, label)
            else:
                obj_link = format_html(
                    '<span style="color:#A61B1B;">该{}已被删除，无法打开</span>', label)
    except Exception:  # noqa: BLE001
        obj_link = ''

    head = format_html(
        '<div style="padding:14px 16px;background:#F6F8FE;border:1px solid #E4E9F5;'
        'border-radius:6px;margin-bottom:16px;font-size:13px;line-height:1.9;">'
        '<div><strong>{}</strong>「{}」　{}</div>'
        '<div style="color:#5A6B9E;">操作人：{}　时间：{}　{}</div>',
        label, short, obj_link, entry.user, entry.action_time.strftime('%Y-%m-%d %H:%M'),
        format_html('批次：{}', parsed['batch']) if parsed['batch'] else '',
    )

    # —— 明细表 ——
    if entry.action_flag == DELETION and parsed['snapshot']:
        rows.append(('<tr><td colspan="2" style="padding:10px 12px;background:#FDECEA;'
                     'font-weight:700;color:#A61B1B;border:1px solid #F3D3CF;border-bottom:0;">'
                     '删除前快照（对象已不存在）</td></tr>'))
        for key, info in parsed['snapshot'].items():
            value = info.get('value') if isinstance(info, dict) else info
            kind = info.get('kind') if isinstance(info, dict) else 'text'
            path = info.get('path', '') if isinstance(info, dict) else ''
            rows.append(_row_html(key, '', value, kind, '', path, snapshot=True))
    elif parsed['details']:
        header = ('<tr>'
                  '<th style="text-align:left;padding:9px 12px;background:#F6F8FE;'
                  'border:1px solid #E4E9F5;font-size:12px;color:#5A6B9E;">字段</th>'
                  '<th style="text-align:left;padding:9px 12px;background:#F6F8FE;'
                  'border:1px solid #E4E9F5;font-size:12px;color:#5A6B9E;">旧值</th>'
                  '<th style="text-align:left;padding:9px 12px;background:#F6F8FE;'
                  'border:1px solid #E4E9F5;font-size:12px;color:#5A6B9E;">新值</th>'
                  '</tr>')
        rows.append(header)
        for d in parsed['details']:
            rows.append(_row_html(
                _clip(d.get('label') or d.get('name') or '', 30),
                _clip(d.get('old') or '', 200),
                _clip(d.get('new') or '', 200),
                d.get('kind') or 'text',
                d.get('old_path') or '',
                d.get('new_path') or '',
            ))
    else:
        rows.append(
            '<tr><td colspan="3" style="padding:14px 12px;border:1px solid #E4E9F5;'
            'color:#5A6B9E;font-size:13px;">此记录早于 V0.14.0，无旧值明细'
            '（当时只记录了字段名，没有旧值/新值）。</td></tr>'
        )

    table = format_html(
        '<table style="width:100%;border-collapse:collapse;font-size:13px;">{}</table>',
        mark_safe(''.join(str(r) for r in rows)),  # noqa: S308 —— 各部分已 format_html 转义
    )

    raw = ''
    if entry.change_message:
        raw = format_html(
            '<details style="margin-top:16px;">'
            '<summary style="cursor:pointer;font-size:12px;color:#5A6B9E;padding:6px 0;">'
            '原始记录（JSON）</summary>'
            '<pre style="margin:8px 0 0;padding:12px;background:#FAFBFE;border:1px solid #E4E9F5;'
            'border-radius:4px;font-size:12px;line-height:1.6;white-space:pre-wrap;'
            'word-break:break-all;max-height:320px;overflow:auto;">{}</pre></details>',
            entry.change_message,
        )
    return format_html('{}{}{}', head, table, raw)


def _row_html(field_label, old, new, kind, old_path='', new_path='', snapshot=False):
    def cell(value, path=''):
        if kind == 'secret':
            return format_html('<span style="color:#8A93AD;">{}</span>', value or SECRET_DISPLAY)
        if not value:
            return format_html('<span style="color:#B4BCCB;">{}</span>', '（空）')
        if kind in ('image', 'file'):
            short = str(value).rsplit('/', 1)[-1]
            href = _media_url(path or value)
            if kind == 'image':
                return format_html(
                    '<a href="{}" target="_blank" style="display:inline-flex;align-items:center;gap:8px;">'
                    '<img src="{}" alt="" style="width:40px;height:40px;object-fit:cover;'
                    'border:1px solid #E4E9F5;border-radius:3px;background:#F6F8FE;">'
                    '<span style="font-size:12px;word-break:break-all;">{}</span></a>',
                    href, href, short,
                )
            return format_html(
                '<a href="{}" target="_blank" style="font-size:12px;word-break:break-all;">{}</a>',
                href, short,
            )
        return format_html('<span style="word-break:break-word;">{}</span>', value)

    if snapshot:
        # 删除快照只有"值"没有"旧值"，用两列避免一片（空）
        return format_html(
            '<tr>'
            '<td style="padding:9px 12px;border:1px solid #E4E9F5;background:#FCFDFF;'
            'font-weight:600;color:#3A4A7A;white-space:nowrap;vertical-align:top;">{}</td>'
            '<td colspan="2" style="padding:9px 12px;border:1px solid #E4E9F5;color:#162A87;'
            'vertical-align:top;">{}</td>'
            '</tr>',
            field_label, cell(new, new_path),
        )

    return format_html(
        '<tr>'
        '<td style="padding:9px 12px;border:1px solid #E4E9F5;background:#FCFDFF;'
        'font-weight:600;color:#3A4A7A;white-space:nowrap;vertical-align:top;">{}</td>'
        '<td style="padding:9px 12px;border:1px solid #E4E9F5;color:#8A93AD;'
        'vertical-align:top;max-width:260px;">{}</td>'
        '<td style="padding:9px 12px;border:1px solid #E4E9F5;color:#162A87;'
        'vertical-align:top;max-width:260px;">{}</td>'
        '</tr>',
        field_label, cell(old, old_path), cell(new, new_path),
    )


def _media_url(filename):
    """把记录里的文件名拼成媒体 URL（图片记录只存文件名）。"""
    try:
        from django.conf import settings
        media = str(getattr(settings, 'MEDIA_URL', '/media/') or '/media/').rstrip('/')
        if filename.startswith(('http://', 'https://', '/')):
            return filename
        return f'{media}/{filename.lstrip("/")}'
    except Exception:  # noqa: BLE001
        return filename
