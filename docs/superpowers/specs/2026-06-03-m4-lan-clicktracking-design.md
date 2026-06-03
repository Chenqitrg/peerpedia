# M4 LAN Cluster + Citation Click Tracking — Design Spec

> 日期: 2026-06-03
> 状态: 设计完成，待用户审核
> 依赖: Phase 3 M1-M5 已完成（157 tests）

---

## 1. Overview

两个独立但互补的子系统：

- **M4 LAN Cluster** — 同一 WiFi 下的节点互相发现、同步文章目录
- **Citation Click Tracking** — 记录读者在引用链接上的点击，构建带权跃迁图

二者通过 `catalog.md`（YAML frontmatter + Markdown 表格）共享数据，clicks 聚合数随 catalog 在 LAN 节点间同步。

---

## 2. M4 LAN Cluster

### 2.1 Discovery: UDP 广播心跳

每个节点每 3 秒在 `255.255.255.255:3690` 发送广播包，其他节点接收后更新本地节点表。

**心跳消息格式**（纯文本，一行 JSON）：

```json
{"type":"peerpedia_hello","node_id":"node-shanghai-01","host":"192.168.1.10","port":8080,"version":"0.2.0","articles_count":42}
```

**NodeInfo ORM**（SQLite，本地）：

```python
class NodeInfo(Base):
    __tablename__ = "lan_nodes"
    node_id = Column(String, primary_key=True)
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    version = Column(String, nullable=False)
    articles_count = Column(Integer, default=0)
    last_seen = Column(DateTime, nullable=False)
    is_self = Column(Integer, default=0)
```

- 超过 30 秒未收到心跳 → 标记离线
- 超过 1 小时的离线节点 → 自动清理
- `is_self=1` 记录本节点自身

### 2.2 Catalog Sync: MD 文件 HTTP 交换

每个节点暴露两个 HTTP 端点：

**`GET /api/v1/lan/catalog`** — 返回本节点的 `catalog.md` 原始内容（YAML + Markdown）

**`GET /api/v1/lan/catalog.yaml`** — 仅返回 YAML frontmatter（机器对机器，更紧凑）

**同步流程**：

```
1. 发现新节点 → HTTP GET /catalog.yaml → 拿到对方文章列表
2. 对比本地 SQLite articles 表 → 找出新文章/版本更新
3. 对每个新文章 → HTTP GET /api/v1/articles/{id}/meta → 写入本地 SQLite
4. 合并 clicks 聚合数（双方取 sum）
5. 本地 git commit catalog.md（可选，记录同步历史）
```

**同步频率**：每次发现新节点时触发全量同步，之后每 60 秒增量同步一次。

### 2.3 catalog.md 格式

```markdown
---
node_id: "node-shanghai-01"
updated: "2026-06-03T10:30:00Z"
articles:
  - id: "a1b2c3..."
    title: "Quantum Error Correction"
    authors: ["alice", "bob"]
    version: "v2.1"
    cid: "bafy...abc"
    references:
      - target: "d4e5f6..."
        title: "Holographic Duality"
        clicks_local: 15
      - target: "x7y8z9..."
        title: "Topological Order"
        clicks_local: 3
---

# 知著网 文章目录 — node-shanghai-01

| ID | 标题 | 作者 | 版本 | CID |
|----|------|------|------|-----|
| a1b2c3 | Quantum Error Correction | alice, bob | v2.1 | bafy...abc |
| d4e5f6 | Holographic Duality | bob, charlie | v1.0 | bafy...def |
```

- YAML frontmatter 是机器读写的主数据源
- Markdown 表格是给人看的冗余展示（程序自动生成，人手不改）
- `clicks_local` = 仅本节点读者的点击次数（来自 SQLite），不同节点取 **sum**（无重复，因为读者群体不重叠）

### 2.4 LAN Settings

在 `Settings` dataclass 中新增：

```python
lan_enabled: bool = False
lan_broadcast_port: int = 3690
lan_broadcast_interval: float = 3.0       # 心跳间隔（秒）
lan_sync_interval: float = 60.0           # 目录同步间隔（秒）
lan_node_timeout: float = 30.0            # 节点离线超时（秒）
manual_peers: list[str] = field(default_factory=list)  # --peers 备用
```

### 2.5 CLI 命令

```bash
peerpedia serve --lan              # 启动 Web + LAN 模式（已有占位，实现它）
peerpedia lan status               # 显示发现的节点列表 + 文章数
peerpedia lan sync [--node <id>]   # 手动触发同步
```

