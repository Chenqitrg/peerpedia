# Phase 2.1 — Online Polish · 联网功能打磨

> **目标：** 修完已知 bug，完整测试写作-发布-评审闭环。之后进入正式使用。

---

## Week 1 — Bug 清零 · 修 bug

### 已知 Bug

| # | Bug | 现象 | 优先级 |
|---|-----|------|--------|
| 1 | Bookmark 需要认证 | Tauri 连服务器后，书签操作提示 authentication required | P0 |
| 2 | School → 用户主页不可达 | 从 Schools 页面点击其他作者，无法进入其主页 | P0 |
| 3 | 关注提示"没有此人" | Tauri 连服务器后，关注/取关操作报 user not found | P0 |
| 4 | 其他待发现 | 使用中遇到的边角问题 | P1 |

### 策略

- 每个 bug 先写 xspec 测试 → 复现 → 修 → 验证
- 不做大范围重构，保持外科手术式改动
- 每个 bug 单独 PR，方便回溯

---

## Week 2 — 测试写作闭环 · 自己用起来

### 完整走通以下流程

| 场景 | 步骤 |
|------|------|
| 注册/登录 | Tauri 本地注册 → 服务器同时注册 → 双栈认证 |
| 写文章 | 创建 Markdown/Typst 文章 → 多次保存（git commit）→ 查看历史 |
| 发布到 Pool | 写自评 → 发布 → 在 Pool 页面看到自己的文章 |
| 浏览/评论 | 浏览他人文章 → 写评论 → 收到回复 |
| 关注/Feed | 关注其他作者 → Feed 页面看到其动态 |
| Fork/Merge | Fork 一篇文章 → 修改 → 提交 merge proposal |
| 书签 | 收藏文章 → 在 Bookmarks 页面看到 |
| 搜索 | 本地搜索 + 网络搜索 |

### 输出

- 每走通一个场景，写对应的 xspec 测试
- 遇到 bug 当场修
- 记录体验问题（UX papercuts）——不急着修，先记下来

---

## Phase 2.2+ — 后续（不在本周范围）

- 服务器部署（见 `plan_reshape.md` P2）
- arXiv 镜像
- 标签/分类
- AI agent

---

## 与 plan_reshape.md 的关系

`plan_reshape.md` 是长期路线图（Phase 1.5 → Phase 2 → Phase 3）。本文件是 Phase 2 的**第一步执行计划**——聚焦 bug 修复和闭环测试，不引入新功能。

---

*Created: 2026-06-10 · This week's focus: fix bugs, test writing flows end-to-end.*
