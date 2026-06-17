# PeerPedia 技术架构审查（P0级问题）

## 目的

本文档不讨论：

* 产品需求
* 功能设计
* 社区治理
* Reputation机制
* Review机制
* Citation机制

默认上述需求已经确定。

本文仅讨论：

> 哪些技术设计现在修改成本极低，但后期会导致大规模重构。

---

# P0-1：Review.thread 不应使用 JSON

## 当前设计

```python
Review.thread = JSON
```

例如：

```json
[
  {
    "author": "Alice",
    "content": "I disagree"
  },
  {
    "author": "Bob",
    "content": "Why?"
  }
]
```

---

## 风险

随着回复增加：

* 无法分页
* 无法高效搜索
* 无法建立索引
* 并发修改冲突

每次回复都需要：

```text
读取整个JSON
修改
写回整个JSON
```

---

## 推荐方案

拆分为：

```python
Review
```

```python
ReviewMessage
```

示例：

```python
Review
------
id

ReviewMessage
------
id
review_id
parent_id
author_id
content
created_at
```

---

## 修改成本

当前：极低

后期：极高

优先级：

```text
P0
```

---

# P0-2：所有关系数据禁止使用 JSON

## 检查范围

需要检查所有模型。

如果出现：

```python
followers = JSON
```

```python
citations = JSON
```

```python
reviews = JSON
```

```python
votes = JSON
```

类似设计。

---

## 风险

关系数据最终一定需要：

```text
查询
排序
统计
过滤
索引
```

JSON 不适合承担此职责。

---

## 原则

允许 JSON：

```text
用户配置
编辑器状态
缓存
AI分析结果
```

禁止 JSON：

```text
用户关系
Review关系
Citation关系
Follow关系
投票关系
```

---

## 修改成本

当前：极低

后期：极高

优先级：

```text
P0
```

---

# P0-3：明确 Source of Truth

## 当前问题

系统同时维护：

```text
Git
+
Database
```

但未明确：

```text
谁是真相源
```

---

## 风险

出现：

```text
Git成功
DB失败
```

或：

```text
DB成功
Git失败
```

时，

系统状态会产生分裂。

---

## 必须确定

以下二选一：

### 方案A

```text
Git = Source of Truth
DB = Index
```

推荐。

---

### 方案B

```text
DB = Source of Truth
Git = Export Layer
```

也可以。

---

禁止：

```text
Git ↔ DB 双向真相源
```

---

## 修改成本

当前：低

后期：灾难级

优先级：

```text
P0
```

---

# P0-4：禁止持久化 compiled_output

## 当前设计

数据库保存：

```python
compiled_output
compiled_pages
```

即：

```text
Markdown
↓
HTML
↓
Database
```

---

## 风险

未来：

```text
Markdown升级
Typst升级
KaTeX升级
```

都会导致历史缓存失效。

---

## 推荐

数据库只保存：

```python
source
```

例如：

```text
markdown_source
typst_source
```

---

编译结果：

```text
Cache
```

而非：

```text
Primary Data
```

---

## 修改成本

当前：低

后期：高

优先级：

```text
P0
```

---

# P0-5：Article.score 不应作为核心字段

## 当前设计

```python
Article.score
```

保存聚合结果。

---

## 风险

评分依赖：

```text
Review
Vote
Reputation
```

未来都会变化。

---

容易出现：

```text
缓存失效
同步错误
历史数据错误
```

---

## 推荐

Phase 1：

```text
实时计算
```

性能不足后：

```text
Materialized View
Redis Cache
Background Job
```

---

## 修改成本

当前：低

后期：中高

优先级：

```text
P0
```

---

# P1-1：Repository 粒度重新评估

## 当前设计

```text
One Article
=
One Repository
```

---

## 风险

未来：

```text
10万文章
=
10万个Git Repo
```

会增加运维复杂度。

---

## 建议

保留现有实现作为 MVP。

但需要在文档中明确：

```text
未来可能迁移为
Sharded Repository Architecture
```

---

## 修改成本

当前：中

后期：中

优先级：

```text
P1
```

---

# P1-2：SQLite 仅作为 MVP 方案

## 建议

在架构文档明确：

```text
SQLite
=
Phase 1
```

未来默认迁移：

```text
PostgreSQL
```

---

不要让业务逻辑依赖 SQLite 特性。

---

## 修改成本

当前：低

后期：中

优先级：

```text
P1
```

---

# P1-3：Citation 模型先最小化

## 当前设计

出现：

```python
forward_prob
backward_prob
```

等高级字段。

---

## 建议

第一阶段仅保留：

```python
from_id
to_id
```

即可。

---

复杂权重等待真实数据验证后引入。

---

## 修改成本

当前：极低

后期：低

优先级：

```text
P1
```

---

# 建议执行顺序

## 本周必须处理

```text
Review.thread
JSON关系字段
Source of Truth
compiled_output
```

---

## 第一版上线前处理

```text
Article.score
Citation简化
```

---

## 用户增长后处理

```text
SQLite迁移
Repository分片
```

---

# 总结

本次审查认为：

真正需要立即修改的并不多。

最关键的原则只有三条：

1. 关系数据不要塞进 JSON
2. Source of Truth 必须唯一
3. 编译结果不要作为核心数据存储

这三项属于架构级问题。

现在修改成本极低。

后期修改成本极高。

建议在开始大规模编码前完成调整。
