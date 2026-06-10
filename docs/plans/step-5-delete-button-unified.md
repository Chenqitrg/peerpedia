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

