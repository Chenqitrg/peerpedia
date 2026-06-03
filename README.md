# 知诸网 (PeerPedia)

**去中心化学术出版系统 — 取代 arXiv 和学术期刊。**

> 谐音「蜘蛛网」🕸️：P2P 节点互联。取"孜孜以求，诸子百家"之意。

```
Author writes in Typst → Peer review → Publish → Cite & collaborate
                           ↑
              Reviewer can join as co-author
              Post-publication open editing
              Git-native contribution timeline
              Citation DAG with click-to-jump
              Multi-dimensional reputation radar
```

## Architecture

```
peerpedia_core/     ← Protocol (messages, signing, reputation, storage, citations)
peerpedia/          ← Reference client (CLI + Web)
```

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Register a user
peerpedia user register zhangsan --name "张三" --email "zhang@example.com"

# Submit an article (auto-scans peerpedia references)
peerpedia submit article.typ --author zhangsan

# Start the web interface
peerpedia serve

# Start LAN mode (multi-user on same network)
peerpedia serve --lan
```

## Features

| Category | Feature | Status |
|---|---|---|
| **Submit** | Typst + Markdown/Katex article submission with auto-compile | ✅ |
| **Review** | Peer review workflow: assign → score → decide | ✅ |
| **Collaboration** | Reviewer → co-author, post-publication edit proposals | ✅ |
| **Reputation** | 4D radar chart (academic/review/collaboration/education) + identity boost | ✅ |
| **Citations** | Reference scanning, NetworkX citation graph, click-to-jump sidebar + click tracking | ✅ |
| **Mirror** | ArXiv article import with dangling founder accounts | ✅ |
| **LAN** | UDP broadcast node discovery + catalog.md article pool sync | ✅ |
| **Follow** | Follow authors, activity feed (HTMX-driven) | ✅ |

## Available Commands

```bash
peerpedia init                                    # Initialize ~/.peerpedia/
peerpedia serve [--lan] [--port 8080]              # Start web interface
peerpedia submit article.typ --author zhangsan     # Submit article
peerpedia review <id> -d accept -c "great work"    # Submit peer review
peerpedia decide <id>                              # Decide on article
peerpedia mirror 2301.00001 -u zhangsan            # Mirror from arXiv
peerpedia collaborate <id> -r reviewer_name        # Accept collaboration
peerpedia propose-edit <id> -t minor -d "fix typo" # Propose post-publication edit
peerpedia merge-proposal <pid> <aid>               # Merge approved proposal
peerpedia user register <id> --name 张三 --email .. # Register user
peerpedia lan status                               # LAN node status
peerpedia lan sync [-n <node>]                     # Sync article catalog
```

## API Endpoints (30 routes)

| Group | Endpoints |
|---|---|
| Articles | GET/POST `/api/v1/articles`, GET `/articles/{id}`, GET `/articles/{id}/compile`, GET `/articles/{id}/reviews`, POST reviews, POST decide |
| Users | GET/POST `/api/v1/users`, GET `/users/{id}`, POST `/users/{id}/identities`, GET `/users/{id}/reputation` |
| Citations | GET `/citations` (cites + cited-by), POST `/citations/click`, GET `/citations/transitions` |
| Follow | POST/DELETE `/users/{id}/follow`, GET `/users/{id}/following`, GET `/users/{id}/followers`, GET `/following/feed` |
| Collaboration | POST `/articles/{id}/collaborate`, GET `/articles/{id}/collaboration/{reviewer}` |
| Edit Proposals | POST `/articles/{id}/proposals`, GET `/articles/{id}/proposals`, POST `/proposals/{id}/review`, POST `/proposals/{id}/merge` |
| Contributions | GET `/articles/{id}/contributions` (timeline + breakdown) |
| LAN | GET `/lan/catalog`, GET `/lan/nodes`, GET `/lan/status` |
| Health | GET `/api/v1/health` |

## Development

```bash
# Run tests
pytest                    # 211 tests, 0 failures

# Run with coverage
pytest --cov=peerpedia_core --cov=peerpedia
```

## Design

See [design/brainstorm.md](design/brainstorm.md) for the full vision, decisions, and roadmap.
See [STATUS.md](STATUS.md) for current state and restart guide.

## License

MIT — Protocol is free, reference implementation is MIT.
Content published via PeerPedia is CC BY-SA 4.0 by default.
