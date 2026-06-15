# Changelog

PeerPedia 遵循[语义版本](https://semver.org/lang/zh-CN/)。0.x 阶段 API 不稳定，每个次版本号代表一个里程碑。

## [0.2.1] — 2026-06

线上/线下共存。

- Tauri 离线编辑 + 联网同步
- `useDraftPersistence` 双模式 abstraction
- Policy layer 统一权限检查
- Git bundle "电话模型"同步（pull-before-push 协议）
- Hash 一致性保证（客户端和服务器同一份 hash）
- 发现 commit hash 安全漏洞（Git `--author` 可伪造，评审数据缺少文件级权限）
- 架构文档（系统地图、core、backend、frontend）+ 同步协议文档
- 记录 7 个架构/安全问题（#85–#92）
- Codecov 94% 覆盖率门禁 + Pre-commit hooks
- 版本号从 0.3.0 降回 0.2.1

## [0.2.0] — 2026-06

第一个可运行的版本。

- Tauri 桌面端：本地 Git 写作、离线 Markdown/Typst 编辑
- FastAPI 服务器：REST API + SQLite 缓存
- 五维评分 + 沉淀池 → 发布流程
- Git 作为 Source of Truth，数据库作为缓存/索引
- **已知问题**：线上/线下路径不统一，Web 和 Tauri 作者处理不一致
