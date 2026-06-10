# PeerPedia Design System — Master

> **LOGIC:** When building a new page/component, follow this file.
> Page-specific overrides live in `design-system/pages/[page-name].md`.
> If no override exists, this Master is the source of truth.

**Project:** PeerPedia (知诸网)
**Updated:** 2026-06-10
**Base Style:** Dark Mode (GitHub-inspired academic editor)
**Icon Set:** Lucide (lucide-vue-next)

---

## Color Palette

All colors verified against DESIGN.en.md and main.css.

| Token | Hex | Tailwind | Usage |
|---|---|---|---|
| Page BG | `#0d1117` | `bg-page` | Root page background |
| Card BG | `#161b22` | `bg-card` | Cards, modals, panels |
| Hover BG | `#21262d` | — | Button/card hover states |
| Divider | `#30363d` | `border-divider` | Borders, separators |
| Text Primary | `#e6edf3` | `text-ink` | Body text, headings |
| Text Muted | `#6e7681` | `text-ink-muted` | Secondary text, placeholders |
| Accent | `#7b8c9e` | `text-accent` / `bg-accent` | Links, active states, primary actions |
| Accent Hover | `#8b9cae` | `hover:text-accent-hover` | Hover brightening |
| Success | `#238636` | `text-success` / `bg-success` | Positive indicators |
| Danger | `#d73a49` | `text-danger` / `bg-danger` | Delete, destructive actions |
| Warning | `#d29922` | — | Warnings (rarely used) |

### Color Rules

- **NEVER hardcode hex values** in components. Use Tailwind tokens: `text-danger` not `#d73a49`.
- **Danger = `text-danger`** for text, **`bg-danger`** for solid backgrounds. `bg-danger/10` for subtle hover.
- **Accent = `text-accent` / `bg-accent`**. `bg-accent/10` for subtle hover.
- **Backgrounds**: Page = `#0d1117`, Cards = `#161b22`, Code/editor = `#0d1117`.
- **Contrast**: Text on page BG = 13:1 (exceeds WCAG AAA). Muted text = 5:1 (meets WCAG AA).

---

## Typography

| Role | Font | CSS |
|---|---|---|
| Body | Inter | `font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif` |
| Headings | EB Garamond | `font-family: 'EB Garamond', 'Noto Serif SC', 'STSong', Georgia, serif` |
| Code | JetBrains Mono | `font-family: 'JetBrains Mono', 'Fira Code', monospace` |
| Chinese Body | — | Falls back to PingFang SC, Noto Serif SC (embedded in font stacks) |

**Google Fonts Import (already in main.css):**
```css
@import url('https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
```

### Typography Rules

- **Headings**: EB Garamond, semibold, tight tracking. `font-heading font-semibold tracking-tight`.
- **Body**: Inter, 16px minimum on mobile. `text-sm` (14px) for secondary text only.
- **Code**: JetBrains Mono, `text-sm` with `leading-relaxed`.
- **Line-height**: 1.5-1.75 for body text. `leading-relaxed` class.
- **Line-length**: Max 75 chars per line (prose). `max-w-prose` for article body.

---

## Spacing

Tailwind default scale. Key conventions:

| Context | Spacing |
|---|---|
| Card padding | `p-4` to `p-6` |
| Modal padding | `p-6` |
| Icon button | `w-7 h-7` or `w-8 h-8` |
| Button text+icon | `px-2.5 py-1` (small), `px-4 py-2.5` (normal) |
| Section gap | `mb-6` |
| Toolbar | `px-4 py-2` |
| Page content | `max-w-content` (defined in tailwind.config.ts) |

---

## Component Patterns

### Buttons

```
Icon-only:    w-7 h-7 rounded-lg text-ink-muted hover:text-ink hover:bg-[#21262d] transition-colors duration-200
Primary:      bg-accent text-[#0d1117] font-bold rounded-lg hover:brightness-110
Danger-solid: bg-danger text-white font-semibold rounded hover:brightness-110
Ghost:        text-ink-muted hover:text-ink hover:bg-[#21262d]
Disabled:     opacity-30 cursor-not-allowed
```

### Cards

