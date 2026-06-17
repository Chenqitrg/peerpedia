# Phase 2 P0 执行计划

> 基于 `docs/plan_reshape.md`，优先级 P0。
> **全部采用 TDD 模式**：先写失败测试 → 实现 → 验证通过。

---

## 新分支

```
feat/phase2-p0
```

基于 `origin/main` 创建。

---

## TDD 工作流（每一步都必须遵守）

```
🔴  RED    → 写一个失败测试（证明功能不存在）
🟢  GREEN  → 写最少代码让测试通过
🔵  REFACT → 重构，保持测试绿
🔄  循环   → 直到功能完整
```

---

## 执行顺序（从简到繁）

### 1. 删除文章 (Delete Articles)

#### 🔴 RED — 先写测试

**Rust test (`test_commands.rs`):**
```rust
#[test]
fn test_delete_article_removes_git_repo() {
    // 1. Create account + save draft → get draft_id + git repo path
    // 2. Assert git repo directory exists
    // 3. Call delete_article(draft_id)
    // 4. Assert DB row deleted (list_drafts returns empty)
    // 5. Assert git repo directory removed
}
```

**Vitest (`UserPage.test.ts`):**
```typescript
it('shows delete button on own article card', () => { ... })
it('clicking delete shows confirmation dialog', () => { ... })
it('confirming delete removes article from list', () => { ... })
it('cancel delete does nothing', () => { ... })
```

#### 🟢 GREEN — 实现

**Rust:**
- 扩展 `delete_draft` → 新增 `delete_article` 命令，删除 DB row + `~/.peerpedia/articles/{id}/` 目录
- 使用 `std::fs::remove_dir_all`

**Frontend:**
- UserPage 文章卡片 + ArticlePage 增加删除按钮（Trash2 icon，与现有 Lucide 图标集一致）
- 确认弹窗（防止误删）
- 乐观更新：删除后立即从列表移除

---

### 2. 差异对比 (Diff View)

#### 🔴 RED — 先写测试

**Rust test (`test_commands.rs`):**
```rust
#[test]
fn test_git_diff_parses_hunks() {
    // 1. Init git repo with two commits
    // 2. Call git_diff(hash1, hash2)
    // 3. Assert returned hunks have correct line types
}

#[test]
fn test_git_diff_empty_for_same_commit() {
    // diff between same commit → empty result
}
```

**Vitest (`DiffView.test.ts`):**
```typescript
it('renders additions in green', () => { ... })
it('renders deletions in red', () => { ... })
it('shows line numbers', () => { ... })
it('handles empty diff gracefully', () => { ... })
```

#### 🟢 GREEN — 实现

**Rust:**
- 新增 `git_diff` Tauri 命令
- 调用 `git diff hash1..hash2 --unified=3`，解析 unified diff 输出为结构化 JSON

**Frontend:**
- 新建 `DiffView.vue` 组件
- 左右分栏，新增行绿色 / 删除行红色，行号
- 集成到 HistoryPage（替换现有 REST API `getDiff` 调用）

---

### 3. 草稿搜索 (Draft Search)

#### 🔴 RED — 先写测试

**Rust test (`test_commands.rs`):**
```rust
#[test]
fn test_search_drafts_fts() {
    // 1. Create account + save two drafts with distinct titles
    // 2. Call search_drafts("keyword", account_id)
    // 3. Assert only matching draft returned
}

#[test]
fn test_search_drafts_empty_query() {
    // empty query → returns all drafts for account
}
```

**Vitest (`UserPage.test.ts`):**
```typescript
it('shows search input on UserPage', () => { ... })
it('typing shows typeahead dropdown', () => { ... })
it('selecting result navigates to article', () => { ... })
it('empty query hides dropdown', () => { ... })
```

#### 🟢 GREEN — 实现

**Rust:**
- DB migration v4: `CREATE VIRTUAL TABLE drafts_fts USING fts5(title, content, tokenize='porter')`
- 触发器自动同步 `drafts` 的 INSERT/UPDATE/DELETE
- 新增 `search_drafts(q, account_id) → Vec<DraftSummary>` 命令
- 使用 FTS5 的 `rank` 排序：title 匹配优先

**Frontend:**
- UserPage 顶部增加搜索框
- 输入时 typeahead 下拉展示匹配结果

---

### 4. Typst 编译 (Typst Compile)

#### 🔴 RED — 先写测试

**Rust test (`test_commands.rs`):**
```rust
#[test]
fn test_compile_typst_success() {
    // Mock typst CLI to return success output
    // Call compile_typst → assert returns output_path
}

#[test]
fn test_compile_typst_failure() {
    // Mock typst CLI to return error
    // Call compile_typst → assert returns error message
}

#[test]
fn test_compile_typst_timeout() {
    // Mock typst CLI to hang → assert timeout error
}
```

**Vitest (`EditorPage.test.ts`):**
```typescript
it('compile button shows spinner while compiling', () => { ... })
it('successful compile shows toast', () => { ... })
it('failed compile shows error message', () => { ... })
```

#### 🟢 GREEN — 实现

**Rust:**
- 新增 `compile_typst` Tauri 命令
- `std::process::Command` spawn `typst compile --format svg/pdf`
- 超时 30s，捕获 stdout/stderr

**Frontend:**
- 编辑器工具栏编译按钮，loading spinner，toast 结果

---

## 不在本次 P0 范围

| 功能 | 原因 |
|------|------|
| 编辑器体验 (CodeMirror) | 用户要求推迟 |
| Forward/Share Paper | 依赖完整 Git 打包，建议 P1 |
| Distribute & Feedback | 等 P0 稳定 |
| arXiv Mirror | P1 |
| Tags/Categories | P1 |
| AI Agent | 探索中 |
