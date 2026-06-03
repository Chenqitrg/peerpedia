# 知著网 (PeerPedia)

**去中心化学术出版系统 — 取代 arXiv 和学术期刊。**

```
Author writes in Typst → Peer review → Publish to P2P network
                           ↑
              Reviewer can join as co-author
              Post-publication open editing
              Git-native contribution timeline
```

## Architecture

```
peerpedia_core/     ← Protocol (message formats, signing, reputation, storage)
peerpedia/          ← Reference client (CLI + Web)
```

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Start single-user mode
peerpedia serve

# Start LAN mode (multi-user on same network)
peerpedia serve --lan
```

## Development

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=peerpedia_core --cov=peerpedia
```

## Design

See [design/brainstorm.md](design/brainstorm.md) for the full vision and decisions.

## License

MIT — Protocol is free, reference implementation is MIT.
Content published via PeerPedia is CC BY-SA 4.0 by default.