```
.card            → bg-card border border-divider rounded-card shadow-card
.card-interactive → .card + cursor-pointer hover:shadow-card-hover
```

### Modals

```
Overlay:  fixed inset-0 z-50 bg-black/50 backdrop-blur-sm
Dialog:   bg-card border border-divider rounded-xl shadow-2xl p-6
Entrance: animate-fade-in
Dismiss:  click backdrop → close, Esc → close, X button → close
A11y:     role="dialog" aria-modal="true"
```

### Delete/Destructive Actions

```
Trigger:  icon-only (Trash2), text-ink-muted hover:text-danger hover:bg-danger/10
Confirm:  "Confirm?" label + bg-danger text-white button + Cancel text button
Guard:    Two-step confirmation REQUIRED before any destructive action
```

### Editor Layout

```
Toolbar:     flex items-center justify-between px-4 py-2 bg-card border border-divider
Split pane:  draggable w-1 bg-divider cursor-col-resize hover:bg-accent/50
Editor:      flex-1 bg-[#0d1117] font-mono text-sm
Preview:     flex-1 overflow-y-auto bg-[#0d1117] p-4
Bottom bar:  flex items-center justify-between px-4 py-1.5 bg-card border text-xs
```

---

## Interaction Patterns

| Pattern | Specification |
|---|---|
| Hover transition | `transition-colors duration-200` (150-300ms range) |
| Focus ring | `outline-2 outline-offset-2 outline-accent rounded` on `:focus-visible` |
| Disabled state | `opacity-50 cursor-not-allowed` (buttons), `opacity-30` (subtle) |
| Loading state | Spinner `animate-spin` + dimmed text |
| Empty state | Icon + message + hint. Card centered, muted tones. Never "No items found." alone |
| Error state | Red text (danger), actionable retry button if recoverable |
| Success feedback | Brief "Saved" text, auto-dismiss 2s |
| Tooltip | `data-tooltip` attribute → CSS `::after` on hover, 50ms delay |

---

## Icons

**Set:** Lucide (lucide-vue-next). ALL icons from this set. Never mix icon libraries.

| Usage | Icon | Size |
|---|---|---|
| Navigation | `Search`, `Bookmark`, `FilePlus`, `User` | `w-4 h-4` |
| Actions (toolbar) | `Save`, `Play`, `Eye`, `EyeOff`, `Send` | `w-4 h-4` |
| Actions (card) | `Bookmark`, `BookmarkCheck`, `Edit`, `Trash2`, `GitFork`, `History` | `w-3.5 h-3.5` |
| Status | `GitCommitHorizontal`, `Clock`, `MessageSquare`, `Users` | `w-3 h-3` |
| Format | `FileText` (Markdown), `FileCode` (Typst) | `w-5 h-5` (modal) |
| Modal close | `X` | `w-4 h-4` |
| Download | `FileCode` (source), `FileDown` (compiled), `Package` (repo) | `w-4 h-4` |
| Delete | `Trash2` | `w-3.5 h-3.5` |

---

## Anti-Patterns (DO NOT USE)

- ❌ **Hardcoded hex colors** — use Tailwind tokens (`text-danger`, `bg-accent`, `text-ink-muted`)
- ❌ **Emojis as icons** — always Lucide SVG
- ❌ **Scale transforms on hover** — use color/opacity transitions only (prevents layout shift)
- ❌ **Instant state changes** — always `transition-colors duration-200`
- ❌ **Missing cursor-pointer** — all clickable elements need it
- ❌ **Placeholder-as-label** — form inputs need visible labels
- ❌ **Low contrast text** — muted = `#6e7681` minimum (4.5:1 on `#0d1117`)
- ❌ **Silent destructive actions** — always confirm before delete

---

## Pre-Delivery Checklist

- [ ] All colors use Tailwind tokens (no hardcoded hex)
- [ ] All icons from Lucide set
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with `transition-colors duration-200`
- [ ] Focus states visible for keyboard nav (`:focus-visible`)
- [ ] Delete actions have two-step confirmation
- [ ] Modals have Esc/backdrop/X dismiss + focus trap
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive at 375px, 768px, 1024px
- [ ] No horizontal scroll on mobile
