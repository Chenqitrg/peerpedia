# L4 文章同步 — 实施计划

> **创建日期:** 2026-06-11  
> **分支:** main  
> **审查状态:** ENG + DESIGN CLEARED  
> **预计工期:** 3-4 小时（含测试）

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [架构概览](#2-架构概览)
3. [前置条件](#3-前置条件)
4. [任务 T1：Rust — drafts 表加 sync 列](#4-任务-t1rust--drafts-表加-sync-列)
5. [任务 T2：Rust — set_server_article_id 命令](#5-任务-t2rust--set_server_article_id-命令)
6. [任务 T3：TypeScript — useArticleSync composable](#6-任务-t3typescript--usearticlesync-composable)
7. [任务 T4：ArticleCard — 状态图标](#7-任务-t4articlecard--状态图标)
8. [任务 T5：ArticlePage — 冲突图标 + Diff View 面板](#8-任务-t5articlepage--冲突图标--diff-view-面板)
9. [任务 T6：EditorPage — Upload 入口](#9-任务-t6editorpage--upload-入口)
10. [任务 T7：书签/关注离线提示](#10-任务-t7书签关注离线提示)
11. [任务 T8：后端 E2E 测试](#11-任务-t8后端-e2e-测试)
12. [任务 T9：前端 vitest 测试](#12-任务-t9前端-vitest-测试)
13. [全局验证](#13-全局验证)
14. [手动端到端测试](#14-手动端到端测试)
15. [NOT in Scope](#15-not-in-scope)

---

## 1. 背景与目标

### 问题

L1-L3（PR #38）实现了认证 token 同步和 profile 同步。用户可以在 Tauri 桌面端离线写作，服务器上线后自动获取 JWT。但是：

1. **书签/关注的离线状态不友好** —— `useBookmarkToggle` 在离线时调用不存在的 Rust IPC 命令（`add_bookmark` / `follow_user`），静默失败。
2. **文章无法同步到服务器** —— 本地写的文章永远留在本地，无法进入沉淀池、无法被社区评审。
3. **没有冲突处理** —— 如果服务器上有文章的新版本（多设备或之前 push 过），本地不知道。

### 本 PR 范围（L4）

| 内容 | 说明 |
|------|------|
| 文章首次上传 | 本地文章 POST 到服务器创建 |
| 文章后续更新 | 本地编辑后 PUT 到服务器更新 |
| 冲突检测 | 对比本地 HEAD 与 server_commit_hash |
| 冲突解决 | Diff View + Keep Local / Use Remote |
| 书签/关注离线提示 | 按钮置灰 + tooltip，不调不存在的 IPC |

### 核心设计原则

**没有独立的 Push 按钮。冲突解决就是同步。**

```
三种状态：

  1. 首次上传（无 server_article_id）
     → 显示 Upload 图标

  2. 已同步（server_commit_hash === local HEAD）
     → 无图标，安静状态

  3. 冲突（server_commit_hash !== local HEAD）
     → 显示 GitCompare 图标（强制处理，不能忽略）
     → 点击 → Diff View
       → "Keep Local"  = PUT 到服务器（保留本地，覆盖远程）
       → "Use Remote" = git reset 到服务器版本（丢弃本地）
```

---

## 2. 架构概览

### 数据流

```
首次上传:
  EditorPage/ArticleCard → Upload 图标
    → POST /api/v1/articles { content, title, authors, format, status, ... }
    → 拿到 server_article_id → save_draft(server_article_id, server_commit_hash)
    → Upload 图标消失 → 进入已同步状态

冲突检测:
  server_article_id 存在 && git_history[0].hash !== server_commit_hash
    → ArticleCard + ArticlePage 显示 GitCompare 图标

冲突解决:
  点击 GitCompare → DiffView(远程=server_commit_hash, 本地=HEAD)
    → "Keep Local"
      → PUT /api/v1/articles/{server_article_id} { content, title, ... }
      → save_draft(server_commit_hash=HEAD.hash)
      → GitCompare 图标消失
    → "Use Remote"
      → git_rollback(server_commit_hash)
      → save_draft(server_commit_hash = server_commit_hash)  // 不变
      → GitCompare 图标消失，文章重新渲染为远程内容
```

### 涉及的模块

```
frontend/src-tauri/src/db.rs              ← 加 migration
frontend/src-tauri/src/local_store.rs     ← Draft 结构体加字段
frontend/src-tauri/src/commands.rs        ← set_server_article_id 命令
frontend/src/composables/useArticleSync.ts ← 新增：sync 状态机
frontend/src/components/ArticleCard.vue    ← 状态图标
frontend/src/pages/ArticlePage.vue         ← 冲突图标 + Diff View 面板
frontend/src/pages/EditorPage.vue          ← Upload 入口
frontend/src/composables/useBookmarkToggle.ts ← 离线提示
frontend/src/pages/UserPage.vue            ← follow 离线提示
backend/tests/test_spec_article_sync.py    ← 新增 E2E
```

### 状态机

```
                    ┌──────────────────────┐
                    │    offline: 隐藏图标   │
                    └──────────────────────┘
                              ↑
                          !isOnline
                              ↑
  ┌──────────┐   Upload    ┌──────────┐   本地编辑    ┌─────────────┐
  │ 首次上传  │ ──成功──→  │  已同步   │ ──────────→  │    冲突      │
  │ Upload   │            │  (无图标)  │              │ GitCompare   │
  │   图标    │            └──────────┘              └──────┬──────┘
  └──────────┘                                            │
                                              ┌───────────┴───────────┐
                                              │    点击 GitCompare      │
                                              │    Diff View 打开       │
                                              └───────────┬───────────┘
                                                          │
                                        ┌─────────────────┴─────────────────┐
                                        │                                   │
                                   Keep Local                          Use Remote
                                   PUT /articles/{id}                  git_rollback
                                        │                                   │
                                        └─────────────────┬─────────────────┘
                                                          │
                                                    图标消失（已同步）
```

---

## 3. 前置条件

### 环境

- Python 3.12+（后端）
- Node.js 18+（前端）
- Rust（Tauri）
- 后端 `.venv` 已安装依赖
- 前端 `npm install` 已完成
- 后端运行在 `http://localhost:8080`

### 启动后端

```bash
cd backend
source .venv/bin/activate
python seed.py                              # 如果 peerpedia.db 不存在
uvicorn peerpedia_api.main:app --port 8080 --reload
```

### 启动 Tauri

```bash
cd frontend
npm run tauri dev
```

### 阅读参考

- `docs/DESIGN.en.md` — 架构文档
- `docs/api-contract.json` — API 规范
- `docs/implementation-plan-user-sync-2026-06-10.md` — L1-L3 实现（参考模式）

---

## 4. 任务 T1：Rust — drafts 表加 sync 列

**优先级:** P0 | **文件:** `frontend/src-tauri/src/db.rs`, `frontend/src-tauri/src/local_store.rs`

### 4.1 添加 migration

**文件:** `frontend/src-tauri/src/db.rs`

找到 `run_migrations` 函数，在 drafts 表创建语句中添加两列：

```rust
// drafts 表现在大概是这样（找到实际定义）:
// CREATE TABLE IF NOT EXISTS drafts (
//   id TEXT PRIMARY KEY,
//   account_id TEXT NOT NULL,
//   title TEXT NOT NULL DEFAULT '',
//   content TEXT NOT NULL DEFAULT '',
//   format TEXT NOT NULL DEFAULT 'markdown',
//   updated_at TEXT NOT NULL DEFAULT (datetime('now')),
//   FOREIGN KEY (account_id) REFERENCES local_accounts(id)
// )

// 改为：
// CREATE TABLE IF NOT EXISTS drafts (
//   ...
//   server_article_id TEXT,              -- 新增：服务器上对应的文章 ID
//   server_commit_hash TEXT,             -- 新增：上次同步时的 commit hash
//   ...
// )
```

具体做法：在 `run_migrations` 函数末尾，CREATE TABLE 之后，加 ALTER TABLE 语句（用 IF NOT EXISTS 包装或 try-catch，因为 SQLite 不支持 `ALTER TABLE ADD COLUMN IF NOT EXISTS`，但 `execute` 失败会返回错误，可以忽略或先查询列是否存在）。

**推荐方案**（幂等，可多次运行）：

```rust
// 在 run_migrations 末尾，CREATE TABLE 之后添加：
// 尝试加列，如果已存在则忽略错误
let _ = conn.execute("ALTER TABLE drafts ADD COLUMN server_article_id TEXT", []);
let _ = conn.execute("ALTER TABLE drafts ADD COLUMN server_commit_hash TEXT", []);
```

这两个 `let _ =` 会忽略"列已存在"错误。

### 4.2 更新 Draft 结构体

**文件:** `frontend/src-tauri/src/local_store.rs`

找到 `Draft` 结构体（约第 15-22 行）：

```rust
// 改前:
pub struct Draft {
    pub id: String,
    pub account_id: String,
    pub title: String,
    pub content: String,
    pub format: String,
    pub updated_at: String,
}

// 改为:
pub struct Draft {
    pub id: String,
    pub account_id: String,
    pub title: String,
    pub content: String,
    pub format: String,
    pub updated_at: String,
    pub server_article_id: Option<String>,   // 新增
    pub server_commit_hash: Option<String>,  // 新增
}
```

### 4.3 更新 get_draft 函数

找到 `get_draft` 函数（约第 126 行），SQL 查询加上新列：

```rust
// 改前:
"SELECT id, account_id, title, content, format, updated_at FROM drafts WHERE id = ?1"

// 改为:
"SELECT id, account_id, title, content, format, updated_at, server_article_id, server_commit_hash FROM drafts WHERE id = ?1"
```

更新 row 闭包，加上第 6、7 个字段的读取：

```rust
|row| {
    Ok(Draft {
        id: row.get(0)?,
        account_id: row.get(1)?,
        title: row.get(2)?,
        content: row.get(3)?,
        format: row.get(4)?,
        updated_at: row.get(5)?,
        server_article_id: row.get(6)?,   // 新增
        server_commit_hash: row.get(7)?,  // 新增
    })
}
```

### 4.4 更新 save_draft 函数

找到 `save_draft` 函数（约第 60 行）。需要：
1. 函数签名加两个参数
2. INSERT/UPDATE 加上新列

```rust
// 改前:
pub fn save_draft(
    conn: &Connection,
    id: Option<&str>,
    account_id: &str,
    title: &str,
    content: &str,
    format: &str,
) -> Result<Draft, AppError> {

// 改为:
pub fn save_draft(
    conn: &Connection,
    id: Option<&str>,
    account_id: &str,
    title: &str,
    content: &str,
    format: &str,
    server_article_id: Option<&str>,   // 新增
    server_commit_hash: Option<&str>,  // 新增
) -> Result<Draft, AppError> {
```

INSERT 语句：

```sql
-- 改前:
INSERT INTO drafts (id, account_id, title, content, format, updated_at)
VALUES (?1, ?2, ?3, ?4, ?5, datetime('now'))

-- 改为:
INSERT INTO drafts (id, account_id, title, content, format, updated_at, server_article_id, server_commit_hash)
VALUES (?1, ?2, ?3, ?4, ?5, datetime('now'), ?6, ?7)
```

ON CONFLICT UPDATE 同样加上。

### 4.5 更新所有 save_draft 调用点

`save_draft` 签名变了，所有调用方需要加两个 `None` 参数。在 `commands.rs` 的 `save_draft` 命令中：

```rust
// 改前（约 commands.rs:120）:
local_store::save_draft(&conn, params.id.as_deref(), &account_id, &params.title, &params.content, &params.format)

// 改为:
local_store::save_draft(
    &conn,
    params.id.as_deref(),
    &account_id,
    &params.title,
    &params.content,
    &params.format,
    None,  // server_article_id — 前端暂不传
    None,  // server_commit_hash — 前端暂不传
)
```

### 4.6 更新 Rust 单元测试

**文件:** `frontend/src-tauri/src/local_store.rs`（测试在文件末尾 `#[cfg(test)] mod tests`）

所有调用 `save_draft` 的地方加两个 `None`：

```rust
// 改前:
save_draft(&conn, None, "acc1", "My Draft", "# Hello", "markdown")

// 改为:
save_draft(&conn, None, "acc1", "My Draft", "# Hello", "markdown", None, None)
```

新增一个测试验证新字段：

```rust
#[test]
fn test_draft_server_sync_fields() {
    let conn = setup();
    let draft = save_draft(
        &conn, None, "acc1", "Test", "content", "markdown",
        Some("server-article-123"), Some("abc123def"),
    ).unwrap();
    assert_eq!(draft.server_article_id.as_deref(), Some("server-article-123"));
    assert_eq!(draft.server_commit_hash.as_deref(), Some("abc123def"));

    // 读回确认
    let reloaded = get_draft(&conn, &draft.id).unwrap();
    assert_eq!(reloaded.server_article_id, draft.server_article_id);
    assert_eq!(reloaded.server_commit_hash, draft.server_commit_hash);
}
```

### 4.7 验证

```bash
cd frontend/src-tauri
cargo test
```

预期：所有 Rust 测试通过，含新增的 `test_draft_server_sync_fields`。

---

## 5. 任务 T2：Rust — set_server_article_id 命令

**优先级:** P0 | **文件:** `frontend/src-tauri/src/commands.rs`, `frontend/src-tauri/src/main.rs`

### 5.1 添加 IPC 命令

**文件:** `frontend/src-tauri/src/commands.rs`

在文件末尾添加新的参数结构和命令函数：

```rust
// ── Article sync command ────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct SetServerArticleIdParams {
    pub draft_id: String,
    pub server_article_id: String,
    pub server_commit_hash: String,
    pub token: Option<String>,
    #[serde(default)]
    pub account_id: String,
}

#[tauri::command]
pub fn set_server_article_id(
    state: State<'_, AppState>,
    params: SetServerArticleIdParams,
) -> Result<OkResponse, AppError> {
    // Resolve account
    let account_id = if let Some(ref token) = params.token {
        resolve_account(&state, token)?
    } else if !params.account_id.is_empty() {
        params.account_id.clone()
    } else {
        return Err(AppError::AuthFailed("Authentication required".into()));
    };

    let conn = lock_db(&state)?;
    // Read existing draft
    let mut draft = local_store::get_draft(&conn, &params.draft_id)?;
    if draft.account_id != account_id {
        return Err(AppError::AuthFailed("Draft belongs to another account".into()));
    }

    // Update sync fields
    draft.server_article_id = Some(params.server_article_id);
    draft.server_commit_hash = Some(params.server_commit_hash);

    // save_draft now has the two new params — pass the sync values
    local_store::save_draft(
        &conn,
        Some(&draft.id),
        &draft.account_id,
        &draft.title,
        &draft.content,
        &draft.format,
        draft.server_article_id.as_deref(),
        draft.server_commit_hash.as_deref(),
    )?;

    Ok(OkResponse { ok: true })
}
```

### 5.2 注册命令

**文件:** `frontend/src-tauri/src/main.rs`

在 `invoke_handler!` 宏中添加：

```rust
commands::set_server_article_id,
```

### 5.3 验证

```bash
cd frontend/src-tauri
cargo test && cargo build
```

---

## 6. 任务 T3：TypeScript — useArticleSync composable

**优先级:** P0 | **文件:** 新建 `frontend/src/composables/useArticleSync.ts`

### 6.1 创建 composable

```typescript
// frontend/src/composables/useArticleSync.ts
import { ref, computed } from 'vue'
import { useUserStore } from '../stores/useUserStore'
import { useTauri } from './useTauri'
import { useNetworkStatus } from './useNetworkStatus'
import { createArticle, updateArticle, getArticle } from '../api/articles'
import { getArticleSource } from '../api/articles'
import { extractErrorMessage } from './useLocalStorage'
import type { Draft } from './useTauriTypes'

export type SyncState = 'upload' | 'synced' | 'conflict' | 'offline' | 'loading'

/**
 * Article sync state machine.
 *
 * @param draftId — local draft ID (article UUID)
 * @param serverArticleId — ref to server article ID (may be populated later)
 * @param serverCommitHash — ref to last-synced server commit hash
 * @param localHeadHash — ref to current local git HEAD hash
 */
export function useArticleSync(
  draftId: string,
  serverArticleId: () => string | null | undefined,
  serverCommitHash: () => string | null | undefined,
  localHeadHash: () => string | null,
) {
  const userStore = useUserStore()
  const tauri = useTauri()
  const { isOnline } = useNetworkStatus()

  const error = ref<string | null>(null)
  const pushing = ref(false)

  const syncState = computed<SyncState>(() => {
    if (!isOnline.value) return 'offline'
    if (pushing.value) return 'loading'
    const sid = serverArticleId()
    const sch = serverCommitHash()
    const lh = localHeadHash()
    if (!sid) return 'upload'
    if (!lh || !sch) return 'synced'  // can't compare, assume synced
    if (lh !== sch) return 'conflict'
    return 'synced'
  })

  /** First upload: POST to create server article */
  async function upload(): Promise<boolean> {
    if (!userStore.token?.value) {
      error.value = '请先登录服务器'
      return false
    }
    if (!draftId) {
      error.value = '没有可上传的文章'
      return false
    }

    pushing.value = true
    error.value = null

    try {
      // 1. Get local content from git HEAD
      const draft = await tauri.getDraft({ id: draftId })
      if (!draft || 'error' in draft) {
        error.value = '无法读取本地草稿'
        return false
      }
      const d = draft as Draft

      // 2. Get git HEAD content
      const history = await tauri.gitHistory({ article_id: draftId })
      if (!history || 'error' in history) {
        error.value = '无法读取 git 历史'
        return false
      }
      const headHash = Array.isArray(history) && history.length > 0 ? history[0].hash : null
      if (!headHash) {
        error.value = '文章没有任何提交'
        return false
      }

      const contentResult = await tauri.gitShow({ article_id: draftId, commit_hash: headHash })
      if (!contentResult || 'error' in contentResult) {
        error.value = '无法读取文章内容'
        return false
      }

      // 3. POST to server
      const viewer = userStore.viewer
      const result = await createArticle({
        title: d.title || 'Untitled',
        content: contentResult as string,
        format: d.format || 'markdown',
        authors: viewer ? [viewer.name || viewer.username] : ['Anonymous'],
        keywords: [],
        categories: [],
        abstract: '',
        commit_message: 'Initial upload from PeerPedia Desktop',
        self_review: { originality: 3, rigor: 3, completeness: 3, pedagogy: 3, impact: 3 },
      })

      const serverId = result?.id
      if (!serverId) {
        error.value = '服务器返回异常'
        return false
      }

      // 4. Store mapping
      await tauri.invoke('set_server_article_id', {
        draftId: draftId,
        serverArticleId: serverId,
        serverCommitHash: headHash,
        token: userStore.localToken?.value || undefined,
        accountId: userStore.viewer?.id || '',
      } as Record<string, unknown>)

      return true
    } catch (e: any) {
      error.value = extractErrorMessage(e) || '上传失败'
      return false
    } finally {
      pushing.value = false
    }
  }

  /** Push local changes to server (Keep Local) */
  async function pushUpdate(): Promise<boolean> {
    const sid = serverArticleId()
    if (!sid || !userStore.token?.value) {
      error.value = '无法更新：缺少服务器文章 ID'
      return false
    }

    pushing.value = true
    error.value = null

    try {
      const draft = await tauri.getDraft({ id: draftId })
      if (!draft || 'error' in draft) throw new Error('无法读取本地草稿')

      const history = await tauri.gitHistory({ article_id: draftId })
      if (!history || 'error' in history) throw new Error('无法读取 git 历史')
      const headHash = Array.isArray(history) && history.length > 0 ? history[0].hash : null
      if (!headHash) throw new Error('文章没有任何提交')

      const contentResult = await tauri.gitShow({ article_id: draftId, commit_hash: headHash })
      if (!contentResult || 'error' in contentResult) throw new Error('无法读取文章内容')

      const d = draft as Draft
      await updateArticle(sid, {
        title: d.title,
        content: contentResult as string,
        format: d.format,
      })

      // Update local sync hash
      await tauri.invoke('set_server_article_id', {
        draftId: draftId,
        serverArticleId: sid,
        serverCommitHash: headHash,
        token: userStore.localToken?.value || undefined,
        accountId: userStore.viewer?.id || '',
      } as Record<string, unknown>)

      return true
    } catch (e: any) {
      error.value = extractErrorMessage(e) || '更新失败'
      return false
    } finally {
      pushing.value = false
    }
  }

  /** Use remote version: rollback local git to server commit */
  async function useRemote(remoteCommitHash: string): Promise<boolean> {
    pushing.value = true
    error.value = null

    try {
      await tauri.gitRollback({
        article_id: draftId,
        commit_hash: remoteCommitHash,
        author: userStore.viewer?.name || 'PeerPedia',
      })

      // Update sync hash (now matches remote)
      const sid = serverArticleId()
      await tauri.invoke('set_server_article_id', {
        draftId: draftId,
        serverArticleId: sid || '',
        serverCommitHash: remoteCommitHash,
        token: userStore.localToken?.value || undefined,
        accountId: userStore.viewer?.id || '',
      } as Record<string, unknown>)

      return true
    } catch (e: any) {
      error.value = extractErrorMessage(e) || '回滚失败'
      return false
    } finally {
      pushing.value = false
    }
  }

  /** Get content at a specific commit for diff view */
  async function getContentAtCommit(hash: string): Promise<string | null> {
    const result = await tauri.gitShow({ article_id: draftId, commit_hash: hash })
    if (!result || 'error' in result) return null
    return result as string
  }

  function clearError() {
    error.value = null
  }

  return {
    syncState,
    error,
    pushing,
    upload,
    pushUpdate,
    useRemote,
    getContentAtCommit,
    clearError,
  }
}
```

### 6.2 注意

`tauri.invoke` 在 `useTauri` 中已经存在但未暴露通用的 `invoke`。需要检查 `useTauri.ts` 是否可以直接调用。如果不行，需要在 `useTauri.ts` 中导出一个通用 `invoke`：

```typescript
// 在 useTauri() 的 return 中添加：
async function invoke<T>(command: string, args?: Record<string, unknown>) {
  return _invoke<T>(command, args)
}
```

或者直接在 composable 中使用 `window.__TAURI__.core.invoke`（不推荐，测试困难）。

**如果 `_invoke` 是模块级函数不能直接暴露**，可以在 `commands.rs` 中复用现有 `save_draft` 命令来更新 sync 字段——在 `SaveDraftParams` 中加 `server_article_id` 和 `server_commit_hash` 字段。

---

## 7. 任务 T4：ArticleCard — 状态图标

**优先级:** P1 | **文件:** `frontend/src/components/ArticleCard.vue`

### 7.1 添加 props

ArticleCard 需要知道 sync 状态。组件本身不负责检测——接收 props：

```typescript
// 在 <script setup> 中添加：
import { Upload, GitCompare } from 'lucide-vue-next'

const props = defineProps<{
  // ... 现有 props
  syncState?: 'upload' | 'synced' | 'conflict' | 'offline'  // 新增
  serverCommitHash?: string | null  // 新增：用于 Diff View
}>()

const emit = defineEmits<{
  // ... 现有 emits
  (e: 'sync-upload', articleId: string): void
  (e: 'sync-resolve', articleId: string): void
}>()
```

### 7.2 添加图标模板

在 ArticleCard 模板中，标题右侧操作图标区域，添加：

```html
<!-- 状态图标 -->
<button
  v-if="syncState === 'upload'"
  class="sync-icon-btn"
  :title="'上传到服务器'"
  @click.stop="emit('sync-upload', article.id)"
>
  <Upload :size="16" stroke-width="2" class="text-accent" />
</button>
<button
  v-if="syncState === 'conflict'"
  class="sync-icon-btn"
  :title="'与服务器版本冲突，点击解决'"
  @click.stop="emit('sync-resolve', article.id)"
>
  <GitCompare :size="16" stroke-width="2" class="text-warning" />
</button>
```

### 7.3 CSS

```css
.sync-icon-btn {
  display: flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border: none; border-radius: 6px;
  background: transparent; cursor: pointer;
  transition: background-color 150ms ease;
}
.sync-icon-btn:hover {
  background-color: rgba(123, 140, 158, 0.15);
}
.text-warning { color: #9e6a03; }
```

---

## 8. 任务 T5：ArticlePage — 冲突图标 + Diff View 面板

**优先级:** P1 | **文件:** `frontend/src/pages/ArticlePage.vue`

### 8.1 添加冲突检测

在 `ArticlePage.vue` 的 `<script setup>` 中：

```typescript
import { useArticleSync } from '../composables/useArticleSync'
import DiffView from '../components/DiffView.vue'
import { GitCompare, Check, X } from 'lucide-vue-next'

// 获取 draft ID（article page 路由参数或 query）
const articleId = computed(() => route.params.id as string)

// 获取 sync 元数据
const draft = ref<Draft | null>(null)
const serverArticleId = () => draft.value?.server_article_id
const serverCommitHash = () => draft.value?.server_commit_hash
const localHeadHash = () => currentHeadHash.value

const currentHeadHash = ref<string | null>(null)
const { syncState, pushing, upload, pushUpdate, useRemote, getContentAtCommit, clearError } =
  useArticleSync(articleId.value, serverArticleId, serverCommitHash, localHeadHash)

// 加载 draft sync 元数据
async function loadSyncMeta() {
  const result = await tauri.getDraft({ id: articleId.value })
  if (result && !('error' in result)) draft.value = result as Draft
  const history = await tauri.gitHistory({ article_id: articleId.value })
  if (history && !('error' in history) && Array.isArray(history) && history.length > 0) {
    currentHeadHash.value = history[0].hash
  }
}
onMounted(() => { loadSyncMeta() })

// Diff View state
const showDiff = ref(false)
const remoteContent = ref('')
const localContent = ref('')
const diffError = ref<string | null>(null)

async function openDiffView() {
  const sch = serverCommitHash()
  const lh = localHeadHash()
  if (!sch || !lh) { diffError.value = '无法加载对比'; return }
  const [remote, local] = await Promise.all([
    getContentAtCommit(sch),
    getContentAtCommit(lh),
  ])
  if (remote === null || local === null) { diffError.value = '无法读取版本内容'; return }
  remoteContent.value = remote
  localContent.value = local
  showDiff.value = true
}

async function handleKeepLocal() {
  const ok = await pushUpdate()
  if (ok) { showDiff.value = false; await loadSyncMeta() }
}

async function handleUseRemote() {
  const sch = serverCommitHash()
  if (!sch) return
  const ok = await useRemote(sch)
  if (ok) {
    showDiff.value = false
    await loadSyncMeta()
    // 重新渲染文章内容为远程版本
    // 这会触发 ArticlePage 重新 loadArticle()
  }
}
```

### 8.2 模板

在标题旁添加冲突图标：

```html
<button
  v-if="syncState === 'conflict'"
  class="sync-icon-btn"
  title="与服务器版本冲突，点击解决"
  @click="openDiffView"
>
  <GitCompare :size="18" stroke-width="2" class="text-warning" />
</button>
```

Diff View 面板（在文章内容区域上方或全屏 overlay）：

```html
<Teleport to="body">
  <div v-if="showDiff" class="diff-overlay">
    <div class="diff-panel">
      <div class="diff-header">
        <h3>版本对比</h3>
        <span class="text-xs text-ink-muted">远程版本 vs 本地版本</span>
        <button class="sync-close-btn" @click="showDiff = false">
          <X :size="18" stroke-width="2" />
        </button>
      </div>
      <div v-if="diffError" class="diff-error">
        {{ diffError }}
        <button @click="diffError = null">关闭</button>
      </div>
      <DiffView
        v-else
        :article-id="articleId"
        :hash1="serverCommitHash()!"
        :hash2="localHeadHash()!"
      />
      <div class="diff-actions">
        <button
          class="btn-primary"
          :disabled="pushing"
          @click="handleKeepLocal"
        >
          <Check v-if="!pushing" :size="16" stroke-width="2" />
          <Loader v-else :size="16" stroke-width="2" class="animate-spin" />
          Keep Local
        </button>
        <button
          class="btn-secondary"
          :disabled="pushing"
          @click="handleUseRemote"
        >
          <X :size="16" stroke-width="2" />
          Use Remote
        </button>
      </div>
    </div>
  </div>
</Teleport>
```

### 8.3 CSS

```css
.diff-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0, 0, 0, 0.8);
  display: flex; align-items: center; justify-content: center;
}
.diff-panel {
  width: 90vw; max-width: 1200px; max-height: 90vh;
  background: #0d1117; border: 1px solid #30363d; border-radius: 12px;
  display: flex; flex-direction: column; overflow: hidden;
}
.diff-header {
  display: flex; align-items: center; gap: 12px;
  padding: 16px 20px; border-bottom: 1px solid #30363d;
}
.diff-header h3 { flex: 1; margin: 0; font-size: 16px; }
.sync-close-btn {
  background: none; border: none; color: #8b949e; cursor: pointer;
}
.diff-error {
  padding: 16px; color: #f85149;
}
.diff-actions {
  display: flex; gap: 12px; padding: 16px 20px;
  border-top: 1px solid #30363d; justify-content: flex-end;
}
.btn-primary {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 16px; border: none; border-radius: 6px;
  background: #7b8c9e; color: #0d1117; font-weight: 600;
  cursor: pointer; font-size: 13px;
}
.btn-primary:hover { filter: brightness(1.15); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 16px; border: 1px solid #30363d; border-radius: 6px;
  background: #21262d; color: #e6edf3; font-size: 13px;
  cursor: pointer;
}
.btn-secondary:hover { background: #30363d; }
```

**特别注意:** 需要 import `Loader` 和 `X`、`Check` 从 lucide-vue-next（如果还没 import）。

---

## 9. 任务 T6：EditorPage — Upload 入口

**优先级:** P1 | **文件:** `frontend/src/pages/EditorPage.vue`

### 9.1 添加 Upload 按钮

在 EditorPage 的工具栏区域（Save / Download 按钮附近），添加条件渲染的 Upload 按钮：

```html
<button
  v-if="syncState === 'upload'"
  class="toolbar-btn"
  :disabled="pushing"
  title="上传到服务器"
  @click="handleUpload"
>
  <Loader v-if="pushing" :size="18" stroke-width="2" class="animate-spin" />
  <Upload v-else :size="18" stroke-width="2" />
</button>
```

`syncState` 和 `pushing` 来自 `useArticleSync` composable（与 ArticlePage 同样的用法）。EditorPage 需要知道当前 draft 的 `server_article_id`。

### 9.2 Script 逻辑

```typescript
import { useArticleSync } from '../composables/useArticleSync'
import { Upload, Loader, GitCompare } from 'lucide-vue-next'

// ... 在 setup 中
const { syncState, pushing, upload, pushUpdate, clearError } =
  useArticleSync(draftId.value, serverArticleId, serverCommitHash, localHeadHash)

async function handleUpload() {
  const ok = await upload()
  if (ok) {
    // 刷新 draft 元数据
    await loadDraftMeta()
  }
}
```

EditorPage 已有 `draftId`（来自 `useDraftPersistence` 或路由参数）。需要从 draft 中读取 `server_article_id` 和 `server_commit_hash`。

---

## 10. 任务 T7：书签/关注离线提示

**优先级:** P1 | **文件:** `frontend/src/composables/useBookmarkToggle.ts`, `frontend/src/pages/UserPage.vue`

### 10.1 useBookmarkToggle — 离线路径修复

**文件:** `frontend/src/composables/useBookmarkToggle.ts`

当前代码中 `isLocal` 为 true 时调用 `tauri.addBookmark()` / `tauri.removeBookmark()` —— 这些 Rust 命令不存在，静默失败。

改为：离线时回滚 optimistic update 并提示用户。

```typescript
// 在 toggle() 函数的 try 块之前，添加离线检查：
if (isLocal) {
  // 离线模式：书签需要服务器连接
  article.is_bookmarked = previous  // 回滚乐观更新
  if (onError) {
    onError('书签功能需要服务器连接')
  }
  return
}
```

`isLocal` 的判断保持不变：`(userStore.isTauriMode || userStore.isBrowserLocal) && !isOnline.value`。

### 10.2 Bookmark 按钮 UI

书签图标按钮上添加 title 属性：

```html
<button
  :title="isOnline ? 'Bookmark' : '需要服务器连接'"
  :class="{ 'opacity-40 cursor-not-allowed': !isOnline }"
  @click="toggle"
>
  <BookmarkIcon />
</button>
```

### 10.3 UserPage — follow 同理

**文件:** `frontend/src/pages/UserPage.vue`

`handleFollow` 函数中，离线时提示用户而非调用不存在的 IPC：

```typescript
// 在 handleFollow() 开头添加：
if ((userStore.isTauriMode || userStore.isBrowserLocal) && !isOnline.value) {
  showError('关注功能需要服务器连接')
  return
}
```

---

## 11. 任务 T8：后端 E2E 测试

**优先级:** P1 | **文件:** 新建 `backend/tests/test_spec_article_sync.py`

### 11.1 测试文件

```python
"""SPEC-SYNC: Article sync E2E specification tests.

These tests define the expected product behavior for L4 article sync.
They are locked specifications — implementation must conform.
"""
import pytest
from fastapi.testclient import TestClient
from peerpedia_api.main import app

client = TestClient(app)

# ── Helpers ──────────────────────────────────────────────────────

def register_and_login(username: str = "sync_test_user", password: str = "test123"):
    """Register a new user and return (token, user)."""
    resp = client.post("/api/v1/auth/register", json={
        "username": username,
        "password": password,
        "email": f"{username}@test.com",
        "name": "Sync Test User",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["token"], data["user"]

def create_article(token: str, title: str = "Test Article", content: str = "# Hello"):
    """Create an article on the server."""
    resp = client.post("/api/v1/articles", json={
        "title": title,
        "content": content,
        "format": "markdown",
        "authors": ["Sync Test User"],
        "keywords": [],
        "categories": [],
        "abstract": "",
        "commit_message": "Initial",
        "self_review": {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestSpecSyncUpload:
    """SPEC-SYNC-1: First upload"""

    def test_first_upload_creates_article(self):
        """User uploads a local article → server creates it → returns ID."""
        token, user = register_and_login("upload_test")
        article = create_article(token, "My First Upload")
        assert "id" in article
        assert article["title"] == "My First Upload"
        assert article["status"] == "draft"

    def test_uploaded_article_appears_in_list(self):
        """After upload, article appears in GET /articles."""
        token, _ = register_and_login("list_test")
        create_article(token, "Listable Article")
        resp = client.get("/api/v1/articles", params={"author_id": _["id"]})
        assert resp.status_code == 200
        articles = resp.json().get("articles", resp.json())
        titles = [a["title"] for a in articles]
        assert "Listable Article" in titles

    def test_upload_requires_auth(self):
        """Upload without token → 401 or 422."""
        resp = client.post("/api/v1/articles", json={
            "title": "No Auth",
            "content": "# No",
            "format": "markdown",
            "authors": ["Anon"],
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
        })
        assert resp.status_code in (401, 422)


class TestSpecSyncUpdate:
    """SPEC-SYNC-3/4: Update (Keep Local / Use Remote)"""

    def test_update_article_content(self):
        """PUT /articles/{id} updates content and title."""
        token, _ = register_and_login("update_test")
        article = create_article(token, "Original Title", "# Original")
        aid = article["id"]

        resp = client.put(f"/api/v1/articles/{aid}", json={
            "title": "Updated Title",
            "content": "# Updated Content",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["title"] == "Updated Title"

    def test_update_preserves_id(self):
        """Update doesn't change the article ID."""
        token, _ = register_and_login("id_test")
        article = create_article(token, "ID Test")
        aid = article["id"]

        resp = client.put(f"/api/v1/articles/{aid}", json={
            "title": "Still ID Test",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.json()["id"] == aid

    def test_update_rejects_wrong_user(self):
        """User B cannot update User A's article."""
        token_a, _ = register_and_login("author_a", "pass_a")
        article = create_article(token_a, "A's Article")

        token_b, _ = register_and_login("author_b", "pass_b")
        resp = client.put(f"/api/v1/articles/{article['id']}", json={
            "title": "Hacked",
        }, headers={"Authorization": f"Bearer {token_b}"})
        assert resp.status_code in (403, 401)


class TestSpecSyncConflict:
    """SPEC-SYNC-2: Conflict detection (server side receives different version)"""

    def test_article_source_endpoint(self):
        """GET /articles/{id}/source returns raw content for diff comparison."""
        token, _ = register_and_login("source_test")
        article = create_article(token, "Source Test", "# Remote Content")
        aid = article["id"]

        resp = client.get(f"/api/v1/articles/{aid}/source")
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "# Remote Content"
        assert data["format"] == "markdown"
```

### 11.2 运行

```bash
cd backend
.venv/bin/python -m pytest backend/tests/test_spec_article_sync.py -v
```

预期：7 个测试全部通过。

---

## 12. 任务 T9：前端 vitest 测试

**优先级:** P1 | **文件:** 新建 `frontend/src/composables/__tests__/useArticleSync.test.ts`

### 12.1 useArticleSync 测试

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { useArticleSync } from '../useArticleSync'

// Mock dependencies
vi.mock('../../stores/useUserStore', () => ({
  useUserStore: () => ({
    viewer: { id: 'u1', name: 'Test', username: 'test' },
    token: ref('test-token'),
    localToken: ref('local-token'),
    isTauriMode: false,
    isBrowserLocal: false,
    trySyncServerAuth: vi.fn(),
    syncError: ref(null),
  }),
}))

vi.mock('../useTauri', () => ({
  useTauri: () => ({
    getDraft: vi.fn().mockResolvedValue({ id: 'd1', title: 'Test', content: '# Test', format: 'markdown' }),
    gitHistory: vi.fn().mockResolvedValue([{ hash: 'abc123' }]),
    gitShow: vi.fn().mockResolvedValue('# Content'),
    gitRollback: vi.fn().mockResolvedValue({ hash: 'def456' }),
    invoke: vi.fn().mockResolvedValue({ ok: true }),
  }),
}))

vi.mock('../useNetworkStatus', () => ({
  useNetworkStatus: () => ({ isOnline: ref(true) }),
}))

vi.mock('../../api/articles', () => ({
  createArticle: vi.fn().mockResolvedValue({ id: 'server-1' }),
  updateArticle: vi.fn().mockResolvedValue({ id: 'server-1' }),
  getArticle: vi.fn().mockResolvedValue({}),
  getArticleSource: vi.fn().mockResolvedValue({ content: '# Remote', format: 'markdown' }),
}))

describe('useArticleSync', () => {
  it('SPEC-SYNC-1: syncState is "upload" when no serverArticleId', () => {
    const { syncState } = useArticleSync('d1', () => null, () => null, () => 'abc123')
    expect(syncState.value).toBe('upload')
  })

  it('SPEC-SYNC-2: syncState is "conflict" when hashes differ', () => {
    const { syncState } = useArticleSync('d1', () => 's1', () => 'old123', () => 'new456')
    expect(syncState.value).toBe('conflict')
  })

  it('SPEC-SYNC-5: syncState is "synced" when hashes match', () => {
    const { syncState } = useArticleSync('d1', () => 's1', () => 'abc123', () => 'abc123')
    expect(syncState.value).toBe('synced')
  })

  it('SPEC-SYNC-6: syncState is "offline" when not online', async () => {
    const { useNetworkStatus } = await import('../useNetworkStatus')
    ;(useNetworkStatus as any)().isOnline = ref(false)
    const { syncState } = useArticleSync('d1', () => 's1', () => 'old', () => 'new')
    expect(syncState.value).toBe('offline')
  })

  it('upload returns true on success', async () => {
    const { upload } = useArticleSync('d1', () => null, () => null, () => 'abc123')
    const result = await upload()
    expect(result).toBe(true)
  })

  it('pushUpdate returns true on success', async () => {
    const { pushUpdate } = useArticleSync('d1', () => 's1', () => 'old', () => 'new')
    const result = await pushUpdate()
    expect(result).toBe(true)
  })
})
```

### 12.2 运行

```bash
cd frontend
npx vitest run src/composables/__tests__/useArticleSync.test.ts
```

预期：6 个测试全部通过。

---

## 13. 全局验证

### 运行全部测试

```bash
# 1. Rust 测试
cd frontend/src-tauri && cargo test

# 2. 前端测试
cd frontend && npx vitest run

# 3. 后端测试
cd backend && .venv/bin/python -m pytest backend/tests/ core/tests/ -q

# 4. TypeScript 类型检查
cd frontend && npx vue-tsc --noEmit
```

**通过标准:**
- Rust: 全部测试通过（含 `test_draft_server_sync_fields`）
- 前端: 492+ 测试通过（486 已有 + 6 新）
- 后端: 243+ 测试通过（236 已有 + 7 新）
- 类型检查: 0 errors

---

## 14. 手动端到端测试

### 测试场景 1：首次上传

```
1. 确保后端运行在 8080
2. 启动 Tauri (npm run tauri dev)
3. 登录本地账号
4. 创建新文章，写内容，保存
5. 在 EditorPage 工具栏看到 Upload 图标
6. 点击 Upload → 图标消失
7. curl http://localhost:8080/api/v1/articles | grep "你的标题"
   预期：文章出现在服务器上
```

### 测试场景 2：编辑后冲突

```
1. 上传文章后，继续编辑并保存（本地有新 commit）
2. ArticleCard 和 ArticlePage 显示 GitCompare 图标
3. 点击 GitCompare → Diff View 打开
4. 确认左侧为远程版本，右侧为本地版本
5. 点击 "Keep Local"
6. 图标消失，服务器文章已更新
```

### 测试场景 3：使用远程版本

```
1. 上传文章后编辑本地 → 冲突图标出现
2. 点击 GitCompare → Diff View
3. 点击 "Use Remote"
4. 文章渲染更新为远程版本内容，图标消失
```

---

## 15. NOT in Scope

| 内容 | 原因 |
|------|------|
| Pull（从服务器拉文章到本地） | Phase 1 单设备，无此需求 |
| 自动冲突合并（3-way merge） | 用户手动选择方向 |
| 书签/关注离线存储 | server-first，无离线浏览场景 |
| 后台自动同步 | 用户主动操作模型 |
| 多设备间文章同步 | Phase 2+ |

---

*最后更新: 2026-06-11 · 审查: ENG + DESIGN CLEARED · 9 个任务（T1-T9）· 7 个 xspec · 13 个新测试*
