# Sync Auto-Push Design

**Date**: 2026-06-14
**Status**: Approved

## Problem

当前同步功能有多余的"保险"层，用户在联网后需要手动确认每个待推送操作：

- `ReconnectDialog` — 重连后逐条确认 push/discard
- `SyncConflictsPage` — 独立冲突处理页面，Router Guard 强制跳转
- `SyncButton` — 需要手动点击连接

用户已经有 Git 版本历史和 commit message 做变更追踪，这些额外的同步确认是冗余的。

## Principle

**本地即权威（Local as Source of Truth）。** 联网后自动将本地操作推送到服务器，静默覆盖服务器版本，无需任何同步确认。

## Scope

### Remove

| 组件/逻辑 | 文件 | 说明 |
|---|---|---|
| ReconnectDialog | `frontend/src/components/ReconnectDialog.vue` | 整个组件删除 |
| SyncConflictsPage | `frontend/src/pages/SyncConflictsPage.vue` | 整个页面 + 路由 `/sync/conflicts` 删除 |
| Router Guard 冲突阻断 | `frontend/src/router/index.ts` | 去掉 `pendingConflictCount` 检查 |
| pendingConflictCount | `frontend/src/App.vue` | 去掉相关状态和 watcher |

### Modify

| 组件 | 文件 | 改动 |
|---|---|---|
| App.vue `isSynced` watcher | `frontend/src/App.vue` | 检测到联网 → 自动批量推送 pending 操作 |
| EditorPage save flow | `frontend/src/pages/EditorPage.vue` | 保存后在线则自动 push，失败静默忽略 |
| SyncButton | `frontend/src/components/SyncButton.vue` | 从手动连接开关 → 连接状态指示器 |
| useNetworkStatus | `frontend/src/composables/useNetworkStatus.ts` | 连接改为自动检测，去手动触发 |

### Keep Unchanged

- Commit message 弹窗（`useCommitFlow`）
- Delete 确认（一步确认框，`DeleteButton.vue`）
- Git log / 版本历史
- 本地暂存（draft persistence）

## Data Flow

```
离线编辑 → 本地暂存 + pending 队列
       ↓
  检测到网络恢复（自动）
       ↓
  静默推送所有 pending（本地覆盖服务器）
       ↓
  NavBar toast "已同步 N 条更改"
```

## UX Details

### SyncButton 演变为状态指示器

- **离线**：WiFi 图标灰色 + 下方红色数字标记未同步 commit 数
- **同步中**：WiFi 图标旋转动画
- **已同步**：WiFi 图标蓝色，显示最近同步时间

用户无需点击，连接检测全自动。

### 冲突策略

本地直接覆盖服务器。不做时间戳比较、不做合并、不创建分支。

### 失败处理

- 推送失败时静默忽略，等待下次网络恢复后重试
- 不弹错误对话框
- 4xx 错误（如文章已被删除）丢弃 pending，不再重试

## Files Touched

```
frontend/src/components/ReconnectDialog.vue       # DELETE
frontend/src/pages/SyncConflictsPage.vue           # DELETE
frontend/src/router/index.ts                       # MODIFY (remove guard)
frontend/src/App.vue                               # MODIFY (auto-push watcher)
frontend/src/pages/EditorPage.vue                  # MODIFY (auto-push on save)
frontend/src/components/SyncButton.vue             # MODIFY (status indicator)
frontend/src/composables/useNetworkStatus.ts       # MODIFY (auto-detect)
```

## Verification

1. 离线编辑一篇文章，保存（commit message 弹窗正常工作）→ 检查 WiFi 图标显示红色未同步数字
2. 恢复网络 → 自动推送，无弹窗 → 服务器文章内容已更新
3. 离线删除一篇文章 → 恢复网络 → 自动同步删除，确认框正常弹出
4. 同时在线 → 保存自动 push，commit message 弹窗正常
5. 服务器不可达 → 静默失败，pending 队列保留，下次恢复网络重试
