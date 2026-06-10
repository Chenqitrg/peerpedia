# Self-Hosted Deployment Design — Phase 2 "Go Online"

> 2026-06-09 · PeerPedia 从本地到联网的部署方案

## 1. 目标

不租云服务器，用现有的台式机作为 PeerPedia 服务器，让 < 10 个人通过公网访问。

## 2. 约束

- 不租 VPS（Hetzner/DigitalOcean），成本 = 0
- 台式机位于办公室/宿舍/家中，没有公网 IP
- 只存索引（文章元数据 + 关系），不存文章内容（内容在 Git repo 中，Git = 内容分发层）
- 用户 < 10 人，无需考虑高并发
- 需要 HTTPS，不能裸 HTTP

## 3. 架构

```
互联网用户 ──HTTPS──▶ Cloudflare ──Cloudflare Tunnel──▶ 台式机
   (< 10人)          (peerpedia.dev)                    FastAPI :8080
                                                        SQLite :peerpedia.db
                                                        Git repos :~/.peerpedia/articles/
```

### 3.1 组件

| 组件 | 角色 | 成本 |
|------|------|------|
| **台式机** | 运行 FastAPI + SQLite + Git repos | 已有 |
| **Cloudflare Tunnel** (`cloudflared`) | 内网穿透，将 Cloudflare 边缘节点连接到台式机 :8080 | 免费 |
| **Cloudflare DNS** | 解析 `peerpedia.dev` 到 Tunnel | 免费 |
| **Cloudflare SSL** | 自动 HTTPS 证书 | 免费 |
| **域名 `peerpedia.dev`** | 用户访问入口 | ~$12/年 |

### 3.2 数据流

```
[浏览器] → peerpedia.dev → Cloudflare Edge → cloudflared → localhost:8080
                                                              │
                                                    FastAPI (peerpedia_api)
                                                              │
                                                              ├── SQLite (索引)
                                                              └── Git repos (内容)
```

### 3.3 Cloudflare Tunnel 原理

`cloudflared` 是在台式机上运行的一个轻量 daemon，它主动向 Cloudflare 边缘节点建立一条持久化的 QUIC 隧道。外界访问 `peerpedia.dev` 的流量通过 Cloudflare 的全球网络转发到这条隧道，最终到达 `localhost:8080`。

```
cloudflared tunnel create peerpedia
cloudflared tunnel route dns peerpedia peerpedia.dev
cloudflared tunnel run --url http://localhost:8080 peerpedia
```

### 3.4 安全考量

- **Cloudflare WAF**: 免费套餐自带 DDoS 防护和基础 WAF
- **Cloudflare Access**: 可选，加一层 GitHub OAuth 登录，只允许你邀请的人访问
- **JWT auth**: 已有的 FastAPI JWT 认证继续生效
- **数据库**: SQLite 单文件，无需担心远程数据库攻击面
- **台式机不需要开放任何入站端口** — cloudflared 只出站

## 4. 部署清单

### 4.1 域名

1. 在 Cloudflare（或任意注册商）购买 `peerpedia.dev`（~$12/年）
2. DNS 托管到 Cloudflare（免费）

### 4.2 台式机

```bash
# 1. 安装 cloudflared
brew install cloudflare/cloudflare/cloudflared
# 或 https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

# 2. 认证
cloudflared tunnel login

# 3. 创建隧道
cloudflared tunnel create peerpedia

# 4. 配置 DNS
cloudflared tunnel route dns peerpedia peerpedia.dev

# 5. 启动
cloudflared tunnel run --url http://localhost:8080 peerpedia
```

### 4.3 应用

```bash
# 启动后端（和现在一样）
uvicorn peerpedia_api.main:app --port 8080

# 或者做成 systemd/launchd 服务实现开机自启
```

### 4.4 验证

```bash
curl https://peerpedia.dev/health
curl https://peerpedia.dev/api/v1/articles
```

## 5. 台式机关机/断网怎么办

- **Cloudflare 显示 502** — 用户会看到 Cloudflare 的错误页面
- **解决**: 可以考虑加一个便宜的 VPS 做 fallback（未来），或者接受"主机在线才可用"的约束
- **通知**: 可以用一个简单的静态页面（Cloudflare Pages 免费托管）作为 landing page，显示服务状态

## 6. 未来演进

| 阶段 | 方案 | 触发条件 |
|------|------|----------|
| 现在 | 台式机 + cloudflared | < 10 用户 |
| 用户增长 | VPS（Hetzner CX22 €4/mo） | 台式机不稳定/用户 > 10 |
| 内容分发 | P2P（Phase 3） | 文章数量大，Git 拉取慢 |

## 7. NOT in Scope

- 不实现 P2P 内容分发（Phase 3）
- 不做 CDN 缓存（暂时不需要）
- 不做数据库备份（Git 是 Source of Truth，DB 可重建）
- 不做自动伸缩/容器化

## 8. 决定

- [x] 域名: `peerpedia.dev`
- [x] 隧道: Cloudflare Tunnel
- [x] 台式机直接跑 FastAPI，不容器化
- [x] 只存索引，不存内容
