# ScoreBadges Hover Expand 设计

## 目标

改造 `ScoreBadges.vue` 组件：
1. **缩小**默认显示体积
2. **hover 动画**：光标移到字母上，字母展开为全称（`O` → `Originality`）

## 交互

```
默认:   O:5  R:5  C:4  P:4  I:5    ← 紧凑
       ─────────────────────────
hover O:  Originality:5  R:5  C:4  ← 当前展开，其余保持
         └─ 平滑滑出 ─┘
```

## 实现方案

每个维度一个 `<span class="score-dim">`，内含两个子元素：

```html
<span class="score-dim">
  <span class="short">O</span>
  <span class="full">riginality</span>
  <span>:5</span>
</span>
```

- `.short` — 始终可见
- `.full` — `max-width: 0; overflow: hidden; white-space: nowrap`，hover 时 `max-width: 100px`
- CSS `transition: max-width 0.3s ease` 实现平滑展开
- `.score-dim:hover .full` 触发展开

## 颜色

- 第一个维度（originality）高亮 `text-accent font-semibold`
- 其余 `text-ink-muted`
- hover 时不改变颜色

## 风格

- 字号：`text-[11px]`（比 `text-xs` 更紧凑）
- 字体：`font-mono`（数字对齐）
- 间距：`gap-x-2.5`

## 引用处

| 页面 | 当前使用 | 改动 |
|------|---------|------|
| ArticlePage 顶部 | `<ScoreBadges :score="article.score" :highlight-first="true" class="text-xs font-mono" />` | 自动生效 |
| ArticleCard | `<ScoreBadges :score="article.score" :highlight-first="true" />` | 自动生效 |
| HistoryPage | `<ScoreBadges :score="commit.score" />` | 自动生效 |
| ArticlePage 评审列表 | 内联 `v-for="dim in SCORE_DIMS"` | 改为 `<ScoreBadges :score="review.scores" />` |

## 不翻译

评分标签（Originality, Rigor, Completeness, Pedagogy, Impact）保持英文。

## 文件

- 修改: `frontend/src/components/ScoreBadges.vue`
- 修改: `frontend/src/pages/ArticlePage.vue`（评审列表改用 ScoreBadges）
