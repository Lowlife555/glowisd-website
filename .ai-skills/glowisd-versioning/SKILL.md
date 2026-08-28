---
name: glowisd-versioning
description: "Glowisd 官网项目版本号唯一规则（所有 agent 必须遵守）。Use when tagging a release, bumping a version, naming a delivery/build/README/演示, writing changelog or release notes for the glowisd-website project. 项目版本号规则：首个雏形 V0.1.0，迭代按 Va.b.c 十进制逐位递增（V0.1.9 下一个是 V0.2.0），禁止跳号/改名。"
---

# Glowisd 版本号规则（VERSIONING）

> **适用范围：所有参与 Glowisd 官网项目的 agent（dsh / Claude Code / opencode / hermes），无例外。**
> 本规则同步自 `进度看板.md` 变更记录与 `action-manual.md` 项目宪法，以此处为准。

## 规则

1. **首个完成的雏形** 命名为 **`V0.1.0`**。
2. 此后每次迭代按 **语义化版本 `Va.b.c`** 命名，每一位都是 **十进制** 逐位递增：
   - `V0.1.0 → V0.1.1 → V0.1.2 → … → V0.1.9 → V0.2.0 → V0.2.1 → …`
   - 个位满 `9` 进位到前一位（`V0.1.9` 的下一个版本是 `V0.2.0`），**不允许跳号、不允许随意改名**。
3. 以下场景**必须**使用本规则标注版本号：
   - 交付物、发布包、构建产物
   - `README.md`、CHANGELOG、发布说明
   - 演示给客户/展商的版本
   - git tag、npm `version` 字段
4. 版本号变更时,在 `进度看板.md` 变更记录追加一行(格式:`- 日期 | 版本 X → Y | 原因 | 影响任务`)。

## 示例

| 当前版本 | 下一个版本 |
|----------|-----------|
| V0.1.0 | V0.1.1 |
| V0.1.8 | V0.1.9 |
| **V0.1.9** | **V0.2.0** |
| V0.2.9 | V0.3.0 |
| V1.9.9 | V2.0.0 |

## 速记

> 十进制逐位进:个位满 9 进十位,十位满 9 进百位。首版永远从 **V0.1.0** 开始。
