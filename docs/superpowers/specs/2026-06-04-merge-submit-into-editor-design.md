# Merge Submit Page into Editor — Design Spec

> 日期: 2026-06-04
> 状态: 已批准

## 1. Overview

将 `/submit`（文件上传提交）融合进 `/edit`（在线编辑器），提交页面变成编辑器的一个"上传"按钮。上传后文件内容立刻显示在 CodeMirror 编辑器中并触发实时编译预览。

## 2. Functional Changes

### 2.1 Upload button on editor page

- 编辑页格式选择器旁新增「📂 上传」按钮
- 点击触发 `<input type="file" accept=".typ,.md">` 文件选择
- 选文件后弹出 `confirm()` 警告："将替换编辑器现有内容，确定上传？"
- 确认后用 `FileReader` 读取文件 → `cm.setValue(content)` 替换编辑器内容
- 根据文件后缀自动切换格式：`.typ` → Typst，`.md` → Markdown
- `updatePreview()` 随 CodeMirror change 事件自动触发编译/预览
- 全程客户端，不产生网络请求

### 2.2 Remove submit page

- `GET /submit` → 302 重定向到 `/edit`
- 删除 `peerpedia/web/templates/submit.html`
- 所有模板导航栏移除「提交」链接

## 3. File Changes

| 文件 | 操作 |
|------|------|
| `peerpedia/web/templates/edit.html` | 加上传按钮 + FileReader 逻辑 |
| `peerpedia/web/routes/pages.py` | `/submit` 路由改为 302 → `/edit` |
| `peerpedia/web/templates/submit.html` | 删除 |
| `peerpedia/web/templates/index.html` | 导航栏移除「提交」 |
| `peerpedia/web/templates/article.html` | 导航栏移除「提交」 |
| `peerpedia/web/templates/review.html` | 导航栏移除「提交」 |
| `peerpedia/web/templates/user.html` | 导航栏移除「提交」 |
| `tests/test_web_pages.py` | 更新 submit 页面测试预期 |

## 4. Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | 上传替换而非追加 | 编辑器一次只写一篇文章 |
| 2 | confirm() 警告 | 防止误操作覆盖正在写的内容 |
| 3 | /submit 重定向而非 404 | 向后兼容书签和外部链接 |
| 4 | FileReader 客户端读取 | 无需网络请求，即时显示 |
