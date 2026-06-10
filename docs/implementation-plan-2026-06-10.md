# PeerPedia UI/UX Fixes — 实施计划

> 2026-06-10 · 7 issues + 1 bug · 40 executable specs · Step-by-step for human or AI

---

## 前情提要：为什么要做这些修改

PeerPedia 是一个学术出版平台（"学术界的 GitHub"），支持 Markdown 和 Typst 两种格式写作。在 Phase 1.5 打磨阶段，用户反馈和代码审查发现了以下问题：

### 问题 1：用户可以收藏自己的文章

收藏功能本意是让用户收藏**别人**的文章，就像 Twitter 的书签。但系统没有阻止用户收藏自己的文章——后端 API 不检查作者身份，前端按钮也不区分。更严重的是，**ArticlePage（文章详情页）的收藏按钮从未真正调用过 API**——`toggleBookmark()` 只改了本地状态，刷新后收藏就丢了。用户反映"收藏了也看不到"就是这个原因。

### 问题 2：格式可以在编辑中途切换

编辑器工具栏有一个 MD/Typst 切换按钮。用户写了一半 Markdown，突然切换到 Typst，编译器报错、下载格式错乱、草稿格式不一致——这个按钮的存在本身就制造了一整类状态漂移 bug。格式应该在创建文章时就确定。

### 问题 3-4：Typst 编译的 SVG 白底 + 固定尺寸

Typst 编译器生成的 SVG 自带白色背景（`<rect fill="white"/>`），和项目的暗色主题（`#0d1117` 背景）格格不入。同时 SVG 是固定像素尺寸，拖动编辑器的分栏分隔板时不会自适应。

### 问题 5：删除 UI 两处不一致

文章卡片（ArticleCard）和文章详情页（ArticlePage）各自实现了删除功能，但 UI 不同：卡片用纯图标 + `text-danger` token + "Confirm?" 前缀 + 红底确认按钮；详情页用文字按钮 + 硬编码 `#d73a49` + 无确认提示。两处还各自维护了一套删除逻辑（API 调用、状态管理），完全重复。

### 审查过程

本计划经过了 `/plan-eng-review`（两轮，含涟漪分析）、`/plan-design-review`（七轮设计审查）和 `/xspec`（可执行规格）三重审查，共做出 6 个架构决策、锁定 30 条规格。

---

## 目录

