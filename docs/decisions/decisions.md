# Architecture Decisions

> 重大架构决策及其原因。按时间倒序，每条记录：背景、决策、后果。

## ADR-011: 权限策略集中到 Core，语义异常解耦 HTTP

**日期**: 2026-06 | **状态**: 已实施（PR #71）

**背景**: PR #71 在 `backend/peerpedia_api/policies/articles.py` 中引入集中化权限策略，但依赖 `fastapi.HTTPException`（`raise HTTPException(status_code=403)`）。这与 ADR-002（backend = HTTP 翻译，core = 业务逻辑）冲突——HTTP 状态码泄露到了业务层。同时 `crud_article.py` 用 `ValueError`、路由层用内联 `HTTPException`，三处三种异常，同一类错误表达方式不统一。

**原则依据**: [Fail Fast](https://martinfowler.com/ieeeSoftware/failFast.pdf)（Jim Shore, 2004）——错误在最早时刻暴露。Core 不知道 HTTP，异常名字描述**什么错了**，不描述**HTTP 返回什么**。

**决策**:

1. **定义语义异常在 Core**。`core/peerpedia_core/exceptions.py`：`PeerpediaError` → `NotFoundError` / `NotAuthorizedError` / `ConflictError` / `BadRequestError`。零 HTTP 概念——没有 `status_code`，没有 `headers`。

2. **权限函数搬到 Core**。`backend/peerpedia_api/policies/articles.py` → `core/peerpedia_core/policies/articles.py`。所有 `raise HTTPException(403)` 替换为 `raise NotAuthorizedError("...")`。

3. **一个 Handler 做翻译**。`main.py` 注册 `@app.exception_handler(PeerpediaError)`，一个字典映射语义异常 → HTTP 状态码。只有这一个地方知道映射关系。

4. **`validate_article_has_authors` 保留 `ValueError`**。零作者是数据完整性 bug（服务器内部错误），不是权限拒绝。语义对，不改。

**放弃的方案**:

- 异常带 `status_code` 属性（换名字不换耦合——`ForbiddenError(status_code=403)` 和 `HTTPException(403)` 本质相同）
- 独立的"翻译层"文件（过度设计——一个 handler 函数就够）
- 一次性替换所有路由的内联检查（风险 > 收益，后续 PR 逐步做）

**后果**:

- ✅ Core 零 FastAPI 依赖——`grep fastapi core/` 返回空
- ✅ 报错语义统一：`NotFoundError` / `NotAuthorizedError` / `ConflictError` / `BadRequestError`
- ✅ 路由接入成本低：调 `assert_can_*`，异常自动转 HTTP
- ❌ 路由层仍有内联 `get_author_ids` 检查未替换——后续 PR 逐步接入
- ❌ `visible_statuses_for_user` 同时被 core 和 backend 引用——未来可能要进一步统一

---

## ADR-010: 作者解析失败必须报错，禁止静默修复

**日期**: 2026-06 | **状态**: 已实施（PR #68 评审修订）

**背景**: PR #63 引入多作者支持后，Phase 0 添加了 `repair_article_authors`、`repair_orphan_article_authors` 和 legacy `username@peerpedia` 兼容。这些函数在数据不完整时静默修复，掩盖了数据完整性错误。此外，`api_sync_article` 的 auto-create 路径用 `authors=[]` 创建文章再 `rebuild_article_authors`，中间状态存在无作者文章。

**原则依据**: [Fail Fast](https://martinfowler.com/ieeeSoftware/failFast.pdf)（Jim Shore, 2004）——错误应该在最早可能的时刻暴露，而不是延迟到下游以更难调试的方式炸掉。具体到此 PR：

- 非法输入立即拒绝（不返回 None 让调用方猜）
- 不创建处于中间无效状态的对象（不搞 `authors=[]` 再 rebuild）
- 不让 catch-all 掩盖 bug（不做 orphan repair）
- 失败要 visible（User 不存在就让外键炸出来）

**决策**:

1. **作者必须存在于创建时**。`api_sync_article` 先从 git history 解析作者，再传 `author_list` 给 `create_article`。解析不出作者 → 422，不创建文章。

2. **Git commit email 只用 `{UUID}@peerpedia`**。`resolve_user_id_from_git_email` 不接受 `username@peerpedia`，只有一种规范格式。

3. **解析失败抛异常，不返回 None**。`resolve_user_id_from_git_email` 对未知 email 抛出 `ValueError`。`get_authors_from_git` 逐 commit 捕获 `ValueError`（CI/bot commit 是正常的非作者 commit），但单个函数的默认行为是 loud failure。

4. **孤儿文章不修复，只检测**。删除 `repair_article_authors` 和 `repair_orphan_article_authors`。`validate_article_has_authors` 在发现零作者文章时抛出 `ValueError`——这是 bug，不是需要修复的状态。

5. **`replace_article_authors` 不做兜底**。如果 author_id 对应的 User 行不存在，不做 `sorted_ids.extend` 兜底——外键约束会报错，比静默吞掉好。

**放弃的方案**:

- 保留 `repair_article_authors`（掩盖数据完整性错误，把 bug 正常化）
- 保留 `username@peerpedia` 兼容（多种格式增加歧义，且 username 不是 stable identity）
- `resolve_user_id_from_git_email` 返回 `None`（调用方容易忽略，silent skip）
- 创建文章时用 `authors=[]` 再 rebuild（中间状态无作者，rebuild 失败则残留孤儿记录）

**后果**:

- ✅ 文章不可能处于无作者状态——创建时要么带作者，要么不创建
- ✅ 数据完整性错误立即暴露，不会被静默吞掉
- ✅ 代码更简单：`repair_article_authors` + `repair_orphan_article_authors` 全部删除（-87 行）
- ✅ email 格式唯一，没有歧义
- ❌ CI/bot commit 的 email 在 `get_authors_from_git` 中会被捕获跳过——如果将来 bot 也需要映射到 User，需要额外处理
- ❌ 不再支持 `username@peerpedia` 格式的旧数据——如果数据库中有 username-based email 的历史 commit，它们会被跳过

---

## ADR-009: History 展示 article.json 以暴露状态变更

**日期**: 2026-06 | **状态**: 已实施（PR #66）

**背景**: HistoryPage 的 diff 视图只过滤 `article.md` 和 `article.typ`。读者看不到文章的状态生命周期（draft → sedimentation → published），因为状态变更记录在 `article.json` 里。

**决策**: diff filter 从 `['article.md', 'article.typ']` 扩展为 `['article.md', 'article.typ', 'article.json']`。

**放弃的方案**: 在 UI 里单独展示状态变更时间线（过度设计，diff 已经够用）。

**后果**:
- ✅ 读者可以在 history 里看到文章状态转换
- ✅ 改动极小——一行 filter 表达式
- ❌ article.json 的 diff 是原始 JSON，阅读体验不如专门的状态时间线

---

## ADR-008: 离线优先 + Bundle Sync

**日期**: 2026-06 | **状态**: 已实施

**背景**: 桌面端用户可能断网。需要支持离线编辑、在线同步。

**决策**: Tauri 桌面用本地 SQLite + 本地 Git。网络恢复时用 `git bundle create/apply` 做增量同步。

**放弃的方案**: REST 上传文件内容（丢失 Git 历史、覆盖他人修改）。

**后果**:
- ✅ 离线编辑完全不依赖服务器
- ✅ bundle 是 Git 原语，天然保证 fast-forward 安全
- ❌ 需要本地安装 git CLI
- ❌ 冲突时本地覆盖服务器，多设备场景可能丢数据

---

## ADR-007: Git 是事实来源，DB 是索引/缓存

**日期**: 2026-05（2026-06 修订：评审和分数也移入 Git） | **状态**: 已实施

**背景**: 需要支持 fork、merge、diff、历史追溯。传统 CMS 用数据库存所有内容，做不到这些。后来进一步把评审和分数也移入 Git，DB 降级为缓存。

**决策**: 每篇文章一个独立 Git repo（`~/.peerpedia/articles/{id}/`）。

Git 存储（权威）：
- 文章内容（article.md / article.typ）
- 评审数据（reviews/{id}/scores.json + thread.md）
- 文章分数（从评审聚合）
- 完整历史（git log）
- 作者（git commit author）

DB 存储（索引/缓存）：
- users、follows、bookmarks —— 纯关系数据
- articles 表 —— 元数据 + score 缓存
- reviews 表 —— 评审缓存（可从 Git 重建）
- article_authors —— 作者关联缓存（可从 Git 重建）

**Git-first 写入原则**: 评审写入时先写 Git，成功后才写 DB。Git 失败则 DB 不写。

**放弃的方案**: 所有内容存 DB（没有版本历史）；评审只存 DB（没有审计 trail）。

**后果**:
- ✅ fork = clone repo，merge = git merge
- ✅ diff/history/blame 免费获得
- ✅ 评审有不可变审计 trail
- ❌ 大量文章时文件系统压力大（每篇一个 .git 目录）
- ❌ DB 和 Git 之间没有事务保证——缓存可能和 Git 不一致，需要重建

---

## ADR-006: ArticleAuthor 用 Join Table 而非 JSON

**日期**: 2026-06 | **状态**: 已实施

**背景**: 早期 Article.authors 是 JSON 列表（`["uuid1", "uuid2"]`）。无法按作者查文章、无法约束引用完整性。

**决策**: 创建 `article_authors` join table（复合主键 `article_id + author_id`，带 `position` 排序）。

**放弃的方案**: 保持 JSON 列（简单但不可查询）。

**后果**:
- ✅ 可以按作者查文章、按文章查作者
- ✅ 外键约束保证引用完整性
- ❌ 需要额外的 join 查询
- ❌ Git history 中的作者（从 commit email 提取）和 join table 中的作者是两条独立路径，需要 `rebuild_article_authors()` 同步

---

## ADR-005: Typst + Markdown 双格式

**日期**: 2026-05 | **状态**: 已实施

**背景**: 学术用户需要专业排版（公式、引用、SVG），普通用户需要 Markdown 的简洁。

**决策**: 同时支持 Typst 和 Markdown。编译管线：`detect_format → extract_frontmatter → compile → CompileResult`。Typst 走子进程 typst CLI，Markdown 走 Python markdown 库。

**放弃的方案**: 只用 Typst（门槛太高）；只用 Markdown（学术排版不够）。

**后果**:
- ✅ 两类用户都能用
- ❌ Typst CLI 是外部依赖，用户必须自行安装
- ❌ Markdown 的 math protect → render → restore 顺序不可颠倒（已知坑）
- ❌ 编译缓存（compiled_* 字段）混在 Article 表里

---

## ADR-004: Scoring 的三层结构

**日期**: 2026-05 | **状态**: 已实施

**背景**: 需要评审系统支撑同行评议。评分需要区分自评和社区评审，并且评审人的信誉应该影响评分权重。

**决策**: 三层评分模型：
1. **文章评分**（5 维）：weighted average of reviews，自评权重 0.15，社区评审权重 0.85
2. **信誉评分**（4 维）：从文章的 5 维评分映射到用户的 4 维信誉，按文章状态加权
3. **评审权重**：reviewer 的信誉影响其评审在文章评分中的权重

**放弃的方案**: 简单平均（无法区分评审质量）；纯投票（丢失维度信息）。

**后果**:
- ✅ 高信誉评审者的意见权重更大
- ✅ 自评不会主导最终分数
- ❌ 冷启动问题：新用户信誉 0，评审权重 0.8
- ❌ 所有 commit 的 review 都参与聚合，可能导致历史评分拖累当前评分

---

## ADR-003: 沉淀池（Sedimentation Pool）

**日期**: 2026-05 | **状态**: 已实施

**背景**: 文章发布前需要经过一段时间让社区评审。不能直接 publish。

**决策**: 三态模型：draft → sedimentation → published。新文章默认 7 天沉淀期，作者可延长（最多 180 天）。沉淀期结束后自动发布，零评审时扣 0.5 分。

**放弃的方案**: 直接发布（没有评审机会）；无限期评审（文章卡住）。

**后果**:
- ✅ 给了社区评审的时间窗口
- ✅ 自动发布保证文章不会无限期等待
- ❌ 零评审惩罚可能太轻（0.5 分）
- ❌ 编辑文章重新进入 3 天沉淀——频繁编辑会反复重置

---

## ADR-002: FastAPI 做 HTTP 翻译，Core 做业务逻辑

**日期**: 2026-04 | **状态**: 已实施

**背景**: 需要明确 backend 和 core 的职责边界。

**决策**: backend 只做 HTTP 翻译（验证输入、调 core、返回 JSON）。所有业务逻辑在 core。backend 不直接操作 DB（通过 core 的 CRUD）。

**放弃的方案**: backend 直接操作 SQLAlchemy models（业务逻辑散落、无法测试）。

**后果**:
- ✅ core 层可以独立测试，不依赖 HTTP
- ✅ backend 路由很薄（大部分 < 30 行）
- ❌ 部分权限检查（HTTPException）仍在路由层——issue #88

---

## ADR-001: Python Core + Vue/TS Frontend + Tauri Desktop

**日期**: 2026-04 | **状态**: 已实施

**背景**: 需要同时支持 Web 和桌面。需要快速开发。

**决策**:
- Python (FastAPI + SQLAlchemy) 做后端
- Vue 3 + TypeScript 做前端
- Tauri 2 + Rust 做桌面壳

**放弃的方案**: Electron（太重）；全 Rust（开发速度慢）；全 Python（没有好的桌面方案）。

**后果**:
- ✅ Python 生态丰富，快速原型
- ✅ Tauri 比 Electron 轻 10 倍
- ❌ 两套认证系统（Tauri 本地 UUID vs 服务器 JWT）
- ❌ 两套 SQLite schema（Python models vs Rust db.rs）
