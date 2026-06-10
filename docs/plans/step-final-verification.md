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

## 最终验证

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

