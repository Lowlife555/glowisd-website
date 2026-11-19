"""DeepSeek 阿拉伯语翻译服务。

用途：后台保存产品/分类/站点内容时自动生成阿语字段；也可由管理命令批量翻译存量数据。

设计要点：
- 不依赖第三方库，纯标准库 urllib 调用 https://api.deepseek.com/chat/completions
- API Key 存在站点设置（SiteSettings.deepseek_api_key），后台自行填写，不写入代码/环境变量
- 任何失败（无 key / 网络错误 / 返回格式异常）都返回 None，调用方保留原值，绝不阻塞保存
- 统一术语表，保证同一术语全站译法一致（工程机械行业术语）
"""
import json
import re
import urllib.error
import urllib.request

API_URL = 'https://api.deepseek.com/chat/completions'
MODEL = 'deepseek-chat'

# 工程机械行业术语表（中/英 → 阿语固定译法），保证全站一致
GLOSSARY = {
    '摊铺机': 'آلة الرصف',
    'paver': 'آلة الرصف',
    '铣刨机': 'آلة التفريز',
    'milling machine': 'آلة التفريز',
    '压路机': 'المدحلة',
    'road roller': 'المدحلة',
    '传感器': 'المستشعر',
    'sensor': 'المستشعر',
    '线缆': 'الكابل',
    'cable': 'الكابل',
    '控制手柄': 'مقبض التحكم',
    'control handle': 'مقبض التحكم',
    '显示控制器': 'وحدة التحكم بالعرض',
    'display': 'شاشة العرض',
    '接线盒': 'صندوق التوصيل',
    'junction box': 'صندوق التوصيل',
    '找平臂': 'ذراع التسوية',
    'leveling arm': 'ذراع التسوية',
    '平衡梁': 'شعاع التوازن',
    'balance beam': 'شعاع التوازن',
    '电路板': 'لوحة الدوائر',
    'pcb': 'لوحة الدوائر',
    '膜开关': 'مفتاح غشائي',
    'membrane switch': 'مفتاح غشائي',
    '套件': 'الطقم',
    'kit': 'الطقم',
    '工程机械': 'آلات الإنشاءات',
    'construction machinery': 'آلات الإنشاءات',
    '电控系统': 'نظام التحكم الإلكتروني',
    'electronic control system': 'نظام التحكم الإلكتروني',
    '定制': 'التخصيص',
    'customization': 'التخصيص',
    '工厂': 'المصنع',
    'factory': 'المصنع',
    '车间': 'الورشة',
    'workshop': 'الورشة',
    '询价': 'طلب عرض السعر',
    'inquiry': 'طلب عرض السعر',
    '质保': 'الضمان',
    'warranty': 'الضمان',
    '起订量': 'الحد الأدنى للطلب',
    'MOQ': 'الحد الأدنى للطلب',
}

SYSTEM_PROMPT = (
    'You are a professional technical translator for construction machinery (paving, milling, compaction) '
    'electronic components. Translate the given Chinese/English texts into Modern Standard Arabic. '
    'Rules: 1) Keep product codes, part numbers (P/N, SKU) and alphanumeric identifiers unchanged; '
    '2) Keep numbers, units (mm, V, °C) in Latin form; '
    '3) Use the fixed terminology provided; '
    '4) Output ONLY a JSON array of strings, same order and length as the input, no explanations.'
)


def _api_key():
    from core.models import SiteSettings
    return (SiteSettings.load().deepseek_api_key or '').strip()


def _glossary_hint():
    lines = ['%s => %s' % (k, v) for k, v in GLOSSARY.items()]
    return 'Terminology (source => Arabic):\n' + '\n'.join(lines)


def translate_ar(texts, timeout=25):
    """把一组文本翻译成阿语。成功返回等长 list[str]，失败返回 None。

    texts: list[str]，空字符串原样返回空字符串（不发请求）。
    """
    texts = ['' if t is None else str(t) for t in texts]
    idx = [i for i, t in enumerate(texts) if t.strip()]
    if not idx:
        return list(texts)

    key = _api_key()
    if not key:
        return None

    payload = {
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT + '\n\n' + _glossary_hint()},
            {'role': 'user', 'content': json.dumps([texts[i] for i in idx], ensure_ascii=False)},
        ],
        'temperature': 0.2,
        'stream': False,
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % key,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        content = data['choices'][0]['message']['content']
        translated = _parse_json_array(content)
        if translated is None or len(translated) != len(idx):
            return None
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError,
            json.JSONDecodeError, OSError, ValueError):
        return None

    out = list(texts)
    for pos, value in zip(idx, translated):
        out[pos] = str(value).strip() if value is not None else ''
    return out


def _parse_json_array(content):
    """从模型回复里稳健地提取 JSON 数组（容忍 ```json 代码块包裹）。"""
    if not content:
        return None
    text = content.strip()
    m = re.search(r'```(?:json)?\s*(.*?)```', text, re.S)
    if m:
        text = m.group(1).strip()
    start = text.find('[')
    end = text.rfind(']')
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        value = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, list) else None
