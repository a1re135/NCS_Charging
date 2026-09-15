"""Local UI translations. Never machine-translate or modify user-entered data."""
import json
import re
from pathlib import Path
from flask import request

EN = json.loads((Path(__file__).resolve().parent.parent / 'static/i18n/en.json').read_text(encoding='utf-8'))

def current_language():
    language = request.headers.get('X-NCS-Language') or request.args.get('lang', 'zh')
    return 'en' if language == 'en' else 'zh'

def translate(text):
    if current_language() != 'en' or not isinstance(text, str):
        return text
    if text in EN:
        return EN[text]
    patterns = [
        (r'请填写(.+)（1–(\d+) 个字符）', lambda m: f"Enter {EN.get(m[1], m[1])} (1–{m[2]} characters)."),
        (r'金额须(大于等于 0|大于 0)、不超过 (.+) 元，最多两位小数', lambda m: f"Amount must be {'at least 0' if m[1]=='大于等于 0' else 'greater than 0'}, at most {m[2]} CNY, with no more than two decimal places."),
        (r'(.+)须在 (.+) 到 (.+) 之间', lambda m: f"{EN.get(m[1], m[1])} must be between {m[2]} and {m[3]}."),
        (r'(.+)格式应为 HH:MM', lambda m: f"{EN.get(m[1], m[1])} must use HH:MM format."),
        (r'(.+)格式不正确，应为 YYYY-MM-DD', lambda m: f"{EN.get(m[1], m[1])} must use YYYY-MM-DD format."),
        (r'(.+)无效', lambda m: f"Invalid {EN.get(m[1], m[1])}."),
    ]
    for pattern, render in patterns:
        match = re.fullmatch(pattern, text)
        if match:
            return render(match)
    return text

def operation_display(text):
    """Translate only known audit-message formats; IDs and arbitrary text stay intact."""
    if current_language() != 'en':
        return text
    match = re.fullmatch(r'(启用|冻结)用户 #(\d+)', text)
    if match:
        return f"{'Enabled' if match[1] == '启用' else 'Froze'} user #{match[2]}"
    match = re.fullmatch(r'(保存电站|删除电站|保存分时价格规则|删除分时价格规则|保存电桩) #(\d+)', text)
    if match:
        return f'{EN.get(match[1], match[1])} #{match[2]}'
    match = re.fullmatch(r'电桩 #(\d+)：([a-z]+)(（软件模拟）)?', text)
    if match:
        return f'Charger #{match[1]}: {match[2]}' + (' (software simulation)' if match[3] else '')
    match = re.fullmatch(r'登记故障 #(\d+) / 电桩 #(\d+)', text)
    if match:
        return f'Reported fault #{match[1]} / Charger #{match[2]}'
    match = re.fullmatch(r'更新故障 #(\d+)：([a-z]+)', text)
    if match:
        return f'Updated fault #{match[1]}: {match[2]}'
    return text
