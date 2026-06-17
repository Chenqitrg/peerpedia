# 权限矩阵 / Authority Matrix

> 生效版本: `phase-1a-policy-foundation` (2026-06-17)  
> 策略来源: `core/peerpedia_core/policies/articles.py`

## 文章状态

| 状态 | 含义 |
|------|------|
| `draft` | 作者编辑中，仅作者可见 |
| `sedimentation` | 在沉淀池中等待社区评审，公开可读 |
| `published` | 已通过沉淀池，公开可读，可分叉，可下载 repo |

## 调用者身份

| 身份 | 含义 |
|------|------|
| **未认证** | 未携带 token，`current_user = None`。PeerPedia 没有"匿名用户"——未认证就是没登录。 |
| **已认证** | 持有有效 token。可进一步根据是否文章作者拆分权限。 |

## 读操作

| 操作 | 路由 | 未认证可读状态 | 已认证可读状态 |
|------|------|---------------|---------------|
| 查看文章详情 | `GET /articles/{id}` | `sedimentation, published` | `draft`（仅自己的）, `sedimentation, published` |
| 列出文章 | `GET /articles` | `sedimentation, published` | `draft`（仅自己的）, `sedimentation, published` |
| 查看源码 | `GET /articles/{id}/source` | `published` | `published`；作者额外可下载 `draft, sedimentation` |
| 下载源码 | `GET /articles/{id}/download/source` | `published` | `published`；作者额外可下载 `draft, sedimentation` |
| 下载 PDF | `GET /articles/{id}/download/pdf` | `published` | `published`；作者额外可下载 `draft, sedimentation` |
| 下载 git repo | `GET /articles/{id}/download/repo` | `published` | `published`；作者额外可下载 `draft, sedimentation` |
| 查看 diff | `GET /articles/{id}/diff/{a}/{b}` | `sedimentation, published` | `draft`（仅自己的）, `sedimentation, published` |
| 查看历史 | `GET /articles/{id}/history` | `sedimentation, published` | `draft`（仅自己的）, `sedimentation, published` |
| 查看 HEAD | `GET /articles/{id}/head` | `sedimentation, published` | `draft`（仅自己的）, `sedimentation, published` |

## 写操作

所有写操作要求已认证 + 是文章作者。未认证请求一律返回 401/403 （在core里不知道什么是401/403? 这或许是个问题？因为似乎异常报错在core里是纯语义的返回值。）。

| 操作 | 路由 | 允许状态 |
|------|------|----------|
| 编辑文章 | `PUT /articles/{id}` | `draft, published` |
| 删除文章 | `DELETE /articles/{id}` | `draft, published` |
| 回滚 | `POST /articles/{id}/rollback/{hash}` | `draft, published` |
| 延长沉淀期 | `PUT /articles/{id}/sink-extension` | `sedimentation` |
| 同步 bundle | `POST /articles/{id}/sync` | `draft, published` |

## 生命周期操作

| 操作 | 路由 | 允许状态 | 额外条件 |
|------|------|----------|----------|
| 创建文章 | `POST /articles` | —（新文章，初始状态 `draft`） | 已认证即可 |
| 发布到沉淀池 | `POST /articles/{id}/publish` | 任意（作者） | HEAD commit 必须有 `scope=pool` 的自审记录 |
| 分叉文章 | `POST /articles/{id}/fork` | `published` | 同一用户不能重复分叉同一篇文章 |

## 状态常量

```python
# core/peerpedia_core/policies/articles.py

PUBLIC_READABLE_STATUSES   = {"sedimentation", "published"}
FORKABLE_STATUSES          = {"published"}
REPO_DOWNLOADABLE_STATUSES = {"published"}
```

`visible_statuses_for_user` 的返回值：

```python
visible_statuses_for_user(None)                 → {"sedimentation", "published"}
visible_statuses_for_user(authenticated_user)   → {"draft", "sedimentation", "published"}
```

## 异常映射

权限检查抛出 `peerpedia_core.exceptions` 中的语义异常，由 `backend/peerpedia_api/main.py` 的 handler 统一转为 HTTP 状态码：

| 异常 | HTTP | 触发场景 |
|------|------|----------|
| `NotFoundError` | 404 | 文章不存在 |
| `NotAuthorizedError` | 403 | 权限不足（非公开状态 + 非作者） |
| `ConflictError` | 409 | 重复分叉 |
| `BadRequestError` | 400 | 发布前缺少自审、git repo 不存在 |

## 设计原则

1. **Core 无 HTTP** — 异常名描述"什么错了"，不描述"HTTP 返回什么"
2. **默认拒绝** — 未匹配任何允许规则的访问一律拒绝
3. **一函数一检查** — 路由调 `assert_can_*`，不散落 `current_user.id in get_author_ids(...)`
4. **Repo 下载 = Fork** — 沉淀池文章不可分叉，完整 git 历史导出视为等价操作
