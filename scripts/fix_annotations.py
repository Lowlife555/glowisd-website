import json

NAMES = {
    "p001_2": "Control handle Can",
    "p001_3": "Sonic sensor Can",
    "p002_1": "Sonic sensor Can",
    "p002_2": "Junction box",
    "p002_3": "Rotary /grade sensor Can",
    "p003_1": "Slope sensor Can",
    "p003_2": "Control handle PWM",
    "p003_3": "Sonic ski Pwm",
    "p004_1": "Sonic ski Pwm",
    "p004_2": "Rotary /grade sensor Pwm",
    "p004_3": "Slope sensor",
    "p010_1": "Bomag ABG",
    "p012_3": "Keyboard",
    "p016_3": "Dynapac141",
    "p017_2": "58614",
    "p036_2": "10Hole-12Hole",
    "p042_3": "10-7can Y",
    "p043_1": "Typ11 ABG",
}

path = r'C:\Users\15782\Desktop\dsh_glowised_website\site\glowisd-website\products\fixtures\product_annotations.json'
data = json.load(open(path, encoding='utf-8'))
filled = 0
for item in data:
    key = item['image'].split('/')[-1][:-4]  # p001_1
    if key in NAMES:
        item['part_name'] = NAMES[key]
        item['part_name_en'] = NAMES[key]
        filled += 1
json.dump(data, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(f'JSON 品名填充: {filled} 条')
