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

