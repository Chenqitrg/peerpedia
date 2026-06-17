# CodeMirror 6 Markdown Editor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the bare `<textarea>` in EditorPage.vue with CodeMirror 6 for Markdown editing (syntax highlighting, auto-indent, bracket matching). Typst mode keeps plain textarea for now.

**Architecture:** Add a `CodeEditor.vue` wrapper around `vue-codemirror` that handles Markdown mode. EditorPage.vue uses `<CodeEditor>` for Markdown and keeps `<textarea>` for Typst. Data flow: `v-model` on `content` ref, unchanged.

**Tech Stack:** Vue 3.4, `vue-codemirror` (v6), `@codemirror/lang-markdown`, `@codemirror/theme-one-dark`, Vitest, @vue/test-utils

---

### Task 1: Install CodeMirror 6 Dependencies

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install packages**

```bash
cd frontend && npm install codemirror @codemirror/lang-markdown @codemirror/theme-one-dark vue-codemirror
```

- [ ] **Step 2: Verify install**

```bash
ls frontend/node_modules/codemirror/package.json && echo "OK"
ls frontend/node_modules/vue-codemirror/package.json && echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add CodeMirror 6 dependencies (codemirror, lang-markdown, theme-one-dark, vue-codemirror)"
```

---

### Task 2: CodeEditor.vue — Markdown Mode

**Files:**
- Create: `frontend/src/components/CodeEditor.vue`
- Create: `frontend/src/components/__tests__/CodeEditor.test.ts`

- [ ] **Step 1: Write failing test for Markdown rendering**

```typescript
// frontend/src/components/__tests__/CodeEditor.test.ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CodeEditor from '../CodeEditor.vue'

describe('CodeEditor', () => {
  it('renders a CodeMirror editor element', () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '# Hello', format: 'markdown' },
    })
    // CodeMirror creates a div with class cm-editor
    const cm = wrapper.find('.cm-editor')
    expect(cm.exists()).toBe(true)
  })

  it('displays initial modelValue content', () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '# Test Content', format: 'markdown' },
    })
    const cm = wrapper.find('.cm-editor')
    expect(cm.exists()).toBe(true)
    // Content should be in the CM doc — check via the editor view
    const editorEl = wrapper.find('.cm-content')
    expect(editorEl.exists()).toBe(true)
    expect(editorEl.text()).toContain('Test Content')
  })

  it('emits update:modelValue on change', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: 'initial', format: 'markdown' },
    })
    const vm = wrapper.vm as any
    // Simulate a change via the codemirror view's dispatch
    const view = vm.codemirrorView
    expect(view).toBeDefined()
    view.dispatch({
      changes: { from: 0, to: 'initial'.length, insert: 'changed' },
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]).toEqual(['changed'])
  })

  it('exposes getCodemirrorView method', () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '', format: 'markdown' },
    })
    const vm = wrapper.vm as any
    expect(vm.codemirrorView).toBeDefined()
    expect(vm.codemirrorView.state).toBeDefined()
  })
})
```

- [ ] **Step 2: Run test — verify it FAILS (file not found)**

```bash
cd frontend && npx vitest run src/components/__tests__/CodeEditor.test.ts
```
Expected: FAIL — `Cannot find module '../CodeEditor.vue'`

- [ ] **Step 3: Write CodeEditor.vue**

```vue
<!-- frontend/src/components/CodeEditor.vue -->
<script setup lang="ts">
import { ref, watch, shallowRef, computed } from 'vue'
import { Codemirror } from 'vue-codemirror'
import { markdown } from '@codemirror/lang-markdown'
import { oneDark } from '@codemirror/theme-one-dark'
import type { EditorView } from 'codemirror'

const props = defineProps<{
  modelValue: string
  format: 'markdown' | 'typst'
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const codemirrorView = shallowRef<EditorView>()

const extensions = computed(() => {
  const exts: any[] = [oneDark]
  if (props.format === 'markdown') {
    exts.push(markdown())
  }
  return exts
})

function onReady(view: EditorView) {
  codemirrorView.value = view
}

function onUpdate(value: string) {
  emit('update:modelValue', value)
}

defineExpose({ codemirrorView })
</script>

<template>
  <Codemirror
    v-if="format === 'markdown'"
    :model-value="modelValue"
    :extensions="extensions"
    :placeholder="placeholder"
    :indent-with-tab="true"
    :tab-size="2"
    @ready="onReady"
    @update:model-value="onUpdate"
  />
  <!-- Typst fallback: parent handles with textarea -->
  <slot v-else name="typst-fallback" />
</template>
```