---

## 3. Citation Click Tracking

### 3.1 数据模型

**ClickEvent ORM**（SQLite，本地）：

```python
class ClickEvent(Base):
    __tablename__ = "click_events"
    id = Column(String(36), primary_key=True, default=uuid4)
    from_article_id = Column(String(36), ForeignKey("articles.id"), nullable=False, index=True)
    to_article_id = Column(String(36), ForeignKey("articles.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=utcnow)
    node_id = Column(String(100), nullable=False)
    user_id = Column(String(100), nullable=True)   # 可选，未来用于个性化
```

### 3.2 API

**`POST /api/v1/citations/click`** — 记录一次引用点击

```json
Request:  {"from_article_id": "a1b2c3", "to_article_id": "d4e5f6", "user_id": "alice"}
Response: {"status": "recorded", "from_article_id": "a1b2c3", "to_article_id": "d4e5f6"}
```

**`GET /api/v1/citations/transitions`** — 查询跃迁概率

Query params: `?article_id=X&source=local|lan|merged`

```json
Response: {
    "article_id": "a1b2c3",
    "source": "merged",            // local=仅本地, lan=在线节点聚合, merged=本地+catalog
    "total_clicks": 50,
    "transitions": [
        {"to_article_id": "d4e5f6", "title": "Holographic Duality", "clicks": 30, "probability": 0.60},
        {"to_article_id": "x7y8z9", "title": "Topological Order", "clicks": 15, "probability": 0.30},
        {"to_article_id": "...", "clicks": 5, "probability": 0.10}
    ]
}
```

### 3.3 前端集成

在 `article.html` 中，引用侧栏的每个 `<a>` 链接添加 click handler：

```javascript
document.querySelectorAll('.citation-link').forEach(function(link) {
    link.addEventListener('click', function(e) {
        var toId = this.dataset.targetId;
        // Fire-and-forget POST — 不阻塞跳转
        navigator.sendBeacon('/api/v1/citations/click', JSON.stringify({
            from_article_id: '{{ article.id }}',
            to_article_id: toId
        }));
    });
});
```

同时在编译时注入 `data-target-id` 属性到引用链接上。

### 3.4 跃迁概率计算

```python
def compute_transition_probabilities(
    from_article_id: str,
    click_events: list[ClickEvent],           # 本地 SQLite 逐条记录
    other_nodes_clicks: dict[str, int],       # 来自其他节点 catalog 的 clicks_local
) -> dict[str, float]:
    """合并本地点击 + 其他节点点击 → 归一化跃迁概率。

    clicks_local 语义：每个节点只记录自己读者的点击。
    不同节点的读者群体不重叠 → 直接 sum，无重复计数问题。
    """
    counts: dict[str, int] = defaultdict(int)

    # 本地精确计数（最可靠）
    for e in click_events:
        if e.from_article_id == from_article_id:
            counts[e.to_article_id] += 1

    # 其他节点的聚合数（来自 catalog merge，按节点 sum 得到）
    for to_id, n in other_nodes_clicks.items():
        counts[to_id] += n

    total = sum(counts.values())
    if total == 0:
        return {}

    return {
        to_id: count / total
        for to_id, count in sorted(counts.items(), key=lambda x: -x[1])
    }
```

**合并策略**：两数相加即可。`clicks_local` 语义清晰——每个节点只记录*自己读者的点击*，不同节点代表不同的读者群体，不存在重复计数。

### 3.5 多节点 clicks 合并示例

```
节点 A 的 catalog.md:  A→B clicks_local=15  （A 的读者点了 15 次）
节点 B 的 catalog.md:  A→B clicks_local=8   （B 的读者点了 8 次）

节点 A 计算跃迁概率：
  local（SQLite）= 15
  other（B 的 catalog）= 8
  total = 23
  P(A→B) = 23 / total_clicks_from_A

合并后的共享 catalog（广播给所有节点）:
  A→B clicks_local_sum=23  （全网总共 23 次）
```

---

## 4. 文件变更清单

### 新建文件

| 文件 | 说明 |
|------|------|
| `peerpedia_core/workflow/lan.py` | UDP 广播心跳 + 节点发现 + catalog 序列化/解析 |
| `peerpedia/web/routes/api_lan.py` | LAN catalog + 节点发现 API 端点 |
| `tests/test_lan.py` | LAN 模块测试 |
| `tests/test_click_tracking.py` | Click 追踪测试 |

### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `peerpedia_core/storage/db/models.py` | 新增 `ClickEvent`, `NodeInfo` ORM（2 表） |
| `peerpedia_core/storage/db/crud.py` | 新增 click event + node CRUD 函数 |
| `peerpedia_core/workflow/citations.py` | 新增 `record_click()`, `compute_transition_probabilities()` |
| `peerpedia_core/workflow/state_machine.py` | 无需修改 |
| `peerpedia_core/protocol/messages.py` | 可选：新增 LAN 心跳消息模型 |
| `peerpedia/web/routes/api.py` | 注册 `api_lan` router + citations click endpoint |
| `peerpedia/web/routes/pages.py` | 无需修改 |
| `peerpedia/web/templates/article.html` | 引用链接加 `data-target-id` + sendBeacon click handler |
| `peerpedia/config/settings.py` | 新增 LAN 配置字段 |
| `peerpedia/cli/main.py` | 实现 `serve --lan` + 新增 `lan status` |

### 不改的文件

- `peerpedia_core/workflow/contribution.py` — 不相关
- `peerpedia_core/workflow/collaboration.py` — 不相关
- `peerpedia_core/workflow/review.py` — 不相关
- `peerpedia_core/reputation/` — 不相关
- `peerpedia_core/storage/git_backend.py` — 不相关
- `peerpedia_core/storage/compiler.py` — 仅需在 `inject_citation_links` 中加 `data-target-id`

### 编译器小改

`inject_citation_links()` 现有输出：
```html
<a href="/article/{id}" class="citation-link">引用文章</a>
```
改为：
```html
<a href="/article/{id}" class="citation-link" data-target-id="{id}">引用文章</a>
```

---

## 5. 测试计划

### test_lan.py（~12 tests）

- UDP 广播发送/接收
- NodeInfo CRUD
- catalog 序列化/反序列化（YAML frontmatter）
- 节点超时清理
- 心跳消息解析
- `--peers` 手动配置降级

### test_click_tracking.py（~18 tests）

- ClickEvent CRUD
- `POST /api/v1/citations/click` 记录点击
- `GET /api/v1/citations/transitions` 返回跃迁概率
- 概率归一化（总和=1.0）
- 空引用（无点击）处理
- 本地 + catalog 聚合合并（sum 策略，不同节点读者不重叠）
- 单节点合并统计
- `inject_citation_links` 注入 `data-target-id`

### 全量回归

- 预计 157 + 30 = ~187 tests, 0 failures

---

## 6. 架构约束

- LAN 同步**不阻塞**主流程 — 同步失败不影响本地文章浏览
- UDP 广播**仅用于发现** — 数据同步走 HTTP（可靠传输）
- Click 记录**fire-and-forget** — `sendBeacon` 不阻塞页面跳转
- catalog.md 永远是**git 可提交的** — YAML 合法、Markdown 可渲染
- 不引入新依赖 — UDP 用标准库 `socket`，心跳消息用 `json`，YAML frontmatter 手写解析（结构固定，20 行）

### 关于 YAML 依赖

Python 3.14 无内置 YAML。选项：
1. 加 `pyyaml` 依赖（轻量，1 个包）
2. 手写 YAML frontmatter 解析/序列化（20 行，结构足够简单）

**决策：手写**。catalog.md 的 YAML 结构固定（顶层的 node_id, updated, articles 列表），不需要完整 YAML 解析器。心跳消息用 JSON（标准库）。

---

## 7. 决策记录

| # | 决策 | 结论 |
|---|---|---|
| 40 | LAN 节点发现 | UDP 广播心跳（:3690），超时 30s，清理 1h |
| 41 | 文章池同步 | HTTP GET catalog.md（YAML frontmatter + Markdown 表格） |
| 42 | MD 数据格式 | YAML frontmatter 机器读写 + Markdown 表格人类可读 |
| 43 | Catalog 同步频率 | 发现新节点时全量 + 每 60s 增量 |
| 44 | 点击追踪粒度 | 本地 SQLite 逐条记录 + catalog 聚合数（clicks 字段） |
| 45 | 跃迁概率合并 | 本节点精确（SQLite）+ 跨节点聚合（catalog），取 sum（读者群体不重叠） |
| 46 | Click API | fire-and-forget（sendBeacon），不阻塞页面跳转 |
| 47 | YAML 解析 | 手写，不引入 pyyaml 依赖 |
| 48 | LAN 手动后备 | `--peers` CLI 选项，UDP 广播被挡时手动指定 |
