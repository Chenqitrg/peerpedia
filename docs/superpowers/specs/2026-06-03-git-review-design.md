# Git Diff + Review 系统设计

> 2026-06-03 | Phase 3 → Phase 4 过渡

## 1. 当前状态总结

### 已完成
- **322 tests, 0 failures**
- 5 篇 demo 文章（4 Markdown + 1 Typst），内容各异，含 KaTeX 数学公式
- 文章互相引用（Tensor → Category + Holographic；Quantum → Tensor + Holographic）
- KaTeX 本地 serving，国内可访问
- Typst 编译为 PDF，页面显示预览卡片
- 贡献时间线 + 编辑提案 HTML 渲染（不再泄漏 JSON）
- 每篇文章底层是 git repo（`init_article_repo` + `commit_article`）

### 未完成（本次计划覆盖）
| # | 功能 | 当前状态 |
|---|------|---------|
| 4 | Git diff 视图 | 后端有 `get_commit_history`、`get_blame`，前端无 UI |
| 5 | 行级评论 + 建议修改 | 无。石渠阁有参考实现 |
| 6 | Submit/Review demo | 无端到端 demo 脚本 |

---

## 2. 石渠阁可复用分析

石渠阁（`~/Projects/shiquge`）v0.1.16 有一个完整的 PR/review 系统，关键组件：

### 2.1 PR 工作流模型（可直接参考）

```
submit → pending → review → approved → merge
                  → changes_requested → author 修改 → pending (循环)
                  → comment（行级评论）
                  → withdraw（作者撤回）
                  → reopen（作者重开）
```

### 2.2 行级评论数据结构（可适配）

```json
{
  "id": 1,
  "author": "reviewer_name",
  "body": "这里公式有误，建议改成...",
  "line": 42,
  "line_end": 45,
  "type": "comment" | "suggestion",
  "suggestion": "修正后的内容\n多行支持",
  "resolved": false,
  "created_at": 1717401600
}
```

### 2.3 建议修改应用逻辑（_pr_apply）

石渠阁的 `_pr_apply`：根据 `line`/`line_end` 定位行范围 → 替换为 `suggestion` 内容。PeerPedia 可以做到更精确——用 git 定位后生成新 commit。

### 2.4 与 PeerPedia 的差异

| 维度 | 石渠阁 | PeerPedia |
|------|--------|-----------|
| diff 来源 | LCS 算法（JS，纯文本对比） | git diff（GitPython，已有） |
| 存储 | `prs.json` 文件 | SQLite（EditProposal + ReviewComment 表） |
| 版本管理 | 无（存 old_content 字符串） | 有 git repo，每个 PR merge 生成 commit |
| 前端 | vanilla JS + MathJax | Jinja2 + HTMX + KaTeX |
| 网络 | Tailscale P2P | LAN UDP + 未来 IPFS |

**结论**：PR 工作流模型和行级评论数据结构可以直接参考石渠阁。但底层用 git diff 替代 LCS，存储用 SQLite，前端用 HTMX。

---

## 3. Git Diff 视图设计

### 3.1 数据流

```
浏览器点击 commit → HTMX GET /api/v1/articles/{id}/diff/{commit_hash}
  → Python 调用 git diff <parent>..<commit>
  → 渲染为 diff2html HTML
  → HTMX swap 到 #diff-panel
```

### 3.2 新增 API 端点

| 端点 | 说明 |
|------|------|
| `GET /api/v1/articles/{id}/commits` | 返回 commit 历史列表（已有 `get_commit_history`，接到 Web） |
| `GET /api/v1/articles/{id}/diff/{hash}` | 返回该 commit 的 diff（git diff parent..hash） |
| `GET /api/v1/articles/{id}/diff/{hash1}..{hash2}` | 返回两个 commit 之间的 diff（可选） |
| `GET /api/v1/articles/{id}/blame` | 返回 blame 数据（`get_blame` 接到 Web） |

### 3.3 前端渲染

**方案 A**：服务端渲染 diff HTML（Python 生成，HTMX swap）
- 优点：简单，不依赖 JS 库
- 缺点：大 diff 时 HTML 体积大，交互受限

**方案 B**：使用 `diff2html`（推荐）
- 优点：GitHub 风格、代码高亮、折叠展开、行号、3KB min+gz
- 缺点：需要加载一个 JS 文件
- CDN：`unpkg.com/diff2html` 或本地 serving

**选择方案 B**。diff2html 支持 unified diff 和 side-by-side 两种模式。

### 3.4 页面布局

```
┌─────────────────────────────────────────────────────┐
│  文章标题 + 元信息                                    │
├─────────────────────────────────────────────────────┤
│  [版本历史] [当前内容]                                │  ← Tab
├─────────────────────────────────────────────────────┤
│  Commit 列表（左 300px）    │  Diff 视图（右）         │
│  ┌─────────────────────┐  │  ┌───────────────────┐  │
│  │ v0.3 - Fix typos    │  │  │ - old line         │  │
│  │ v0.2 - Add section  │  │  │ + new line         │  │
│  │ v0.1 - Initial      │  │  │   context line     │  │
│  └─────────────────────┘  │  └───────────────────┘  │
│                            │  💬 点击行号添加评论     │
└─────────────────────────────────────────────────────┘
```

### 3.5 新增数据库表

```sql
-- 行级评论（参考石渠阁模型）
CREATE TABLE review_comment (
    id TEXT PRIMARY KEY,
    article_id TEXT NOT NULL,
    commit_hash TEXT NOT NULL,      -- 关联到哪个 commit
    file_path TEXT NOT NULL DEFAULT '',
    line_start INTEGER NOT NULL,    -- 起始行号（diff 中的行）
    line_end INTEGER,               -- 结束行号
    author_id TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    suggestion TEXT DEFAULT '',     -- 建议修改的内容
    comment_type TEXT DEFAULT 'comment',  -- 'comment' | 'suggestion'
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (article_id) REFERENCES article(id)
);
```

