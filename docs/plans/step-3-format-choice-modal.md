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

