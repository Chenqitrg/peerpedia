# M5 Citation Jump — 设计规格

> 日期: 2026-06-03
> 状态: 已批准
> 范围: 引用扫描 + 引用图 + 点击跳转侧栏

---

## 1. 范围

- **引用扫描**: 从 Typst/Markdown 源文件提取 `peerpedia:<id>` 引用
- **引用图**: NetworkX DiGraph，实时构建 cites/cited_by 关系
- **点击跳转**: 文章页面侧栏显示引用关系，可点击导航

---

## 2. Reference Scanner

新文件: `peerpedia_core/workflow/citations.py`

```python
def extract_references(source: str) -> list[str]:
    """从源文件中提取 peerpedia 引用，返回 article_id 列表。

    支持两种格式：
    - Typst:  #cite("peerpedia:<article-id>")
    - 内联:   peerpedia:<article-id>
    """
```

- 正则匹配 `peerpedia:([a-f0-9-]{36})` 和 `#cite\("peerpedia:([a-f0-9-]{36})"\)`
- 去重返回
- 不需要新 DB 表——结果写入已有 `Article.references` 字段

---

## 3. Citation Graph

API: `GET /api/v1/articles/{id}/citations`

返回:
```json
{
  "article_id": "...",
  "cites": [{"id": "...", "title": "..."}, ...],
  "cited_by": [{"id": "...", "title": "..."}, ...]
}
```

- 使用 NetworkX 实时构建 DiGraph
- `cites`: 从 Article.references 读（我引用了谁）
- `cited_by`: 反向查询其他 Article 的 references（谁引用了我）

数据结构:
```python
def build_citation_graph(session) -> nx.DiGraph:
    """遍历所有 articles，用 references 字段建图"""
```

---

## 4. 引用自动填充

在 `submit_article()` 末尾加一步:
```python
# 扫描源文件，提取 references
refs = extract_references(source_text)
article.references = [{"article_id": rid, "title": ""} for rid in refs]
```

在 HTML 编译时（`api_compile_article`），把渲染结果中的 `peerpedia:<id>` 替换为:
```html
<a href="/article/<id>" class="citation-link">[引用文章]</a>
```

---

## 5. 前端侧栏

文章页面 (`article.html`) 右侧加引用侧栏：

```html
<aside class="citation-sidebar">
  <h3>📚 引用关系</h3>
  <div hx-get="/api/v1/articles/{{ id }}/citations"
       hx-trigger="load">
    加载中...
  </div>
</aside>
```

侧栏片段的 Jinja2 模板（返回 HTML 片段）：
- 引用 (cites) 列表 — 每项可点击跳转
- 被引用 (cited_by) 列表 — 每项可点击跳转
- 无引用时显示 "暂无引用关系"

---

## 6. 测试计划

| 测试文件 | 内容 |
|---|---|
| `tests/test_citations.py` | extract_references() 解析测试（Typst 格式 + 内联格式），build_citation_graph() 测试，API 端点测试 |

---

## 7. 文件变更

| 文件 | 操作 |
|---|---|
| `peerpedia_core/workflow/citations.py` | **Create** — scanner + graph builder |
| `peerpedia/submit.py` | Modify — 提交时扫描引用 |
| `peerpedia/web/routes/api.py` | Modify — 新增 citations 端点 + 编译时替换引用 |
| `peerpedia/web/templates/article.html` | Modify — 加引用侧栏 |
| `tests/test_citations.py` | **Create** — 约 8-10 tests |

---

## 8. 自审

- [x] 无 TBD — 所有格式、字段、API 已明确
- [x] 内部一致 — scanner → DB → graph → API → 前端完全对齐
- [x] 范围可控 — 仅引用扫描+图+跳转，不需要新 DB 表
- [x] 无歧义 — 正则模式、API 结构、HTML 模板都写清
- [x] YAGNI — 不做 D3 可视化（侧栏文本足矣），不做 PDF 引用链接（只做 HTML）