---

## 4. Review 工作流设计

### 4.1 完整流程

```
1. Reviewer 浏览文章 → 点击"审稿" → 打开 Diff 视图
2. 点击 diff 中某一行 → 弹出评论框 → 输入评论/建议
3. 可选：写建议修改内容（markdown 代码块）
4. 提交评论 → 保存到 review_comment 表
5. Author 看到评论 → 在本地修改文件 → peerpedia submit（新 commit）
6. 新 commit 出现 → 评论标记为 resolved
```

### 4.2 与现有 EditProposal 的关系

现有 EditProposal 是**整篇文章**的修改提案（minor/medium/major）。
新增 ReviewComment 是**行级**的评论/建议。两者互补：

- **EditProposal**：一个人提 "我要改这篇文章" → 审核 → 合并
- **ReviewComment**：在 diff 的某一行写 "这里有问题" 或 "建议改成 X"

当 Author 应用建议后，通过 `_pr_apply` 逻辑（替换行 → 新 commit），不经过 EditProposal。

### 4.3 API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/articles/{id}/commits` | commit 历史 |
| `GET` | `/articles/{id}/diff/{hash}` | diff 数据（unified diff 文本或 JSON） |
| `GET` | `/articles/{id}/comments?commit={hash}` | 某个 commit 的所有评论 |
| `POST` | `/articles/{id}/comments` | 添加行级评论 |
| `POST` | `/articles/{id}/comments/{cid}/resolve` | 解决评论 |
| `POST` | `/articles/{id}/comments/{cid}/apply` | 应用建议（author only） |

---

## 5. Submit/Review Demo 脚本

### 5.1 场景设计

一个完整的故事线，4 个人参与：

```
Scene 1: zhangliang 提交"Tensor Network"文章
Scene 2: liqun 审稿 → approve → 文章 published
Scene 3: wangshouheng 在 diff 中看到 tensor.md L42 → 写行级评论：
         "这里应该引用 Holographic 的结果"
Scene 4: zhangliang 看到评论 → 修改文章 → 重新提交（commit v0.2）
Scene 5: zhaotongji 提交"Quantum Info Geometry" → 引用 Tensor + Holographic
Scene 6: liqun 审稿 Quantum 文章 → 建议修改 L15 公式 → zhaotongji 接受
```

### 5.2 Demo 脚本形式

用 Python 脚本调用 CLI 命令模拟完整流程：

```bash
# demo_review.sh（或 Python 脚本）
peerpedia submit tensor.md          # Scene 1
peerpedia review <id> --accept      # Scene 2
# Scene 3: 通过 API POST 创建行级评论
curl -X POST /api/v1/articles/<id>/comments -d '{"line":42,"body":"..."}'
# Scene 4: 修改后重新提交
peerpedia submit tensor_v2.md --author zhangliang
# etc.
```

---

## 6. 实现优先级

| 顺序 | 任务 | 预估工作量 | 依赖 |
|------|------|-----------|------|
| 1 | `GET /articles/{id}/commits` API | 小（接现有 `get_commit_history`） | 无 |
| 2 | `GET /articles/{id}/diff/{hash}` API | 中（GitPython diff + 格式化） | 1 |
| 3 | diff2html 集成 + 文章页 diff 面板 | 中（HTML 模板 + CSS） | 2 |
| 4 | ReviewComment 表 + CRUD | 中（SQLAlchemy 模型 + API） | 无 |
| 5 | 行级评论 UI（点击 diff 行 → 评论） | 中（JS 交互 + HTMX） | 3, 4 |
| 6 | 建议修改 apply 逻辑 | 中（git commit + 行替换） | 5 |
| 7 | Submit/Review demo 脚本 | 小（调用已有 CLI + API） | 全部 |

**总计**：约 500-800 行新代码，3-4 个新文件。

---

## 7. 关键决策

1. **Git diff vs LCS**：用 git diff（PeerPedia 已有 git，石渠阁没有）
2. **diff2html**：轻量 JS 库，GitHub 风格渲染，本地 serving
3. **评论存储在 SQLite**：不是 JSON 文件（已有 DB 基础设施）
4. **评论关联到 commit**：不是关联到行号（行号在 commit 间变化）
5. **PR 模型参考石渠阁**：工作流一致，数据模型相似

---

## 8. 已知限制 & 未来路线图

### 8.1 Typst 文章内嵌显示（当前不可用）

Typst 文章编译后输出 PDF，无法像 Markdown 一样直接在页面内渲染为 HTML。
当前方案：显示预览卡片（📄 图标 + "在新标签页查看"/"下载 PDF" 按钮）。

**根本解决方案**：等待 Typst 支持 HTML 输出。
- Typst 0.12+ 已内置 `typst query` 和 `--format html` 实验性支持
- 跟踪 issue：https://github.com/typst/typst/issues/721
- 一旦 Typst 稳定支持 `typst compile --format html`，PeerPedia 的 TypstBackend
  可以直接输出 HTML，像 Markdown 文章一样内嵌显示

**临时方案**：PDF 预览卡片 + 新标签页查看。当前够用，不改动。

### 8.2 其他已知限制

| 限制 | 状态 | 计划 |
|------|------|------|
| Typst HTML 输出 | ⏳ 等待上游 | Typst HTML 稳定后接入 |
| Git diff 视图 | 📋 设计中 | 本 spec 第 3 节 |
| 行级评论 | 📋 设计中 | 本 spec 第 4 节 |
| LAN 多节点 review | 🔮 远期 | Phase 5+ |
