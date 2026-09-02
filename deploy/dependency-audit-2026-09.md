# Glowisd 依赖安全审计报告（2026-09）

> 审计命令：`python -m pip_audit -r requirements.txt --progress-spinner off`
> 工具：pip-audit 2.10.1（PyPI + OSV 漏洞库）
> 时间：2026-09-03（北京时间）

## 结论

```
No known vulnerabilities found
```

`requirements.txt` 中全部 6 个锁定依赖 **均无已知 CVE**，无需升级或豁免。

## 审计范围（requirements.txt 全量锁定版本）

| 依赖 | 版本 | 审计结果 | 说明 |
|------|------|----------|------|
| Django | 6.1 | ✅ 无已知 CVE | 当前稳定版；需 Django ≥5.0，6.1 满足 |
| django-simpleui | 2026.1.13 | ✅ 无已知 CVE | 与 Django 6.1 兼容（现有后台正常） |
| Pillow | 12.3.0 | ✅ 无已知 CVE | 图片处理（水印/裁剪） |
| user-agents | 2.2.0 | ✅ 无已知 CVE | 登录审计 UA 解析 |
| py-ip2region | 3.0.4 | ✅ 无已知 CVE | 登录审计离线 IP 归属 |
| gunicorn | 26.2.0 | ✅ 无已知 CVE | 生产 WSGI |

## 决策记录

- **无 CVE → requirements.txt 未做任何版本变更**（避免为“升级而升级”引入兼容性风险）。
- 本次审计属 P3「依赖安全审计」收口，将作为后续版本迭代的基线；建议每次升版本前重跑
  `python -m pip_audit -r requirements.txt`。