1. [前置准备](#1-前置准备)
2. [Step 1: 后端——自收藏拒绝](#2-step-1-后端自收藏拒绝)
3. [Step 2: 前端 SVG 工具 + CSS](#3-step-2-前端-svg-工具--css)
4. [Step 3: 格式选择弹窗 + 移除 toggle](#4-step-3-格式选择弹窗--移除-toggle)
5. [Step 4: 收藏守卫 + ArticlePage 收藏持久化修复](#5-step-4-收藏守卫--articlepage-收藏持久化修复)
6. [Step 5: DeleteButton 统一组件](#6-step-5-deletebutton-统一组件)
7. [Step 6: Tab 抽屉设计对齐](#7-step-6-tab-抽屉设计对齐)
8. [Step 7: 组件颜色硬编码清理](#8-step-7-组件颜色硬编码清理)
9. [Step 8: 最终验证](#9-step-8-最终验证)
10. [附录: 规格对照表](#10-附录-规格对照表)

---

## 1. 前置准备

```bash
cd /Users/chenqimeng/Projects/peerpedia
git status  # 应该 clean
git branch  # 应该在 main

# 确认后端测试通过
cd backend && python -m pytest -x -q
# 应该看到: 353 passed (或相近数字)

# 确认前端测试通过
cd ../frontend && npm test -- --run
# 应该看到: 425 passed (或相近数字)

# 回到项目根目录
cd ..
```

**记住当前测试数量：** `backend: ___ passed`, `frontend: ___ passed`。最终验证时对比。

---

## 2. Step 1: 后端——自收藏拒绝

**规格:** SPEC-1.1, SPEC-1.2, SPEC-1.6  
**文件:** `backend/peerpedia_api/routes/bookmarks.py`  
**测试:** `backend/tests/test_routes_pool_bookmarks.py`

### 2.1 修改 routes/bookmarks.py

定位 `backend/peerpedia_api/routes/bookmarks.py`。

#### 第 3 行附近，import 区域

**当前（第 3 行）：**
```python
from peerpedia_core.storage.db.crud_article import get_article, get_author_ids
```

如果 `get_author_ids` 还没有被导入，添加它。检查第 3 行是否已经包含 `get_author_ids`。如果没有，改为：
```python
from peerpedia_core.storage.db.crud_article import get_article, get_author_ids
```

#### bookmark() 函数（约第 32-39 行）

**当前代码：**
```python
@router.post("", status_code=201)
def bookmark(article_id: str, current_user: User = Depends(deps.require_user),
             db: Session = Depends(deps.get_db)):
    if get_article(db, article_id) is None:
        raise HTTPException(status_code=404, detail="Article not found")
    if not is_bookmarked(db, current_user.id, article_id):
        add_bookmark(db, current_user.id, article_id)
    return {"bookmarked": True}
```

**改为：**
```python
@router.post("", status_code=201)
def bookmark(article_id: str, current_user: User = Depends(deps.require_user),
             db: Session = Depends(deps.get_db)):
    if get_article(db, article_id) is None:
        raise HTTPException(status_code=404, detail="Article not found")
    author_ids = get_author_ids(db, article_id)
    if current_user.id in author_ids:
        raise HTTPException(status_code=400, detail="Cannot bookmark your own article")
    if not is_bookmarked(db, current_user.id, article_id):
        add_bookmark(db, current_user.id, article_id)
    return {"bookmarked": True}
```

#### unbookmark() 函数（约第 42-46 行）

**当前代码：**
```python
@router.delete("/{article_id}")
def unbookmark(article_id: str, current_user: User = Depends(deps.require_user),
               db: Session = Depends(deps.get_db)):
    remove_bookmark(db, current_user.id, article_id)
    return {"bookmarked": False}
```

**改为：**
```python
@router.delete("/{article_id}")
def unbookmark(article_id: str, current_user: User = Depends(deps.require_user),
               db: Session = Depends(deps.get_db)):
    author_ids = get_author_ids(db, article_id)
    if current_user.id in author_ids:
        raise HTTPException(status_code=400, detail="Cannot bookmark your own article")
    remove_bookmark(db, current_user.id, article_id)
    return {"bookmarked": False}
```

### 2.2 添加后端测试

定位 `backend/tests/test_routes_pool_bookmarks.py`，在 `TestBookmarks` 类末尾（约第 101 行之后）添加：

```python
    def test_self_bookmark_rejected(self, client, db_engine, auth_header):
        """SPEC-1.1: 用户不能收藏自己的文章"""
        s = get_session(db_engine)
        u = User(username="author1", password_hash="", name="作者", anonymous_name="a")
        s.add(u)
        s.commit()
        a = Article(status="published")
        s.add(a)
        s.commit()
        # 将 u 设为文章作者
        from peerpedia_core.storage.db.models import ArticleAuthor
        s.add(ArticleAuthor(article_id=a.id, author_id=u.id, position=0))
        s.commit()
        s.close()

        headers = auth_header(u.id)
        resp = client.post(f"/api/v1/bookmarks?article_id={a.id}", headers=headers)
        assert resp.status_code == 400
        assert "own article" in resp.json()["detail"].lower()

    def test_self_unbookmark_rejected(self, client, db_engine, auth_header):
        """SPEC-1.2: 用户不能取消收藏自己的文章（虽然是多余的，但保持 API 一致）"""
        s = get_session(db_engine)
        u = User(username="author2", password_hash="", name="作者2", anonymous_name="a")
        s.add(u)
        s.commit()
        a = Article(status="published")
        s.add(a)
        s.commit()
        from peerpedia_core.storage.db.models import ArticleAuthor
        s.add(ArticleAuthor(article_id=a.id, author_id=u.id, position=0))
        s.commit()
        s.close()

        headers = auth_header(u.id)
        resp = client.delete(f"/api/v1/bookmarks/{a.id}", headers=headers)
        assert resp.status_code == 400
```

### 2.3 验证 Step 1

```bash
cd backend
python -m pytest tests/test_routes_pool_bookmarks.py -x -q -v
# 预期: 所有测试通过，包括 2 个新测试
# 之前: ~4 个 test_bookmark 测试 → 现在: ~6 个
cd ..
```

---

## 3. Step 2: 前端 SVG 工具 + CSS

**规格:** SPEC-3.1, SPEC-3.2, SPEC-3.3  
**新建:** `frontend/src/utils/typst.ts`, `frontend/src/utils/__tests__/typst.test.ts`  
**修改:** `frontend/src/assets/main.css`, `frontend/src/pages/EditorPage.vue`, `frontend/src/pages/ArticlePage.vue`

### 3.1 创建 frontend/src/utils/typst.ts

新建文件 `frontend/src/utils/typst.ts`，完整内容：

```typescript
/**
 * Sanitize Typst-compiled SVG for dark-theme display.
 * - Strips white/opaque background <rect> elements that clash with dark theme
 * - The responsive sizing (width: 100%, height: auto) is handled by CSS
 */
export function sanitizeTypstSvg(svg: string): string {
  return svg
    // Remove full-width background rects (Typst's default page background)
    .replace(/<rect[^>]*width="100%"[^>]*\/>/gi, '')
    // Remove explicitly white-filled rects
    .replace(/<rect[^>]*fill=["'](?:white|#fff(?:fff)?)["'][^>]*\/>/gi, '')
}
```

### 3.2 创建测试文件 frontend/src/utils/__tests__/typst.test.ts

新建文件 `frontend/src/utils/__tests__/typst.test.ts`，完整内容：

```typescript
import { describe, it, expect } from 'vitest'
import { sanitizeTypstSvg } from '../typst'

describe('sanitizeTypstSvg', () => {
  it('strips white background rect with width="100%"', () => {
    const input = '<svg><rect width="100%" height="100%" fill="white"/><text>Hello</text></svg>'
    const output = sanitizeTypstSvg(input)
    expect(output).not.toContain('<rect')
    expect(output).toContain('<text>Hello</text>')
  })

  it('strips rect with fill="#ffffff"', () => {
    const input = '<svg><rect fill="#ffffff" width="100%"/><path d="M0,0"/></svg>'
    const output = sanitizeTypstSvg(input)
    expect(output).not.toContain('fill="#ffffff"')
    expect(output).toContain('<path')
  })

  it('preserves non-background SVG elements', () => {
    const input = '<svg><g><text>Title</text><path d="M0,0 L10,10"/><circle cx="5" cy="5" r="2"/></g></svg>'
    const output = sanitizeTypstSvg(input)
    expect(output).toContain('<text>Title</text>')
    expect(output).toContain('<path')
    expect(output).toContain('<circle')
  })

  it('returns unchanged SVG when no white rect exists', () => {
    const input = '<svg><text>Hello</text></svg>'
    expect(sanitizeTypstSvg(input)).toBe(input)
  })

  it('handles empty string', () => {
    expect(sanitizeTypstSvg('')).toBe('')
  })
})
```

### 3.3 添加 CSS

定位 `frontend/src/assets/main.css`，在文件末尾（约第 184 行之后）添加：

```css
/* Typst SVG preview — dark theme compatibility */
.typst-preview svg {
  background: transparent !important;
  width: 100% !important;
  height: auto !important;
}
```

### 3.4 在 EditorPage.vue 中使用 sanitizeTypstSvg

定位 `frontend/src/pages/EditorPage.vue`。

#### 3.4.1 添加 import（约第 17 行，其他 utils import 旁边）

在第 17 行 `import { parseMarkdown } from '../utils/markdown'` 下方添加：

```typescript
import { sanitizeTypstSvg } from '../utils/typst'
```

#### 3.4.2 修改 handleCompile()（约第 359-364 行）

**当前代码：**
```typescript
const result = await tauri.compileTypst({
  content: content.value,
  format: format.value,
})
if (result && typeof result === 'string') {
  compileResult.value = { type: 'svg', content: result }
```

**改为：**
```typescript
const result = await tauri.compileTypst({
  content: content.value,
  format: format.value,
})
if (result && typeof result === 'string') {
  compileResult.value = { type: 'svg', content: sanitizeTypstSvg(result) }
```

### 3.5 在 ArticlePage.vue 中使用 sanitizeTypstSvg

定位 `frontend/src/pages/ArticlePage.vue`。

#### 3.5.1 添加 import（约第 18 行）

在第 18 行 `import { renderMathInHtml } from '../utils/math'` 下方添加：

```typescript
import { sanitizeTypstSvg } from '../utils/typst'
```

#### 3.5.2 修改 loadCompiledContent() 中的三处 SVG 使用

**第一处（约第 296 行）—— Tauri 编译结果：**
```typescript
// 当前:
compiledHtml.value = `<div class="typst-preview">${result}</div>`
// 改为:
compiledHtml.value = `<div class="typst-preview">${sanitizeTypstSvg(result)}</div>`
```

**第二处（约第 309 行）—— 服务器编译结果：**
```typescript
// 当前:
compiledHtml.value = result.output  // SVG — skip renderMathInHtml
// 改为:
compiledHtml.value = sanitizeTypstSvg(result.output)
```

### 3.6 验证 Step 2

```bash
cd frontend
npm test -- --run utils/__tests__/typst.test.ts
# 预期: 5 passed
cd ..
```

---

## 4. Step 3: 格式选择弹窗 + 移除 toggle

**规格:** SPEC-2.1 到 SPEC-2.8  
**文件:** `frontend/src/components/NavBar.vue`, `frontend/src/pages/EditorPage.vue`  
**测试:** `frontend/src/pages/__tests__/EditorPage.test.ts`

### 4.1 修改 NavBar.vue — 添加格式选择弹窗

定位 `frontend/src/components/NavBar.vue`。

#### 4.1.1 添加 icon imports（约第 9-20 行）

在 import 语句中添加 `X` icon（如果还没有）:
```typescript
import {
  Bookmark,
  Waypoints,
  FilePlus,
  FileText,
  FileCode,
  Search,
  User,
  ChevronDown,
  Wifi,
  WifiOff,
  Landmark,
  Waves,
  X,
} from 'lucide-vue-next'
```

关键新增: `FileText`, `FileCode`, `X`。

#### 4.1.2 添加弹窗状态和逻辑（约第 63 行，newArticle() 函数附近）

将 `newArticle()` 函数改为：
```typescript
const showFormatModal = ref(false)

function newArticle() {
  close()
  showFormatModal.value = true
}

function chooseFormat(format: 'markdown' | 'typst') {
  showFormatModal.value = false
  router.push(`/edit?new=1&_t=${Date.now()}&format=${format}`)
}

function closeFormatModal() {
  showFormatModal.value = false
}

// Esc 键关闭
function onFormatModalKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    closeFormatModal()
  }
}
```

#### 4.1.3 在 template 中添加弹窗 HTML

在 `</nav>` 闭合标签之后（约第 335 行之后），添加：

```html
    <!-- Format picker modal -->
    <Teleport to="body">
        <div
          v-if="showFormatModal"
          class="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label="Choose article format"
          @click.self="closeFormatModal"
          @keydown="onFormatModalKeydown"
        >
          <div class="bg-card border border-divider rounded-xl max-w-sm w-full mx-4 p-6 animate-fade-in">
            <!-- Header -->
            <div class="flex items-start justify-between mb-5">
              <div>
                <h2 class="text-lg font-heading font-semibold text-ink">Choose Format</h2>
                <p class="text-sm text-ink-muted mt-0.5">Select the format for your new article</p>
              </div>
              <button
                class="flex items-center justify-center w-7 h-7 rounded-lg
                       text-ink-muted hover:text-ink hover:bg-[#21262d]
                       transition-colors duration-200 shrink-0 -mt-1 -mr-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent cursor-pointer"
                aria-label="Close"
                @click="closeFormatModal"
              >
                <X class="w-4 h-4" stroke-width="2" />
              </button>
            </div>

            <!-- Format cards -->
            <div class="grid grid-cols-2 gap-3">
              <!-- Markdown -->
              <button
                class="bg-[#0d1117] border border-divider rounded-lg p-4 cursor-pointer
                       hover:border-accent/50 hover:bg-[#21262d]
                       transition-colors duration-200 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent focus-visible:rounded-lg"
                role="button"
                tabindex="0"
                @click="chooseFormat('markdown')"
                @keydown.enter="chooseFormat('markdown')"
                @keydown.space.prevent="chooseFormat('markdown')"
              >
                <FileText class="w-5 h-5 text-accent mb-2" stroke-width="2" />
                <div class="font-semibold text-ink text-sm">Markdown</div>
                <div class="text-xs text-ink-muted mt-1 leading-relaxed">
                  Standard format with math support (KaTeX)
                </div>
              </button>

              <!-- Typst -->
              <button
                class="bg-[#0d1117] border border-divider rounded-lg p-4 cursor-pointer
                       hover:border-accent/50 hover:bg-[#21262d]
                       transition-colors duration-200 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent focus-visible:rounded-lg"
                role="button"
                tabindex="0"
                @click="chooseFormat('typst')"
                @keydown.enter="chooseFormat('typst')"
                @keydown.space.prevent="chooseFormat('typst')"
              >
                <FileCode class="w-5 h-5 text-accent mb-2" stroke-width="2" />
                <div class="font-semibold text-ink text-sm">Typst</div>
                <div class="text-xs text-ink-muted mt-1 leading-relaxed">
                  Academic typesetting with SVG output
                </div>
              </button>
            </div>
          </div>
    </Teleport>
```

### 4.2 修改 EditorPage.vue — 读取 route query format + 移除 toggle

定位 `frontend/src/pages/EditorPage.vue`。

#### 4.2.1 修改 format 初始化（第 52 行）

**当前：**
```typescript
const format = ref<'markdown' | 'typst'>('markdown')
```

**改为：**
```typescript
const format = ref<'markdown' | 'typst'>(
  (route.query.format as 'markdown' | 'typst') || 'markdown'
)
```

#### 4.2.2 删除 format toggle 按钮组（第 562-582 行）

删除以下 21 行：
```html
        <!-- Format toggle -->
        <div class="flex items-center bg-[#0d1117] border border-divider rounded-lg overflow-hidden ml-1">
          <button
            class="w-9 h-9 flex items-center justify-center text-xs font-mono transition-colors rounded-lg"
            :class="format === 'markdown'
              ? 'bg-accent text-[#0d1117] font-semibold'
              : 'text-ink-muted hover:text-ink'"
            @click="format = 'markdown'"
          >
            MD
          </button>
          <button
            class="w-9 h-9 flex items-center justify-center text-xs font-mono transition-colors rounded-lg"
            :class="format === 'typst'
              ? 'bg-accent text-[#0d1117] font-semibold'
              : 'text-ink-muted hover:text-ink'"
            @click="format = 'typst'"
          >
            Typst
          </button>
        </div>
```

### 4.3 修改 EditorPage 测试（修复回归）

定位 `frontend/src/pages/__tests__/EditorPage.test.ts`。

#### 4.3.1 替换 format toggle 测试（第 89-96 行）

**删除：**
```typescript
it('has format toggle between Markdown and Typst', async () => {
  const EditorPage = (await import('../EditorPage.vue')).default
  const wrapper = mount(EditorPage, {
    global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
  })
  await flushPromises()
  expect(wrapper.text()).toMatch(/markdown|typst/i)
})
```

**替换为：**
```typescript
it('uses format from route query param', async () => {
  const mockRoute = {
    params: {},
    query: { new: '1', format: 'typst' },
    path: '/edit',
    fullPath: '/edit?new=1&format=typst',
    name: 'editor',
    meta: {},
  }
  const EditorPage = (await import('../EditorPage.vue')).default
  const wrapper = mount(EditorPage, {
    global: {
      stubs: { 'router-link': RouterLinkStub, 'router-view': true },
      mocks: { $route: mockRoute },
    },
  })
  await flushPromises()
  // Typst mode → textarea visible (not CodeMirror)
  expect(wrapper.find('textarea').exists()).toBe(true)
})

it('has no format toggle buttons in toolbar', async () => {
  const EditorPage = (await import('../EditorPage.vue')).default
  const wrapper = mount(EditorPage, {
    global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
  })
  await flushPromises()
  // MD/Typst toggle buttons should not exist
  const buttons = wrapper.findAll('button')
  const mdBtn = buttons.filter(b => b.text() === 'MD')
  const typstBtn = buttons.filter(b => b.text() === 'Typst')
  expect(mdBtn.length).toBe(0)
  expect(typstBtn.length).toBe(0)
})
```

### 4.4 验证 Step 3

```bash
cd frontend
npm test -- --run pages/__tests__/EditorPage.test.ts
# 预期: 新增的 format 测试通过，旧的 toggle 测试已替换
cd ..
```

---

## 5. Step 4: 收藏守卫 + ArticlePage 收藏持久化修复

**规格:** SPEC-1.3, SPEC-1.4, SPEC-1.5, SPEC-1.7, SPEC-1.8  
**文件:** `frontend/src/composables/useBookmarkToggle.ts`, `frontend/src/pages/ArticlePage.vue`, `frontend/src/components/ArticleCard.vue`  
**测试:** `frontend/src/pages/__tests__/ArticlePage.test.ts`, `frontend/src/components/__tests__/ArticleCard.test.ts`

### 5.1 修改 useBookmarkToggle.ts — 添加自收藏守卫

定位 `frontend/src/composables/useBookmarkToggle.ts`。

在 `toggle()` 函数中，第 24 行 `if (!article) return` 之后，添加 guard：

```typescript
async function toggle(articleId: string, currentlyBookmarked: boolean) {
    if (!userStore.viewer) return
    const article = articles.value.find(a => a.id === articleId)
    if (!article) return

    // SPEC-1.5: 静默忽略自收藏（防止 API 调用）
    if (article.is_own_article) return

    const previous = article.is_bookmarked
    article.is_bookmarked = !currentlyBookmarked

    // ... 后续代码不变 ...
```

**精确插入位置：** 第 25 行（`if (!article) return` 之后），在第 26 行（`const previous = ...`）之前。

### 5.2 修改 ArticlePage.vue — 修复收藏持久化 + 隐藏自收藏按钮

定位 `frontend/src/pages/ArticlePage.vue`。

#### 5.2.1 添加 API import（约第 7 行）

在 `import { getArticle, getArticleSource, ... } from '../api/articles'` 之后添加：

```typescript
import { addBookmark, removeBookmark } from '../api/bookmarks'
```

#### 5.2.2 替换 toggleBookmark() 函数（第 342-346 行）

**删除当前：**
```typescript
function toggleBookmark() {
  if (article.value) {
    article.value.is_bookmarked = !article.value.is_bookmarked
  }
}
```

**替换为：**
```typescript
async function toggleBookmark() {
  if (!article.value || !userStore.viewer) return
  const wasBookmarked = article.value.is_bookmarked
  // 乐观更新
  article.value.is_bookmarked = !wasBookmarked
  try {
    if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
      if (wasBookmarked) {
        await tauri.removeBookmark({ user_id: userStore.viewer.id, article_id: article.value.id })
      } else {
        await tauri.addBookmark({ user_id: userStore.viewer.id, article_id: article.value.id })
      }
    } else {
      if (wasBookmarked) {
        await removeBookmark(article.value.id)
      } else {
        await addBookmark(article.value.id)
      }
    }
  } catch {
    // 失败时回滚
    article.value.is_bookmarked = wasBookmarked
  }
}
```

> 注意: 这里重用了已有的 `tauri` 变量（第 95 行 `const tauri = useTauri()`）。不需要额外引入。

#### 5.2.3 隐藏自收藏按钮（约第 502 行）

将 bookmark 按钮包裹在条件中。当前第 502-512 行：

```html
          <button
            class="flex items-center justify-center w-7 h-7 rounded
                   text-ink-muted hover:text-accent hover:bg-accent/10
                   transition-colors duration-200"
            :aria-label="isBookmarked ? t('card.removeBookmark') : t('card.addBookmark')"
            :data-tooltip="isBookmarked ? t('card.removeBookmark') : t('card.addBookmark')"
            @click="toggleBookmark"
          >
            <BookmarkCheck v-if="isBookmarked" class="w-4 h-4 text-accent" stroke-width="2" />
            <Bookmark v-else class="w-4 h-4" stroke-width="2" />
          </button>
```

在 `<button` 前面添加 `v-if="!isOwnArticle"`，整段变为：

```html
          <button
            v-if="!isOwnArticle"
            class="flex items-center justify-center w-7 h-7 rounded
                   text-ink-muted hover:text-accent hover:bg-accent/10
                   transition-colors duration-200"
            :aria-label="isBookmarked ? t('card.removeBookmark') : t('card.addBookmark')"
            :data-tooltip="isBookmarked ? t('card.removeBookmark') : t('card.addBookmark')"
            @click="toggleBookmark"
          >
            <BookmarkCheck v-if="isBookmarked" class="w-4 h-4 text-accent" stroke-width="2" />
            <Bookmark v-else class="w-4 h-4" stroke-width="2" />
          </button>
```

### 5.3 修改 ArticleCard.vue — 隐藏自收藏按钮

定位 `frontend/src/components/ArticleCard.vue`，第 191-201 行。

**当前 bookmark 按钮（没有条件）：**
```html
        <button
          class="flex items-center justify-center w-7 h-7 rounded ..."
          ...
          @click="handleBookmarkClick"
        >
```

在 `<button` 前面添加 `v-if="!article.is_own_article"`:

```html
        <button
          v-if="!article.is_own_article"
          class="flex items-center justify-center w-7 h-7 rounded ..."
          ...
          @click="handleBookmarkClick"
        >
```

### 5.4 验证 Step 4

```bash
cd frontend
npm test -- --run
# 预期: 所有测试通过，无回归
cd ..
```

---

## 6. Step 5: DeleteButton 统一组件

**规格:** SPEC-4.1 到 SPEC-4.8  
**新建:** `frontend/src/components/DeleteButton.vue`, `frontend/src/components/__tests__/DeleteButton.test.ts`  
**修改:** `frontend/src/components/ArticleCard.vue`, `frontend/src/pages/ArticlePage.vue`

### 6.1 创建 DeleteButton.vue

新建文件 `frontend/src/components/DeleteButton.vue`，完整内容：

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { Trash2 } from 'lucide-vue-next'
import { useTauri } from '../composables/useTauri'
import { deleteArticle } from '../api/articles'

const props = defineProps<{
  articleId: string
  authorId?: string
}>()

const emit = defineEmits<{
  deleted: [articleId: string]
}>()

const showConfirm = ref(false)
const deleting = ref(false)
const tauri = useTauri()

async function handleDelete() {
  if (deleting.value) return
  deleting.value = true
  try {
    if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
      const result = await tauri.deleteArticle({
        id: props.articleId,
        account_id: props.authorId || '',
      })
      if (result && 'error' in result) return
    } else {
      await deleteArticle(props.articleId)
    }
    emit('deleted', props.articleId)
    showConfirm.value = false
  } catch {
    // Silent failure — article remains visible, user can retry
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <!-- Trigger: trash icon only, danger color on hover -->
  <button
    v-if="!showConfirm"
    class="flex items-center justify-center w-7 h-7 rounded cursor-pointer
           text-ink-muted hover:text-danger hover:bg-danger/10
           transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
    aria-label="Delete article"
    data-tooltip="Delete"
    @click="showConfirm = true"
  >
    <Trash2 class="w-3.5 h-3.5" stroke-width="2" />
  </button>

  <!-- Confirmation: "Confirm?" + solid red Delete + Cancel -->
  <div v-else class="flex items-center gap-1">
    <span class="text-xs text-ink-muted">Confirm?</span>
    <button
      class="px-2 py-1 text-xs font-semibold bg-danger text-white rounded
             hover:brightness-110 transition-all cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      :disabled="deleting"
      @click="handleDelete"
    >
      {{ deleting ? '...' : 'Delete' }}
    </button>
    <button
      class="px-2 py-1 text-xs text-ink-muted hover:text-ink rounded
             hover:bg-[#21262d] transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      @click="showConfirm = false"
    >
      Cancel
    </button>
  </div>
</template>
```

### 6.2 修改 ArticleCard.vue — 用 DeleteButton 替换内联 delete

定位 `frontend/src/components/ArticleCard.vue`。

#### 6.2.1 添加 import（约第 14 行）

在其他 component import 附近添加：
```typescript
import DeleteButton from './DeleteButton.vue'
```

#### 6.2.2 清理不再需要的 imports 和 state

**删除这些行：**
- `import { forkArticle, deleteArticle } from '../api/articles'` 中的 `deleteArticle`（第 7 行）→ 改为 `import { forkArticle } from '../api/articles'`
- `const showDeleteConfirm = ref(false)`（第 27 行）
- `const deleting = ref(false)`（第 28 行）
- `const tauriDelete = useTauri()`（第 29 行）
- `async function handleDelete() { ... }`（第 31-51 行）— 整个函数删除

#### 6.2.3 替换 template 中的 delete UI（第 226-254 行）

**删除：**
```html
        <template v-if="article.is_own_article">
          <button
            v-if="!showDeleteConfirm"
            class="flex items-center justify-center w-7 h-7 rounded
                   text-ink-muted hover:text-danger hover:bg-danger/10
                   transition-colors duration-200"
            aria-label="Delete article"
            data-tooltip="Delete"
            @click="showDeleteConfirm = true"
          >
            <Trash2 class="w-3.5 h-3.5" stroke-width="2" />
          </button>
          <div v-else class="flex items-center gap-1">
            <span class="text-xs text-ink-muted">Confirm?</span>
            <button
              class="px-2 py-1 text-xs font-semibold bg-danger text-white rounded hover:brightness-110 transition-all cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              :disabled="deleting"
              @click="handleDelete"
            >
              {{ deleting ? '...' : 'Delete' }}
            </button>
            <button
              class="px-2 py-1 text-xs text-ink-muted hover:text-ink rounded hover:bg-[#21262d] transition-colors"
              @click="showDeleteConfirm = false"
            >
              Cancel
            </button>
          </div>
        </template>
```

**替换为：**
```html
        <DeleteButton
          v-if="article.is_own_article"
          :article-id="article.id"
          :author-id="article.authors?.[0]?.id"
          @deleted="(id: string) => $emit('deleted', id)"
        />
```

#### 6.2.4 清理不再需要的 icon import

如果 `Trash2` 不再被 ArticleCard 使用（确认 template 中没有其他 Trash2），从 import 中移除：
```typescript
// 从 lucide-vue-next import 中移除 Trash2
import {
  FileText,
  Users,
  GitCommitHorizontal,
  Bookmark,
  BookmarkCheck,
  History,
  Edit,
  GitFork,
  // Trash2,  ← 删除这行
} from 'lucide-vue-next'
```

> 但 `Trash2` 已经移到了 `DeleteButton.vue` 中，所以确保 ArticleCard 没有其他地方用它。

### 6.3 修改 ArticlePage.vue — 用 DeleteButton 替换内联 delete

定位 `frontend/src/pages/ArticlePage.vue`。

#### 6.3.1 添加 import（约第 18 行）

```typescript
import DeleteButton from '../components/DeleteButton.vue'
```

#### 6.3.2 清理不再需要的 imports 和 state

**修改第 6 行 import：**
```typescript
// 当前:
import { getArticle, getArticleSource, getHistory, forkArticle, extendSink, createMergeProposal, deleteArticle } from '../api/articles'
// 改为（移除 deleteArticle）:
import { getArticle, getArticleSource, getHistory, forkArticle, extendSink, createMergeProposal } from '../api/articles'
```

**第 31 行，移除 Trash2 import：**
```typescript
// 当前:
import {
  Bookmark,
  BookmarkCheck,
  History,
  Edit,
  GitFork,
  GitMerge,
  GitCommitHorizontal,
  Clock,
  MessageSquare,
  Eye,
  ArrowLeft,
  Trash2,
} from 'lucide-vue-next'
// 改为（移除 Trash2）:
import {
  Bookmark,
  BookmarkCheck,
  History,
  Edit,
  GitFork,
  GitMerge,
  GitCommitHorizontal,
  Clock,
  MessageSquare,
  Eye,
  ArrowLeft,
} from 'lucide-vue-next'
```

**删除这些 state/functions（约第 38, 67-89 行）：**
```typescript
const tauriDelete = useTauri()   // 第 38 行 — 删除
const showDeleteConfirm = ref(false)  // 第 67 行 — 删除
const deleting = ref(false)      // 第 68 行 — 删除
// 第 69-89 行 async function handleDeleteArticle() { ... } — 整个函数删除
```

#### 6.3.3 添加 handleDeleted() 函数

在删除 `handleDeleteArticle` 的位置（约第 89 行之后），添加：
```typescript
function handleDeleted() {
  router.push(`/user/${userStore.viewer?.id}`)
}
```

#### 6.3.4 替换 template 中的 delete UI（第 573-598 行）

**删除：**
```html
            <template v-if="isOwnArticle && !showDeleteConfirm">
              <button
                class="flex items-center gap-1 px-2.5 py-1 text-xs text-ink-muted hover:text-[#d73a49] hover:bg-[#d73a49]/10 rounded-md transition-colors"
                aria-label="Delete article"
                data-tooltip="Delete"
                @click="showDeleteConfirm = true"
              >
                <Trash2 class="w-3 h-3" stroke-width="2" />
              </button>
            </template>
            <template v-if="showDeleteConfirm">
              <button
                class="flex items-center gap-1 px-2.5 py-1 text-xs text-[#d73a49] hover:bg-[#d73a49]/10 rounded-md transition-colors font-semibold"
                :disabled="deleting"
                @click="handleDeleteArticle"
              >
                {{ deleting ? '...' : 'Delete' }}
              </button>
              <button
                class="flex items-center gap-1 px-2.5 py-1 text-xs text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-md transition-colors"
                :disabled="deleting"
                @click="showDeleteConfirm = false"
              >
                Cancel
              </button>
            </template>
```

**替换为：**
```html
            <DeleteButton
              v-if="isOwnArticle"
              :article-id="article?.id ?? ''"
              :author-id="article?.authors?.[0]?.id"
              @deleted="handleDeleted"
            />
```

### 6.4 创建 DeleteButton 测试

新建文件 `frontend/src/components/__tests__/DeleteButton.test.ts`：

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import DeleteButton from '../DeleteButton.vue'
import { useTauri } from '../../composables/useTauri'
import { deleteArticle } from '../../api/articles'

// Mock dependencies
vi.mock('../../composables/useTauri', () => ({
  useTauri: vi.fn(() => ({
    isTauri: { value: false },
    isBrowserLocal: { value: false },
    deleteArticle: vi.fn(),
  })),
}))

vi.mock('../../api/articles', () => ({
  deleteArticle: vi.fn(),
}))

describe('DeleteButton', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows trash icon by default, no confirm UI', () => {
    const wrapper = mount(DeleteButton, {
      props: { articleId: 'test-1' },
    })
    expect(wrapper.find('[aria-label="Delete article"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Confirm?')
    expect(wrapper.text()).not.toContain('Cancel')
  })

  it('shows confirm UI after clicking trash', async () => {
    const wrapper = mount(DeleteButton, {
      props: { articleId: 'test-1' },
    })
    await wrapper.find('[aria-label="Delete article"]').trigger('click')
    expect(wrapper.text()).toContain('Confirm?')
    expect(wrapper.text()).toContain('Delete')
    expect(wrapper.text()).toContain('Cancel')
  })

  it('Cancel hides confirm UI, trash returns', async () => {
    const wrapper = mount(DeleteButton, {
      props: { articleId: 'test-1' },
    })
    await wrapper.find('[aria-label="Delete article"]').trigger('click')
    await wrapper.find('button', )
    expect(wrapper.find('[aria-label="Delete article"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Confirm?')
  })

  it('emits deleted on successful delete', async () => {
    ;(deleteArticle as any).mockResolvedValueOnce({})
    const wrapper = mount(DeleteButton, {
      props: { articleId: 'test-1' },
    })
    await wrapper.find('[aria-label="Delete article"]').trigger('click')
    // Click Delete
    const deleteBtn = wrapper.findAll('button').find(b => b.text().includes('Delete'))
    await deleteBtn!.trigger('click')
    // Wait for async
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('deleted')).toBeTruthy()
    expect(wrapper.emitted('deleted')![0]).toEqual(['test-1'])
  })

  it('does not emit deleted on API failure, confirm still visible', async () => {
    ;(deleteArticle as any).mockRejectedValueOnce(new Error('fail'))
    const wrapper = mount(DeleteButton, {
      props: { articleId: 'test-1' },
    })
    await wrapper.find('[aria-label="Delete article"]').trigger('click')
    const deleteBtn = wrapper.findAll('button').find(b => b.text().includes('Delete'))
    await deleteBtn!.trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('deleted')).toBeFalsy()
  })
})
```

### 6.5 验证 Step 5

```bash
cd frontend
npm test -- --run components/__tests__/DeleteButton.test.ts
# 预期: 5 passed
cd ..
```

---

## 7. Step 6: Tab 抽屉设计对齐

**规格:** SPEC-6.1 到 SPEC-6.4  
**文件:** `frontend/src/components/TabDrawer.vue`

### 问题

TabDrawer 的 scoped CSS 全部硬编码颜色，且使用了与设计系统不一致的 `#58a6ff`（亮蓝）——项目 accent 是 `#7b8c9e`（灰蓝）。这个第三种强调色在整个应用中只出现在 Tab 抽屉里。

### 修改

所有改动在 `<style scoped>` 块内（约第 114-199 行）。

#### 模板：X 图标尺寸（第 105 行）

**当前：**
```html
<X :size="14" stroke-width="2" />
```

**改为：**
```html
<X :size="16" stroke-width="2" />
```

#### CSS：逐行替换

```
Line 132: background: #58a6ff        → background: #7b8c9e
Line 160: color: #8b949e             → color: #6e7681
Line 162: transition: ... 150ms ...  → transition: ... 200ms ...
Line 168: rgba(88, 166, 255, 0.12)   → rgba(123, 140, 158, 0.12)
Line 169: border-left-color: #58a6ff → border-left-color: #7b8c9e
Line 171: rgba(88, 166, 255, 0.18)   → rgba(123, 140, 158, 0.18)
Line 173: outline: 2px solid #58a6ff → outline: 2px solid #7b8c9e
Line 181: background-color: #58a6ff  → background-color: #7b8c9e
```

不动的值：`#30363d`（= divider）、`#0d1117`（= page bg）、`#21262d`（= hover bg）、`#e6edf3`（= text ink）——这些已经和设计系统一致。

### 状态颜色对齐 ArticleCard 标签

**当前问题：** `statusColor()` 函数自创了一套颜色，和 ArticleCard 的状态标签不一致。

| 状态 | TabDrawer 当前 | ArticleCard 标签 | 应该 |
|---|---|---|---|
| draft | `bg-accent`（灰蓝 #7b8c9e） | `badge-draft`（深灰） | 灰色 |
| published | `bg-success`（纯绿） | `badge-published`（success/20） | 绿色（保持） |
| sedimentation | `bg-yellow-500`（黄） | `badge-sedimentation`（neutral/20） | 灰蓝 |

**修改 `statusColor()` 函数（第 13-21 行）：**

```typescript
// 添加 import
import { getStatusInfo } from '../composables/useStatusMap'

// 替换 statusColor()
function statusColor(status: string, active: boolean): string {
  const base = active ? 'opacity-100' : 'opacity-70'
  const info = getStatusInfo(status)
  switch (info.class) {
    case 'badge-published':    return `bg-success ${base}`
    case 'badge-sedimentation': return `bg-neutral/60 ${base}`
    default:                    return `bg-ink-muted/40 ${base}`  // badge-draft
  }
}
```

### 展开列表添加状态指示点

在 `.tab-drawer-item` 内，icon 后面添加一个 8px 彩色圆点（第 97 行 `</component>` 之后）：

```html
<span
  class="w-2 h-2 rounded-full shrink-0"
  :class="statusColor(tab.status, tab.id === tabStore.activeTabId)"
  :title="tab.status"
/>
```

### 验证

```bash
# 视觉检查：
# - 所有蓝色消失 → 灰蓝 (#7b8c9e)
# - 文字颜色统一为 ink-muted
# - X 按钮 16px
# - 边条状态色：草稿=灰、已发表=绿、沉淀中=灰蓝（和卡片标签一致）
# - 展开列表中每个 tab 项旁边有一个彩色状态圆点
```

---

## 8. Step 7: 组件颜色硬编码清理

**规格:** SPEC-7.1 到 SPEC-7.4  
**文件:** `AuthModal.vue`, `ReviewModal.vue`, `NetworkStatusBadge.vue`, `NavBar.vue`, `Pagination.vue`, `tailwind.config.ts`

### 问题

多个组件在应该用 Tailwind token 的地方硬编码了 hex 颜色值，和设计系统 MASTER.md 的 "NEVER hardcode hex" 规则冲突。

### 7.1 AuthModal / ReviewModal — `text-[#d73a49]` → `text-danger`

`tailwind.config.ts` 已定义 `danger: '#d73a49'`，token 值为 `text-danger`。

**AuthModal.vue 第 133 行（login 表单 error）：**
```diff
- <p v-if="error" class="text-xs text-[#d73a49]">{{ error }}</p>
+ <p v-if="error" class="text-xs text-danger">{{ error }}</p>
```

**AuthModal.vue 第 173 行（register 表单 error）：**
```diff
- <p v-if="error" class="text-xs text-[#d73a49]">{{ error }}</p>
+ <p v-if="error" class="text-xs text-danger">{{ error }}</p>
```

**ReviewModal.vue 第 55 行：**
```diff
- <p v-if="error" class="text-xs text-[#d73a49] mt-4">{{ error }}</p>
+ <p v-if="error" class="text-xs text-danger mt-4">{{ error }}</p>
```

### 7.2 NetworkStatusBadge — scoped CSS → design tokens

**NetworkStatusBadge.vue `<style scoped>` 块：**

| 行 | 当前 | 改为 | 原因 |
|---|---|---|---|
| 32 | `color: #8b949e` | `color: #6e7681` | GitHub muted gray → 项目 ink-muted |
| 44 | `background: #3fb950` | `background: #5c7c6e` | GitHub green → 项目 success |
| 45 | `rgba(63, 185, 80, 0.4)` | `rgba(92, 124, 110, 0.4)` | 匹配新 success 色 |

### 7.3 `text-[#0d1117]` → `text-page`

`tailwind.config.ts` 已定义 `page: '#0d1117'`，所以 `text-page` 等价于 `text-[#0d1117]`。

| 文件 | 行 | 改动 |
|---|---|---|
| `NavBar.vue` | 297 | `text-[#0d1117]` → `text-page`（sign-in 按钮） |
| `Pagination.vue` | 34 | `text-[#0d1117]` → `text-page`（active page 按钮） |
| `AuthModal.vue` | 137, 177 | `text-[#0d1117]` → `text-page`（submit 按钮 ×2） |

### 7.4 border-divider token 修正

`tailwind.config.ts` 第 16 行：`divider: '#21262d'` → `divider: '#30363d'`。

`#21262d` 太暗，作为边框几乎看不见。`#30363d` 是 GitHub 暗色主题的实际边框色，在项目的 scoped CSS 中也一直作为 divider 使用。这是一行 config 改动，但会影响全局 ~98 处 `border-divider` 实例——边框会稍亮。需要目视回归确认。

### 7.5 其他组件同类清理

以下组件有与 7.1–7.4 相同的硬编码模式。

**`text-[#d73a49]` → `text-danger`（6 处）：**

| 文件 | 行 | 上下文 |
|---|---|---|
| `SelfReviewPanel.vue` | 49 | commit message 必填标记 |
| `SelfReviewPanel.vue` | 136 | 贡献比例警告 |
| `ReviewPanel.vue` | 90 | 评审提交错误 |
| `ReviewPanel.vue` | 173 | 回复错误 |
| `ReviewPanel.vue` | 190 | 回复错误（第二处） |
| `HistoryPage.vue` | 272 | 回滚警告条（同时含 border 和 bg） |

HistoryPage:272 整行替换：
```
border-[#d73a49] bg-[#d73a49]/5 text-[#d73a49]
→ border-danger bg-danger/5 text-danger
```

**`text-[#0d1117]` → `text-page`（3 处）：**

| 文件 | 行 |
|---|---|
| `ReviewPanel.vue` | 83（提交按钮） |
| `HistoryPage.vue` | 293（确认回滚） |
| `UserPage.vue` | 296（tab 切换） |

**`bg-[#161b22]` → `bg-card`（1 处）：**

| 文件 | 行 |
|---|---|
| `DiffView.vue` | 231（文件头背景） |

### 验证

```bash
# 启动应用后检查：
# - AuthModal 和 ReviewModal 的错误消息颜色应为 #d73a49（和之前一样，现在是 token）
# - NetworkStatusBadge 的绿点颜色从亮绿变为暗绿（#5c7c6e）
# - 所有 accent 按钮上的深色文字不变（text-page = #0d1117 和之前一样）
# - 所有卡片/面板的边框比之前略微明显（#30363d vs #21262d）
```

---

## 9. Step 8: 最终验证

### 9.1 运行全部测试

```bash
cd /Users/chenqimeng/Projects/peerpedia

# 后端
cd backend && python -m pytest -x -q
# 预期: 355+ passed (原始 ~353 + 2 新测试)

# 前端
cd ../frontend && npm test -- --run
# 预期: 440+ passed (原始 ~425 + 15 新测试)
# 注意: 如果原始是 425，替换 toggle 测试后 test 数量可能 +/-1

cd ..
```

### 9.2 手动验证清单

启动应用后，逐项检查：

- [ ] **自收藏**: 登录 → 打开自己的文章 → 收藏按钮不显示
- [ ] **收藏持久化**: 打开别人的文章 → 点收藏 → 刷新页面 → 收藏状态保持
- [ ] **收藏取消**: 取消收藏 → 刷新页面 → 收藏状态保持
- [ ] **新建文章弹窗**: 点"New Article" → 弹窗出现 → Markdown 和 Typst 卡片等权重
- [ ] **选 Markdown**: 点 Markdown 卡片 → 编辑器打开 CodeMirror
- [ ] **选 Typst**: 点 Typst 卡片 → 编辑器打开 textarea
- [ ] **弹窗关闭**: Esc / 点背景 / 点 X 三种方式都能关闭弹窗
- [ ] **Tab 键**: 弹窗内 Tab 在两张卡片和 X 按钮间循环 → 不逃逸到背景
- [ ] **无 toggle**: 编辑器工具栏没有 MD/Typst 切换按钮
- [ ] **Typst SVG**: 编译 Typst → 预览无白底 → 拖动分栏 SVG 宽度跟随
- [ ] **统一删除**: ArticleCard 和 ArticlePage 都有统一的 DeleteButton
- [ ] **删除确认**: 点垃圾桶 → "Confirm?" + 红色 Delete → 点 Cancel 恢复
- [ ] **删除执行**: 确认删除 → 文章被删除 → ArticlePage 跳转到用户页
- [ ] **Tab 抽屉**: 打开 Tab 抽屉 → 所有蓝色 (#58a6ff) 消失 → 激活态/脏标记/focus ring 为灰蓝 (#7b8c9e) → 文字颜色与全局 muted text 一致

---

## 10. 附录: 规格对照表

| 规格 | 描述 | 覆盖文件 |
|---|---|---|
| SPEC-1.1 | REST API 拒绝自收藏 (POST) | `routes/bookmarks.py`, `test_routes_pool_bookmarks.py` |
| SPEC-1.2 | REST API 拒绝自取消收藏 (DELETE) | `routes/bookmarks.py`, `test_routes_pool_bookmarks.py` |
| SPEC-1.3 | 详情页隐藏自收藏按钮 | `ArticlePage.vue` |
| SPEC-1.4 | 卡片隐藏自收藏按钮 | `ArticleCard.vue` |
| SPEC-1.5 | 编程守卫静默忽略自收藏 | `useBookmarkToggle.ts` |
| SPEC-1.6 | 其他用户仍可收藏 | `test_routes_pool_bookmarks.py` |
| SPEC-1.7 | ArticlePage 收藏持久化 (add) | `ArticlePage.vue` |
| SPEC-1.8 | ArticlePage 取消收藏持久化 (remove) | `ArticlePage.vue` |
| SPEC-2.1 | 弹窗两张等权卡片 | `NavBar.vue` |
| SPEC-2.2 | 选 Markdown → CodeMirror | `NavBar.vue`, `EditorPage.vue` |
| SPEC-2.3 | 选 Typst → textarea | `NavBar.vue`, `EditorPage.vue` |
| SPEC-2.4 | 工具栏无 toggle 按钮 | `EditorPage.vue` |
| SPEC-2.5 | 三种关闭路径 (Esc/背景/X) | `NavBar.vue` |
| SPEC-2.6 | 键盘导航 + focus trap | `NavBar.vue` |
| SPEC-2.7 | 已有文章格式保留 | `EditorPage.vue` (已有逻辑) |
| SPEC-2.8 | 草稿格式保留 | `useDraftPersistence.ts` (已有逻辑) |
| SPEC-3.1 | SVG 透明背景 | `typst.ts`, `main.css`, `EditorPage.vue`, `ArticlePage.vue` |
| SPEC-3.2 | SVG 响应式宽度 | `main.css` |
| SPEC-3.3 | Markdown 不受影响 | `main.css` (scoped) |
| SPEC-4.1 | 初始垃圾桶图标 | `DeleteButton.vue` |
| SPEC-4.2 | 点垃圾桶 → 确认 UI | `DeleteButton.vue` |
| SPEC-4.3 | Cancel → 恢复垃圾桶 | `DeleteButton.vue` |
| SPEC-4.4 | 确认 → API + emit | `DeleteButton.vue` |
| SPEC-4.5 | API 失败 → 静默恢复 | `DeleteButton.vue` |
| SPEC-4.6 | 非自文章无删除按钮 | `DeleteButton.vue` (父组件控制 v-if) |
| SPEC-4.7 | ArticleCard re-emit deleted | `ArticleCard.vue` |
| SPEC-4.8 | ArticlePage → router.push | `ArticlePage.vue` |
| SPEC-5.1 | 现存收藏不受影响 | 全量测试 |
| SPEC-5.2 | 编译输出不变 | 全量测试 |
| SPEC-5.3 | 非 Typst SVG 不受影响 | `main.css` (scoped) |
| SPEC-6.1 | Tab 抽屉 accent 色统一为 #7b8c9e | `TabDrawer.vue` |
| SPEC-6.2 | Tab 抽屉 muted text 统一为 #6e7681 | `TabDrawer.vue` |
| SPEC-6.3 | Tab focus ring 使用 accent 色 | `TabDrawer.vue` |
| SPEC-6.4 | Tab X 按钮 16px 对齐其他关闭按钮 | `TabDrawer.vue` |
| SPEC-6.5 | Tab 状态色对齐 ArticleCard 标签 | `TabDrawer.vue` |
| SPEC-6.6 | Tab 展开列表显示状态指示点 | `TabDrawer.vue` |
| SPEC-7.1 | AuthModal/ReviewModal 错误消息用 text-danger token | `AuthModal.vue`, `ReviewModal.vue` |
| SPEC-7.2 | NetworkStatusBadge 颜色对齐设计系统 | `NetworkStatusBadge.vue` |
| SPEC-7.3 | accent 按钮文字用 text-page token | `NavBar.vue`, `Pagination.vue`, `AuthModal.vue` |
| SPEC-7.4 | border-divider 为 #30363d | `tailwind.config.ts` |

---

## 变更文件总览

| 文件 | 操作 | Step |
|---|---|---|
| `backend/peerpedia_api/routes/bookmarks.py` | 修改 (+6行) | 1 |
| `backend/tests/test_routes_pool_bookmarks.py` | 修改 (+45行) | 1 |
| `frontend/src/utils/typst.ts` | **新建** | 2 |
| `frontend/src/utils/__tests__/typst.test.ts` | **新建** | 2 |
| `frontend/src/assets/main.css` | 修改 (+5行) | 2 |
| `frontend/src/pages/EditorPage.vue` | 修改 (-21行, +3行, 2处) | 2, 3 |
| `frontend/src/pages/ArticlePage.vue` | 修改 (-35行, +30行, 5处) | 2, 4, 5 |
| `frontend/src/components/NavBar.vue` | 修改 (+85行) | 3 |
| `frontend/src/pages/__tests__/EditorPage.test.ts` | 修改 (替换 2 测试) | 3 |
| `frontend/src/composables/useBookmarkToggle.ts` | 修改 (+1行) | 4 |
| `frontend/src/components/ArticleCard.vue` | 修改 (-42行, +5行, 3处) | 4, 5 |
| `frontend/src/components/DeleteButton.vue` | **新建** | 5 |
| `frontend/src/components/__tests__/DeleteButton.test.ts` | **新建** | 5 |
| `frontend/src/pages/__tests__/ArticlePage.test.ts` | 修改 (+2 测试) | 4 |
| `frontend/src/components/__tests__/ArticleCard.test.ts` | 修改 (+1 测试) | 4 |
| `frontend/src/components/TabDrawer.vue` | 修改 (9行) | 6 |
| `frontend/src/components/AuthModal.vue` | 修改 (4处) | 7 |
| `frontend/src/components/ReviewModal.vue` | 修改 (1处) | 7 |
| `frontend/src/components/NetworkStatusBadge.vue` | 修改 (3处) | 7 |
| `frontend/src/components/NavBar.vue` | 修改 (1处) | 7 |
| `frontend/src/components/Pagination.vue` | 修改 (1处) | 7 |
| `frontend/tailwind.config.ts` | 修改 (1行) | 7 |
| `frontend/src/components/SelfReviewPanel.vue` | 修改 (2处) | 7 |
| `frontend/src/components/ReviewPanel.vue` | 修改 (4处) | 7 |
| `frontend/src/pages/HistoryPage.vue` | 修改 (2处) | 7 |
| `frontend/src/pages/UserPage.vue` | 修改 (1处) | 7 |
| `frontend/src/components/DiffView.vue` | 修改 (1处) | 7 |

**新建:** 4 files · **修改:** 23 files · **净增代码:** ~120 行 · **净删代码:** ~100 行