<!-- v-if on format: switching Markdown→Typst destroys the CodeMirror instance (loses cursor/undo). Authors rarely toggle formats — acceptable tradeoff. v-model content survives. -->

- [ ] **Step 4: Run tests — verify PASS**

```bash
cd frontend && npx vitest run src/components/__tests__/CodeEditor.test.ts
```
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/CodeEditor.vue frontend/src/components/__tests__/CodeEditor.test.ts
git commit -m "feat: add CodeEditor.vue with CodeMirror 6 Markdown support"
```

---

### Task 3: Integrate CodeEditor into EditorPage (Markdown Only)

**Files:**
- Modify: `frontend/src/pages/EditorPage.vue`
- Modify: `frontend/src/pages/__tests__/EditorPage.test.ts`

- [ ] **Step 1: Write regression test — textarea still used for Typst**

Add to `frontend/src/pages/__tests__/EditorPage.test.ts`:

```typescript
it('uses CodeMirror editor for Markdown mode', async () => {
  const EditorPage = (await import('../EditorPage.vue')).default
  const wrapper = mount(EditorPage, {
    global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
  })
  await new Promise(r => setTimeout(r, 100))
  // Default is markdown mode — should see .cm-editor
  const cm = wrapper.find('.cm-editor')
  expect(cm.exists()).toBe(true)
  // textarea should NOT be present (replaced by CodeMirror)
  const textareas = wrapper.findAll('textarea')
  expect(textareas.length).toBe(0)
})

it('uses plain textarea for Typst mode', async () => {
  const EditorPage = (await import('../EditorPage.vue')).default
  const wrapper = mount(EditorPage, {
    global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
  })
  await new Promise(r => setTimeout(r, 100))
  const vm = wrapper.vm as any
  vm.format = 'typst'
  await new Promise(r => setTimeout(r, 100))
  // Typst mode: no .cm-editor, should see textarea
  const cm = wrapper.find('.cm-editor')
  expect(cm.exists()).toBe(false)
  const ta = wrapper.find('textarea')
  expect(ta.exists()).toBe(true)
})
```

- [ ] **Step 2: Run — verify FAILS (no .cm-editor in DOM)**

```bash
cd frontend && npx vitest run src/pages/__tests__/EditorPage.test.ts -t "CodeMirror editor"
```
Expected: FAIL — `.cm-editor` not found

- [ ] **Step 3: Modify EditorPage.vue — replace textarea with CodeEditor (markdown path)**

In the template section, replace the current `<textarea>` (lines ~609-618) with a conditional:

```vue
<!-- Editor area (left) -->
<div
  class="flex flex-col"
  :style="{ width: showPreview ? `${splitRatio}%` : '100%' }"
>
  <!-- CodeMirror for Markdown -->
  <CodeEditor
    v-if="format === 'markdown'"
    v-model="content"
    :format="format"
    :placeholder="'# Title\n\nWrite your article in Markdown...'"
    class="flex-1 w-full"
  />
  <!-- Plain textarea for Typst (unchanged) -->
  <textarea
    v-else
    v-model="content"
    class="flex-1 w-full bg-[#0d1117] text-ink font-mono text-sm leading-relaxed
           p-4 resize-none border-none focus:outline-none
           placeholder:text-ink-muted/30"
    :placeholder="'= Title\n\nWrite your article in Typst...'"
    spellcheck="false"
  />
</div>
```

Add the import at the top of `<script setup>`:

```typescript
import CodeEditor from '../components/CodeEditor.vue'
```

- [ ] **Step 4: Run all EditorPage tests — verify existing tests still PASS + new ones PASS**

```bash
cd frontend && npx vitest run src/pages/__tests__/EditorPage.test.ts
```
Expected: All existing tests + 2 new tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/EditorPage.vue frontend/src/pages/__tests__/EditorPage.test.ts
git commit -m "feat: integrate CodeMirror 6 for Markdown editing in EditorPage"
```

