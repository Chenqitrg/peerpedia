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

## 2. Step 1: 后端——自收藏拒绝

**规格:** SPEC-1.1, SPEC-1.2, SPEC-1.6  
**文件:** `backend/peerpedia_api/routes/bookmarks.py`  
**测试:** `backend/tests/test_routes_pool_bookmarks.py`

### 2.1 修改 routes/bookmarks.py

定位 `backend/peerpedia_api/routes/bookmarks.py`。

#### 第 3 行附近，import 区域

**当前（第 3 行）：**
```python
from peerpedia_core.storage.db.crud_article import get_article, get_author_ids
```

如果 `get_author_ids` 还没有被导入，添加它。检查第 3 行是否已经包含 `get_author_ids`。如果没有，改为：
```python
from peerpedia_core.storage.db.crud_article import get_article, get_author_ids
```

#### bookmark() 函数（约第 32-39 行）

**当前代码：**
```python
@router.post("", status_code=201)
def bookmark(article_id: str, current_user: User = Depends(deps.require_user),
             db: Session = Depends(deps.get_db)):
    if get_article(db, article_id) is None:
        raise HTTPException(status_code=404, detail="Article not found")
    if not is_bookmarked(db, current_user.id, article_id):
        add_bookmark(db, current_user.id, article_id)
    return {"bookmarked": True}
```

**改为：**
```python
@router.post("", status_code=201)
def bookmark(article_id: str, current_user: User = Depends(deps.require_user),
             db: Session = Depends(deps.get_db)):
    if get_article(db, article_id) is None:
        raise HTTPException(status_code=404, detail="Article not found")
    author_ids = get_author_ids(db, article_id)
    if current_user.id in author_ids:
        raise HTTPException(status_code=400, detail="Cannot bookmark your own article")
    if not is_bookmarked(db, current_user.id, article_id):
        add_bookmark(db, current_user.id, article_id)
    return {"bookmarked": True}
```

#### unbookmark() 函数（约第 42-46 行）

**当前代码：**
```python
@router.delete("/{article_id}")
def unbookmark(article_id: str, current_user: User = Depends(deps.require_user),
               db: Session = Depends(deps.get_db)):
    remove_bookmark(db, current_user.id, article_id)
    return {"bookmarked": False}
```

**改为：**
```python
@router.delete("/{article_id}")
def unbookmark(article_id: str, current_user: User = Depends(deps.require_user),
               db: Session = Depends(deps.get_db)):
    author_ids = get_author_ids(db, article_id)
    if current_user.id in author_ids:
        raise HTTPException(status_code=400, detail="Cannot bookmark your own article")
    remove_bookmark(db, current_user.id, article_id)
    return {"bookmarked": False}
```

### 2.2 添加后端测试

定位 `backend/tests/test_routes_pool_bookmarks.py`，在 `TestBookmarks` 类末尾（约第 101 行之后）添加：

```python
    def test_self_bookmark_rejected(self, client, db_engine, auth_header):
        """SPEC-1.1: 用户不能收藏自己的文章"""
        s = get_session(db_engine)
        u = User(username="author1", password_hash="", name="作者", anonymous_name="a")
        s.add(u)
        s.commit()
        a = Article(status="published")
        s.add(a)
        s.commit()
        # 将 u 设为文章作者
        from peerpedia_core.storage.db.models import ArticleAuthor
        s.add(ArticleAuthor(article_id=a.id, author_id=u.id, position=0))
        s.commit()
        s.close()

        headers = auth_header(u.id)
        resp = client.post(f"/api/v1/bookmarks?article_id={a.id}", headers=headers)
        assert resp.status_code == 400
        assert "own article" in resp.json()["detail"].lower()

    def test_self_unbookmark_rejected(self, client, db_engine, auth_header):
        """SPEC-1.2: 用户不能取消收藏自己的文章（虽然是多余的，但保持 API 一致）"""
        s = get_session(db_engine)
        u = User(username="author2", password_hash="", name="作者2", anonymous_name="a")
        s.add(u)
        s.commit()
        a = Article(status="published")
        s.add(a)
        s.commit()
        from peerpedia_core.storage.db.models import ArticleAuthor
        s.add(ArticleAuthor(article_id=a.id, author_id=u.id, position=0))
        s.commit()
        s.close()

        headers = auth_header(u.id)
        resp = client.delete(f"/api/v1/bookmarks/{a.id}", headers=headers)
        assert resp.status_code == 400
```

### 2.3 验证 Step 1

```bash
cd backend
python -m pytest tests/test_routes_pool_bookmarks.py -x -q -v
# 预期: 所有测试通过，包括 2 个新测试
# 之前: ~4 个 test_bookmark 测试 → 现在: ~6 个
cd ..
```

---

