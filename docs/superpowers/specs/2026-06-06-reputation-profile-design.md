# ReputationBadges + UserCard 设计

## 1. ReputationBadges 组件

对标 ScoreBadges，紧凑显示四维声誉，hover 展开全称。

| 缩写 | 英文全称 | 中文 |
|------|---------|------|
| P | Professionalism | 专业度 |
| O | Objectivity | 客观性 |
| C | Collaboration | 协作性 |
| R | Readability | 可读性 |

```
默认:   P:5  O:4  C:3  R:4    ← 紧凑一行
hover P: Professionalism:5    ← 平滑展开，同 ScoreBadges 动画
```

## 2. UserCard 组件

复用组件，对标 ArticleCard 格式。结构：

```
┌─────────────────────────────────────────┐
│ 👤 Avatar  用户名                        │
│            归属机构                       │
│            N articles  ·  reputation      │
│            ReputationBadges               │
└─────────────────────────────────────────┘
```

点击整张卡片跳转到 `/user/:id`。

## 3. 文件

| 文件 | 操作 |
|------|------|
| `frontend/src/components/ReputationBadges.vue` | 新建 |
| `frontend/src/components/UserCard.vue` | 新建 |
| `frontend/src/pages/UserPage.vue` | 声誉区改用 ReputationBadges |
| `frontend/src/pages/SchoolsPage.vue` | 用户列表改用 UserCard |
| `frontend/src/locales/en-US.json` | 加 rep.* 键 |
| `frontend/src/locales/zh-CN.json` | 加中文键 |

## 4. 不翻译

四维标签（Professionalism, Objectivity, Collaboration, Readability）保持英文。
