---
name: glowisd-vision-ocr
description: "Glowisd 产品目录识图任务规范(件号 R→GW 改写 + 品名识别)。Use when recognizing part numbers and names from scanned product catalog photos using a vision model. 识图:件号改写规则/品名位置/裁剪区域/输出 JSON 格式。"
---

# Glowisd 产品识图任务规范(踩坑沉淀)

> 适用:opencode / 任何用 vision 模型(deepseek-v4-flash-vision-exp)做产品目录识图的 agent。

## 任务背景

产品目录.pdf 是**扫描版**(无文字层),183 张产品照片已从 PDF 提取(`media/products/pXXX_N.jpg`),件号和品名需要**视觉识别**。

## 识别规则(用户指定,不可改)

1. **件号改写**:PDF 中件号带 `R` 前缀(如 `R202419010`)→ 改成 `GW` 前缀(`GW202419010`)
2. **件号位置**:产品照片**左上角**(灰色字)
3. **品名位置**:照片中**红色波浪线标记处**
4. **裁剪**:按图中蓝色方框区域裁剪产品图

## 输出格式(严格)

输出到 `products/fixtures/product_annotations.json`:
```json
[
  {"image": "products/p001_1.jpg", "pn_original": "R202419001", "pn": "GW202419001", "part_name": "", "part_name_en": ""},
  ...
]
```
- `image` 必须与 `media/products/` 下文件名一致
- 条数 = 183(缺条/错名会打断入库)
- 识别不出的件号/品名留空字符串,不要编造

## 踩坑记录

1. **批量识图耗时**:183 张图 vision 识别需要较长时间 → 建议后台运行,分页处理,先出件号再补品名
2. **易混淆**:扫描件中 `R` 与 `GW` 相邻数字易误读 → 每个件号对照原图复核一遍
3. **图片路径**:用相对路径 `products/pXXX_N.jpg`,别写绝对路径
4. **品名双语**:有英文名就填 `part_name_en`,没有就留空,后续人工补
5. **空白横幅**:个别页(如 p061_2/3)是空白横幅无内容 → 留空标注,不要强行编造

## 验证

完成后:件号条数 = 183,`GW` 前缀覆盖 ≥ 180 条,品名 ≥ 18 条(后续补全),JSON 合法可被 Django fixture 读取。
