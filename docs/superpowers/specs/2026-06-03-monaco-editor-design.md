# Monaco 在线编辑器 — 设计文档

> 目标：让数学家在浏览器里流畅地写作和预览 Markdown/Typst 文章。

## 架构

```
┌──────────────────┬──────────────────────────┐
│   Monaco 编辑器   │     实时预览              │
│                  │                          │
│   (Markdown /    │   Markdown: KaTeX 即时    │
│    Typst 语法     │   Typst: WASM → SVG 即时  │
│    高亮)         │                          │
│                  │                          │
├──────────────────┴──────────────────────────┤
│  标题 / 摘要 / 分类 / 关键词 / 五维自评        │
├─────────────────────────────────────────────┤
│  [保存草稿]  [提交沉淀池]                      │
└─────────────────────────────────────────────┘
```

## 编译路径

| 格式 | 预览引擎 | 延迟 | 说明 |
|------|---------|------|------|
| Markdown | 浏览器 KaTeX | 即时 | Monaco 内容 → Markdown 解析 → KaTeX 渲染 HTML |
| Typst | 浏览器 WASM (`@myriaddreamin/typst.ts`) | 即时 | Monaco 内容 → typst.ts WASM 编译 → SVG 嵌入 DOM |

### Markdown 路径

```
Monaco onChange → 提取文本 → 前端 Markdown 解析 → KaTeX 渲染 → 右侧 HTML
```

完全在浏览器完成，无需服务端。复用 `compiler.py` 的 `_protect_math` / `_restore_math` 逻辑做前端版本。

### Typst 路径

```
Monaco onChange → 防抖 300ms → typst.ts WASM 编译 → SVG → 嵌入右侧 DOM
```

使用 `@myriaddreamin/typst.ts`（MIT 协议），CDN 加载 all-in-one bundle。
编译和渲染全在浏览器 Web Worker 中完成，不经过服务器。
typst.ts 基于 Typst v0.14.2，支持完整 Typst 语法 + 包管理。

## 路由

| 路由 | 说明 |
|------|------|
| `GET /edit` | 新建文章（空白编辑器） |
| `GET /edit/{article_id}` | 编辑已有文章（加载源码填充编辑器） |
| — | 预览 100% 客户端，无需服务端编译端点 |

## 技术选型

| 组件 | 方案 |
|------|------|
| 编辑器 | Monaco Editor（CDN 加载） |
| Markdown 渲染 | 前端 JS，复用 compiler.py protect/restore 逻辑 |
| KaTeX | 已有 CDN（`/static/katex/`） |
| Typst 编译 | `@myriaddreamin/typst.ts` WASM（CDN 加载 all-in-one bundle） |
| Typst 渲染 | typst.ts SVG 输出 → 嵌入 DOM |
| 防抖 | Markdown 即时 / Typst 300ms debounce |

## 元数据面板

编辑器下方折叠面板，字段对齐现有 `submit_article` 流程：

- 标题（必填）
- 摘要
- 中文摘要（可选）
- 分类（逗号分隔）
- 关键词（逗号分隔）
- 语言（en / zh）
- 五维自评（1-5 星，可选）

## 提交流程

1. 点击「提交沉淀池」→ 元数据 + 编辑器内容打包 POST `/api/v1/articles`
2. 复用现有 `submit_article` 流程：生成 UUID → git init → commit → DB → CID
3. 成功后跳转到文章页

## 不做的事

- 不新建编辑器专用的编译管线 — 复用现有 `compiler.py` 和 `api_compile.py`
- 不新建文章模型 — 复用现有 `Article` ORM
- 不改变现有文件上传提交方式 — 新编辑器是新增入口，不是替代
- 不做 bTeX/Instiki 适配 — 搁置
- 不做服务端 Typst 预览 — typst.ts WASM 覆盖了

## 文件结构

```
peerpedia/web/
├── routes/
│   └── pages.py            ← 添加 GET /edit, GET /edit/{id}
├── templates/
│   └── edit.html           ← 新建，Monaco 编辑器页面
└── static/
    └── monaco/             ← Monaco 静态资源（或 CDN）
```

全部客户端渲染，不需要新增服务端 API。

## 测试计划

- 编辑器加载：页面渲染 Monaco Editor 实例
- Markdown 预览：输入 `# Hello $x^2$` → 右侧渲染标题 + KaTeX
- Typst 预览：输入 `= Hello` → WASM 编译 → 右侧 SVG 显示
- 提交草稿：POST /api/v1/articles → 返回 article_id
- 编辑已有文章：GET /edit/{id} → Monaco 填充源码
