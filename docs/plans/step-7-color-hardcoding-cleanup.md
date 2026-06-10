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