---

### Task 4: Visual Verification — Run the App

**Files:** None (verification only)

- [ ] **Step 1: Start the frontend dev server**

```bash
cd frontend && npm run dev
```

- [ ] **Step 2: Open http://localhost:5173/edit — verify:**
  - [ ] CodeMirror editor renders with dark theme
  - [ ] Typing Markdown shows syntax highlighting (headings, bold, code, etc.)
  - [ ] Auto-indent works for lists and blockquotes
  - [ ] Bracket matching works for `[]`, `()`, `{}`
  - [ ] Split pane preview still works (compile button)
  - [ ] Save button works, content saved correctly
  - [ ] Switch to Typst — textarea appears (no CodeMirror)
  - [ ] Switch back to Markdown — CodeMirror reappears with content

- [ ] **Step 3: Run full frontend test suite**

```bash
cd frontend && npx vitest run
```
Expected: All tests PASS (existing count + 6 new)

---

### Task 5: Update Documentation

**Files:**
- Modify: `docs/DESIGN.en.md`

- [ ] **Step 1: Add editor mention to Phase 1.5 section**

In the Phase 1.5 table (around line 413), add:
```markdown
| P1 | CodeMirror 6 Markdown editor (syntax highlight, auto-indent) | ✅ |
```

- [ ] **Step 2: Commit**

```bash
git add docs/DESIGN.en.md
git commit -m "docs: note CodeMirror 6 Markdown editor in Phase 1.5"
```

---

## Verification Checklist

- [ ] `npm run dev` → editor renders CodeMirror for Markdown
- [ ] Syntax highlighting visible for headings, bold, code, lists
- [ ] Auto-indent works for lists and nested content
- [ ] `v-model` binding: save, compile, preview all read correct content
- [ ] `isClean` computed still works (save button disabled state)
- [ ] Typst mode falls back to textarea
- [ ] Format toggle (Markdown ↔ Typst) preserves content
- [ ] All existing EditorPage tests still pass (20 tests)
- [ ] New CodeEditor tests pass (4 tests)
- [ ] Full vitest suite passes

## NOT in Scope
- Typst syntax highlighting (Lezer grammar TBD)
- Autocomplete (will be separate PR)
- Line numbers / gutter
- Custom Markdown extensions (wikilinks, citations)
- Editor state preservation across format toggle (cursor/undo lost on v-if destroy; format switch is rare, acceptable tradeoff)

## What Already Exists
- `EditorPage.vue` — save/compile/preview/download flows all consume `content.value` via `v-model`. CodeEditor preserves this binding.
- `frontend/src/utils/markdown.ts` — Markdown compilation pipeline (marked + KaTeX). Untouched.
- `frontend/src/composables/useSplitPane.ts` — split pane resize. Untouched.
- `frontend/src/pages/__tests__/EditorPage.test.ts` — 20 existing tests, all must pass.

## Failure Modes
| Failure | Test covers? | Error handling? | User sees? |
|---------|-------------|-----------------|------------|
| CodeMirror JS fails to load (bundle corruption) | No | No — white screen | Silent blank editor |
| `computed` not imported → ReferenceError | Yes (would fail mount test) | No | Blank editor |
| Content > 1MB causes CM6 slowdown | No | No | Laggy typing |

## Implementation Tasks
- [ ] **T1 (P1, human: ~5min / CC: ~2min)** — CodeEditor.vue — fix `computed` import
  - Surfaced by: Architecture review — `computed` is not auto-imported by `<script setup>`, must explicitly import
  - Files: `frontend/src/components/CodeEditor.vue`
  - Verify: `npx vitest run src/components/__tests__/CodeEditor.test.ts`

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `/plan-eng-review` | Architecture & tests | 1 | CLEAR | 1 bug fixed (computed import), 1 tradeoff documented (v-if state loss), 3 minor test gaps noted |

- **VERDICT:** ENG CLEARED — ready to implement. 1 bug caught pre-implementation. 4 test gaps are low-priority (long docs, double-click, placeholder render, CM6 load failure) — none block ship.
