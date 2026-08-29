---
name: glowisd-collab
description: "Glowisd 多 agent 协作铁律(所有 agent 必须遵守)。Use when starting any task in the glowisd-website workspace: reading/writing files, updating the kanban board, delegating work, or checking cost status. 协作规则:文件编辑互斥/看板唯一真相源/委派登记/省钱守护。"
---

# Glowisd 多 Agent 协作规范

> 适用范围:所有参与 Glowisd 官网项目的 agent(dsh / Claude Code / opencode / hermes),开工前必读。

## 1. 唯一真相源

- **任务状态、进度日志、变更记录、委派记录**一律以 `glowisd-website/进度看板.md` 为准
- 禁止在其他地方另建状态副本;开始/完成/委派任务必须更新看板

## 2. 文件编辑互斥(防打架铁律)

同一时间只允许一个 agent 编辑同一个文件:
1. 编辑前 → 在看板「文件锁登记」区登记:`- 时间 | 文件名 | 编辑者 | 预计时长`
2. 编辑完成 → 立即删除登记
3. 看到文件被他人登记 → 不许碰,等对方完成
4. 只读操作随时可以,不受限
5. 违规导致的覆盖/冲突由后编辑者负责修复

> 经验教训:2026-08-29 Hermes 与 dsh 同时编辑 contact.html 险些互相覆盖,故立此规则。

## 3. 开工前必读:省钱守护

- 读 `glowisd-website/运行调度状态.md`
- `PAUSED_HIGH_COST`(北京周一至五 9-12/14-18,DeepSeek 价×2)→ 暂停发起新 LLM 任务,做完当前步骤即停,可做本地免费工作
- `OVERRIDE_RUN` → 正常干活(用户已明确本次不省钱)
- `RUNNING` → 正常

## 4. 委派与分工

- 核心编码 → Claude Code;批量/机械 → opencode;识图 → vision 模型(deepseek-v4-flash-vision-exp);验收/监控/推送 → hermes
- 委派他人必须看板登记(禁止私下委派不留痕)
- 需要用户决策(如腾讯云控制台操作)→ 立即停下,通过微信简报告知,不瞎试

## 5. 交付标准

"完成" = 代码写完 + 本地跑起来 + 验收标准全过 + 看板已更新 + 版本号按 glowisd-versioning 规则
