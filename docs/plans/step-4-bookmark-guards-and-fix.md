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


---

> 从 [implementation-plan-2026-06-10.md](../implementation-plan-2026-06-10.md) 拆分。**独立执行，不依赖其他 Step。**

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

