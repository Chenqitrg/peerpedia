# 06 — Compilation Pipeline

> Markdown → HTML (client-side by default), Typst → SVG/PDF (sidecar/server). On-demand with filesystem cache.

## 1. Markdown Compilation (Client-Side)

**File:** `frontend/src/utils/markdown.ts`

### Pipeline

```
Raw Markdown string
  │
  ▼
Stage 1: protectMath(content)
  │  Replace $$...$$ and $...$ with unique placeholders
  │  Placeholder format: PEERPEDIA-MATH-D0, PEERPEDIA-MATH-D1, ...
  │  (Hyphens prevent GFM parser from misinterpreting underscores)
  │
  ▼
Stage 2: marked.parse(protected)
  │  Standard Markdown → HTML
  │  GFM tables, task lists, strikethrough enabled
  │
  ▼
Stage 3: restoreMath(html, mathBlocks)
  │  Replace placeholders back with original LaTeX
  │  Uses split/join instead of String.replace() because
  │  replace() interprets $$ in the replacement as literal $
  │
  ▼
Stage 4: renderMathInHtml(html)
  │  KaTeX.render() for each math block
  │  Display math: $$...$$ → displayMode=true
  │  Inline math: $...$ → displayMode=false
  │
  ▼
Final HTML string
```

### Why the pipeline order matters

If marked parses math as Markdown, it corrupts LaTeX:
- `$x^2$` → `$x<sup>2</sup>$` (superscript misinterpreted)
- `$$...$$` → `_..._` interpreted as emphasis

Protecting math BEFORE Markdown parsing, then restoring AFTER, prevents this.

### Performance

| Document Size | Compile Time |
|--------------|-------------|
| 1 page, no math | ~5ms |
| 1 page, heavy math (50+ equations) | ~50ms |
| 50 pages, heavy math | ~500ms |

All client-side, no server round-trip for Markdown.

## 2. Typst Compilation (Sidecar/Server)

### Tauri Mode

```
Typst source
  → Tauri IPC: invoke('compile_typst', { content })
  → Rust: write temp file, spawn `typst compile`
  → Read output SVG
  → Return to frontend
```

### Web Mode

```
Typst source
  → POST /api/v1/compile-preview { content, format: 'typst' }
  → Python: write temp file, subprocess `typst compile`
  → Read output SVG
  → Return in response
```

### PDF Download

Same flow but `--format pdf`, returns binary. Download filename includes 7-char commit hash: `Title-a1b2c3d.pdf`.

## 3. Filesystem Cache

```
~/.peerpedia/cache/{article_id}/{commit_hash}.{html|svg|pdf}
```

- Cache key = commit_hash. Same content always produces same output.
- Cache miss → compile → write cache
- Cache hit → return cached file (~1ms)
- Clean cache: `rm -rf ~/.peerpedia/cache/`
- Compiler upgrade: delete cache, next request recompiles

**Cache is never the source of truth.** Git is always the authority. Cache is a pure performance optimization.

## 4. Compile Endpoint (Server)

```
POST /api/v1/compile-preview
  Body: { content: string, format: 'markdown' | 'typst', commit_hash?: string }
  Response: { html?: string, svg?: string, pages?: number }

Flow:
  1. Check cache: /cache/{article_id}/{hash}.{format}
  2. Cache hit → return cached
  3. Cache miss:
     a. Markdown: Python marked + KaTeX (server-side for PDF generation)
     b. Typst: subprocess typst compile
  4. Write cache
  5. Return result
```

## 5. Format Support Matrix

| Format | Tauri Desktop | Web |
|--------|-------------|-----|
| Markdown → HTML | Client-side (marked + KaTeX) | Client-side (marked + KaTeX) |
| Markdown → PDF | NOT SUPPORTED | Server-side via /compile-preview |
| Typst → SVG | Tauri sidecar CLI | Server-side via /compile-preview |
| Typst → PDF | Tauri sidecar CLI | Server-side via /compile-preview |

**Gap:** Markdown → PDF has no client-side path. Tauri users cannot download Markdown articles as PDF. The /compile-download API handles this on the server but requires network.

## 6. DownloadButton States

```
Idle (after save):
  [FileDown] HTML  [FileCode] Source  [Package] PDF (Typst only)
  Click → 800ms cooldown → disabled → FileCheck → re-enabled

Before first save:
  All buttons disabled (opacity-30, cursor-not-allowed)
  Tooltip: "Save before downloading"
```

**Filenames:** `Title-a1b2c3d.html` (7-char commit hash embedded). Source: `.typ` or `.md` extension. Compiled: `.html` or `.pdf`.

## 7. Design Issues

### I16: No Markdown → PDF on desktop

Tauri users writing Markdown cannot export to PDF without a server connection. The server-side compile endpoint is the only path for PDF. A Tauri sidecar for Pandoc or a headless Chrome print would close this gap.

### I17: Typst compilation blocks UI

Both Tauri (synchronous IPC) and server (synchronous subprocess) block during Typst compilation. For large documents, the UI freezes with no progress bar. Should be async with streaming progress.

### I18: Cache never expires

Files in `~/.peerpedia/cache/` persist forever. No LRU eviction, no size limit, no TTL. A user who edits heavily could accumulate GBs of stale cache files. The only cleanup mechanism is manual deletion.

### I19: Math protection is regex-based

The `protectMath` function uses regex to find `$$...$$` and `$...$` blocks. Edge cases with nested dollar signs, code blocks containing `$`, or escaped dollars (`\$`) may produce incorrect protection. No test suite for edge case math strings.
