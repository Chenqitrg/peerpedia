# 实施计划索引

> 原完整计划：[implementation-plan-2026-06-10.md](../implementation-plan-2026-06-10.md)  
> 所有 Step **互相解耦**——每个 Step 只触碰自己的文件，可以按任意顺序执行。

## 建议执行顺序（按风险从低到高）

| # | 文件 | 内容 | 文件数 | 风险 |
|---|---|---|---|---|
| 1 | [step-7-color-hardcoding-cleanup.md](step-7-color-hardcoding-cleanup.md) | 组件颜色硬编码清理 | 8 | 低——全部是单行 token 替换 |
| 2 | [step-6-tab-drawer-design.md](step-6-tab-drawer-design.md) | Tab 抽屉设计对齐 | 1 | 低——scoped CSS + 函数替换 |
| 3 | [step-2-typst-svg-dark-theme.md](step-2-typst-svg-dark-theme.md) | Typst SVG 暗色主题 | 4 | 低——纯 CSS + 新 utility |
| 4 | [step-3-format-choice-modal.md](step-3-format-choice-modal.md) | 格式选择弹窗 | 3 | 中——新增 UI 组件 |
| 5 | [step-1-bookmark-self-rejection.md](step-1-bookmark-self-rejection.md) | 自收藏拒绝（后端 + 前端） | 2 | 中——涉及后端 API |
| 6 | [step-4-bookmark-guards-and-fix.md](step-4-bookmark-guards-and-fix.md) | 收藏守卫 + Bug 修复 | 4 | 中——修复持久化 bug |
| 7 | [step-5-delete-button-unified.md](step-5-delete-button-unified.md) | DeleteButton 统一组件 | 3 | 中——新建组件 + 清理死代码 |
| — | [step-final-verification.md](step-final-verification.md) | 最终验证 | — | 全部 Step 完成后运行 |

## 每个 Step 文件的结构

```
前情提要（共用）
↓
前置准备（共用）
↓
Step 专属内容（问题 → 修改 → 验证）
```

每个文件自包含——打开就能执行，不需要来回翻主计划。
