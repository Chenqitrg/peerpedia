# Lessons Learned

> 从实际开发和调试中积累的经验教训。每个条目包含问题、根因、修复和预防措施。

## 1. DB 数据丢失

**问题**: 重构 crud/lan 模块后，demo 数据（4 用户、4 文章、7 关注关系）丢失，导致首页无文章、用户选择器只有"游客"。

**根因**: SQLite DB 文件在重构过程中被覆盖或清空。没有 seed 脚本可以快速重建。

**修复**: 通过 CLI 重新注册 4 个用户，用 submit_article 重建 4 篇文章，设置发布时间和关注关系。

**预防**:
- 每次修改 DB 相关代码后，验证 DB 状态
- 需要写一个 `peerpedia seed` 命令来快速重建 demo 数据

## 2. HTMX Feed 返回 JSON 导致乱码

**问题**: 首页"关注动态" tab 显示乱码。HTMX 请求 `/api/v1/following/feed` 后，`hx-swap="innerHTML"` 把 JSON 当 HTML 渲染。

**根因**: feed 端点返回 `{"user_id": "...", "events": [...]}` JSON dict，但 HTMX 期望 HTML 片段。

**修复**:
- 添加 `_render_feed_html()` 函数，将 events 渲染为 HTML
- 端点支持 `?format=html` 参数（和 followers/following 端点一致）
- 首页模板改为 `hx-get="...&format=html"`
- 扩大 feed 时间窗口从 30 天到 60 天

**预防**: 所有 HTMX `hx-swap="innerHTML"` 的端点，必须返回 HTML。用浏览器测试，不要只用 curl。

## 3. Jinja2 模板缓存

**问题**: 修改模板后刷新浏览器看不到变化。`uvicorn --reload` 只监听 Python 文件变更，不监听 `.html` 模板。

**修复**: 杀掉服务器进程重启：`lsof -ti:8080 | xargs kill -9 && peerpedia serve`

**预防**: 模板修改后强制重启。验证命令：`curl -s http://localhost:8080/ | grep "expected-string"`

## 4. 新 UI 组件必须有 CSS

**问题**: 添加审稿按钮、协作复选框、贡献时间线、编辑提案表单等新 HTML 元素后，用户看不到或看到无样式的原始元素。

**根因**: 只改了 HTML 模板，没加 CSS。另外 body `max-width: 800px` 太窄，放不下侧栏。

**修复**:
- body 宽度 800px → 1100px
- 添加 `.btn-review`、`.citation-sidebar`、`.contribution-timeline`、`.edit-proposal-form`、`.identity-section`、`.lan-table` 样式
- 添加移动端响应式断点 `@media (max-width: 768px)`

**预防**: 每次加新的 HTML 组件时，同时添加 CSS。用 gstack browse 在浏览器中验证视觉效果。

## 5. 模板 HTML 结构错误

**问题**: article.html 模板有多余的 `</div>` 标签，导致 HTML 结构破坏。在插入 B3/B4 内容时遗留。

**修复**: 删除多余的 `</div>`。

**预防**: 修改模板后检查 `curl` 输出的 HTML 中 `<div>` 和 `</div>` 数量是否匹配。

## 6. 公式渲染顺序

**问题**: Markdown 数学公式 `$x_i$` 中的下划线被 Markdown 解析器转成 `<em>i</em>`，导致 KaTeX 无法渲染。

**根因**: `_render_markdown()` 先于 `_wrap_math()` 执行。Markdown 看到 `_` 就转成 `<em>`，之后 `_wrap_math` 的 `$...$` 正则匹配失败。

**修复**: Plan A — 用占位符保护。先 `_protect_math()` 替换公式为占位符，再 `_render_markdown()`，最后 `_restore_math()` 恢复公式并包裹 KaTeX span。

**预防**: 任何时候修改编译器管线，先加单元测试覆盖边缘情况（下划线、多行公式、混合格式）。

## 7. ruff 自动清理可能删除 facade imports

**问题**: `ruff --fix` 删除了 `crud.py` 和 `lan.py` facade 模块的 import 语句，因为 `__all__ = [n for n in dir()...]` 没有直接引用导入的符号。

**修复**: 在每个 import 行加 `# noqa: F401` 注释，防止 ruff 删除。或者改用显式的 `__all__` 列表。

**预防**: 对 facade/re-export 模块的 import 行加 `# noqa: F401`。

## 开发检查清单

每次提交前：

1. `python -m pytest tests/ -q` — 全部通过
2. `python -m mypy peerpedia_core/ peerpedia/ --ignore-missing-imports` — 0 errors
3. `python -m ruff check .` — 无新增 critical issues
4. 验证 DB 状态（用户数、文章数）
5. 如果改了模板或 CSS：重启服务器 + gstack browse 验证
6. 如果加了新功能：添加回归测试
