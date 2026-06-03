# M4 Reputation Cluster — 设计规格

> 日期: 2026-06-03
> 状态: 已批准
> 方案: B（中等方案）— 新增 users/identities 表 + 实时计算 + Chart.js

---

## 1. 范围

M4 分为两个集群，本次实现 **Reputation 集群**（M4.1 + M4.2）：

- **M4.1 雷达图可视化**: 用户主页展示四维信誉雷达图（Chart.js CDN）
- **M4.2 身份权重计算**: 新增 users/identities 表，计算 identity- boosted reputation

**不包含**: LAN 节点发现（M4.3）、文章池同步（M4.4）— 下个迭代。

---

## 2. 数据模型

### 2.1 新增 ORM 表

**users 表**:
| 列 | 类型 | 说明 |
|---|---|---|
| id | String(100) PK | user slug, e.g. "zhangsan" |
| name | String(200) | 显示名 |
| email | String(300) | 邮箱 |
| affiliation | String(500) nullable | 机构 |
| expertise | JSONList | ["quantum", "topology"] |
| bio | Text nullable | 个人简介 |
| public_key | Text nullable | PGP/SSH 公钥 |
| joined_at | DateTime | 注册时间 |
| last_active | DateTime nullable | 最后活跃时间（衰减计算） |

**identities 表**:
| 列 | 类型 | 说明 |
|---|---|---|
| id | String(36) PK | UUID |
| user_id | String(100) FK→users.id | 关联用户 |
| type | String(20) | orcid / inst_email / arxiv / github / scholar |
| value | String(300) | "0000-0001-2345-6789" |
| verified | Integer(0/1) | 是否已验证 |
| trust_weight | Integer | ×100 存储（1.0 → 100, 0.3 → 30）|

### 2.2 向后兼容

- 现有 `Article.founding_authors` 和 `Review.reviewer_id` 不变
- user_id 保持一致（字符串 slug）
- 没有 users 表记录的 user_id 仍然有效（"anonymous"等），只是没有信誉档案

---

## 3. API 新增端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/users/{user_id}` | 用户信息 + 身份列表 |
| POST | `/api/v1/users` | 创建用户 |
| POST | `/api/v1/users/{user_id}/identities` | 绑定身份 |
| GET | `/api/v1/users/{user_id}/reputation` | 返回 ReputationVector JSON |

---

## 4. 信誉计算逻辑

`ReputationV1.compute(user_id, session)` 实现：

1. **聚合已有数据**: 文章数、审稿数、审稿积分、贡献权重
2. **身份加权**: `multiplier = 1.0 + sum(verified_identity.trust_weight/100) * 0.1`
3. **时间衰减**: `decay = max(0.5, 0.999 ^ max(0, days_inactive - 90))`
4. **四维计算**: 各项 × multiplier × decay，capped at 100

### 身份权重默认值（来自 ReputationParams）

| IdentityType | trust_weight |
|---|---|
| ORCID | 1.0 |
| INST_EMAIL | 0.8 |
| ARXIV | 0.6 |
| GOOGLE_SCHOLAR | 0.5 |
| GITHUB | 0.3 |

---

## 5. 前端变更

### 5.1 用户页面 (`/user/{user_id}`)

- 新增 **雷达图区域**（Chart.js canvas，200×200px）
- 四轴标签：学术贡献 / 审稿质量 / 协作精神 / 教学传播
- 雷达图数据通过 HTMX `hx-get="/api/v1/users/{user_id}/reputation"` 加载

### 5.2 Chart.js 集成

- CDN 引入：`<script src="https://cdn.jsdelivr.net/npm/chart.js">`
- 零 npm 依赖，零构建步骤
- 仅用户页面加载（按需）

---

## 6. CLI 变更

新增 1 个命令：

```bash
peerpedia user register <user_id> --name "张三" --email "a@b.com"
```

---

## 7. 测试计划

| 测试文件 | 内容 |
|---|---|
| `tests/test_user_db.py` | User + Identity CRUD 操作 |
| `tests/test_reputation.py` | 扩展：compute 集成测试（含身份加权、衰减） |
| `tests/test_user_api.py` | API 端点测试（创建用户、绑定身份、获取信誉）|

---

## 8. 文件变更清单

| 文件 | 操作 |
|---|---|
| `peerpedia_core/storage/db.py` | 新增 User + Identity ORM + CRUD |
| `peerpedia_core/reputation/v1.py` | 实现 compute() 方法 |
| `peerpedia/web/routes/api.py` | 新增 4 个 API 端点 |
| `peerpedia/web/routes/pages.py` | 用户页面加入 reputation 数据 |
| `peerpedia/web/templates/user.html` | 新增雷达图区域 + Chart.js 脚本 |
| `peerpedia/cli/main.py` | 新增 `user register` 命令 |
| `tests/test_user_db.py` | 新测试文件 |
| `tests/test_reputation.py` | 扩展测试 |
| `tests/test_user_api.py` | 新测试文件 |

---

## 9. 自审清单

- [x] 无 TBD/placeholder — 所有字段已明确
- [x] 内部一致 — 数据模型 ↔ API ↔ 前端一致
- [x] 范围可控 — 仅 reputation cluster，不含 LAN
- [x] 无歧义 — trust_weight 存储格式明确（×100 整数）
- [x] 向后兼容 — 不破坏现有 Article/Review 表
