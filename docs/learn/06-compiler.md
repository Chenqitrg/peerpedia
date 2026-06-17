# Compiler 模块

> 编译管线。Typst 和 Markdown 源码 → HTML/SVG/PDF。

## 一句话职责

**把作者写的源码变成读者能看的渲染结果。** 支持两种格式：Typst（学术排版）和 Markdown（通用写作）。

## C3: Compiler 组件依赖

```
   ┌──────────────┐
   │   caller     │  ← backend route 或 Tauri IPC
   │  调 compile()│
   └──────┬───────┘
          │ 依赖
          ▼
   ┌─────────────────────┐
   │  detect_format()    │  ← 根据扩展名 .typ → typst, .md → markdown
   └─────────┬───────────┘
             │ 依赖
             ▼
   ┌─────────────────────┐
   │extract_frontmatter()│  ← 解析 YAML 元数据
   └─────────┬───────────┘
             │ 依赖
             ▼
   ┌─────────────────────┐
   │  CompilerBackend    │  ← 抽象基类，两个实现
   └─────────┬───────────┘
             │
      ┌──────┴──────┐
      ▼             ▼
   ┌──────┐    ┌──────────────┐
   │Typst │    │  Markdown    │
   │Back- │    │  Backend     │
   │end   │    │              │
   │      │    │1.protect_math│  ← 顺序不可颠倒！
   │subpr-│    │2.render_md() │
   │ocess │    │3.restore_math│
   │typst │    │4.嵌入 KaTeX  │
   └──┬───┘    └──────┬───────┘
      │               │
      └───────┬───────┘
              │ 返回
              ▼
   ┌─────────────────┐
   │  CompileResult  │  ← 统一返回：success, format, output_path, html, error
   └─────────────────┘
```

箭头约定：`A ──► B` = A 依赖 B（A 调 B）。自上而下是调用顺序。

- **四个阶段是单向链**：detect → extract → compile → result
- **两个后端互不依赖**：Typst 走子进程，Markdown 走 Python 库
- **Markdown 的三步顺序不可颠倒**：protect → render → restore（lessons-learned #6）

## 架构

```
源文件 (.typ 或 .md)
    ↓
detect_format()          ← 根据扩展名判断格式
    ↓
extract_frontmatter()    ← 解析 YAML 元数据（标题、摘要、关键词）
    ↓
CompilerBackend.compile()
    ├── TypstBackend     → subprocess typst compile → PDF/SVG/PNG
    └── MarkdownBackend  → Python markdown + KaTeX → HTML
    ↓
CompileResult(success, format, output_path, html_content, error)
```

## Typst 后端

### 编译流程

```python
TypstBackend.compile(source_path, output_dir, fmt="pdf")
    → 查找 typst CLI（shutil.which("typst")）
    → subprocess.run(["typst", "compile", "--format", fmt, source, output])
    → 30 秒超时
    → 解析 stderr 中的 warning
```

### 支持格式

| 格式 | 用途 | 输出 |
|------|------|------|
| pdf | 下载/归档 | .pdf 文件 |
| svg | 浏览器预览 | .svg 文件（内联 HTML） |
| png | 缩略图 | .png 文件 |

SVG 预览可以直接嵌入 HTML——Typst 编译的 SVG 是纯 XML，浏览器原生支持。

### 依赖

- **typst CLI** 必须安装在系统上（`brew install typst` 或从 GitHub 下载）
- 不在 PATH 中时返回错误，不会降级到其他方式

## Markdown 后端

### 编译流程（顺序不能错！）

```
1. _strip_frontmatter(source)
   → 移除 --- 包裹的 YAML 元数据
   → 返回 body 部分

2. _protect_math(body)
   → $$...$$ → PEERPEDIA_MATH_D0
   → $...$   → PEERPEDIA_MATH_I0
   → 用占位符替换，防止 Markdown 解析器破坏公式

3. _render_markdown(protected_body)
   → Python markdown 库（fenced_code + tables + codehilite）
   → 如果 markdown 库没装：降级为 <p> 包裹纯文本

4. _restore_math(html, placeholders)
   → PEERPEDIA_MATH_D0 → <span class="katex-display">$$...$$</span>
   → PEERPEDIA_MATH_I0 → <span class="katex-inline">$...$</span>

5. 嵌入 KaTeX 渲染脚本
   → renderMathInElement(article-content)
   → 分隔符：$$ 块级、$ 行内
```

### 顺序为什么重要

如果先跑 Markdown 再保护公式：

```
$x_i$ → Markdown 看到 _ → 转成 <em>i</em> → KaTeX 收到 $x<em>i</em>$ → 渲染失败
```

所以必须 **protect → render → restore**。这是 lessons-learned #6。

## Frontmatter 解析

手写的 YAML 子集解析器（不依赖 PyYAML）：

```yaml
---
title: My Article
abstract: 中文摘要
categories:
  - physics
  - math
keywords:
  - quantum
language: zh
---
```

支持中英文键名别名：
- `标题` → `title`
- `摘要` → `abstract`
- `中文摘要` → `abstract_zh`
- `分类` → `categories`
- `关键词` → `keywords`

## 编译触发时机

| 场景 | 触发方式 |
|------|----------|
| 编辑器实时预览 | `POST /api/v1/compile-preview` |
| 下载 PDF | `GET /api/v1/articles/{id}/download/pdf` |
| Tauri 本地编译 | `compile_typst` / `compile_typst_pdf` IPC |
| 文章首次发布 | 自动编译并缓存 `compiled_*` 字段 |

## 缓存策略

编译结果缓存在 `Article.compiled_*` 字段：

```python
# crud_article.py
update_article_compiled(session, article_id, format, output, pages)
```

缓存不是自动失效的——只有文章内容更新时才重新编译。**这是已知问题：** 如果 Typst CLI 升级导致输出格式变化，旧缓存不会自动刷新。

## 编译在两层

| 层 | 编译方式 | 限制 |
|----|----------|------|
| 服务器（core） | TypstBackend / MarkdownBackend | 需要 typst CLI |
| Tauri 桌面 | `compile_typst` IPC → subprocess typst | 需要本地安装 typst |

两层用同样的 typst CLI，但 Markdown 编译只在服务器端（Tauri 没有 Python markdown 库）。

## 已知问题

1. **Typst CLI 依赖是外部二进制**。没有 fallback，没有 bundling。用户必须自己安装。
2. **编译缓存不自动失效**。Typst 升级后旧缓存不会更新。
3. **Markdown 后端降级方案太简陋**。没有 markdown 库时只做纯文本包裹，公式、表格全部丢失。
4. **30 秒超时可能太短**。大型 Typst 文档（几百页）可能超时。
5. **增量编译没有实现**——issue #70。每次都是全量编译。

## 入口文件

| 想做什么 | 从哪里开始 |
|----------|-----------|
| 加编译格式 | `core/peerpedia_core/storage/compiler.py` 的 CompilerBackend |
| 改 Markdown 渲染 | `compiler.py` 的 MarkdownBackend.compile() |
| 改公式处理 | `compiler.py` 的 _protect_math / _restore_math |
| 改 Typst 编译 | `compiler.py` 的 TypstBackend.compile() |
