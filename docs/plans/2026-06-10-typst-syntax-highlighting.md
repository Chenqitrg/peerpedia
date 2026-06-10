# Typst Syntax Highlighting in CodeMirror 6 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the plain `<textarea>` used for Typst editing with CodeMirror 6 + `codemirror-lang-typst` (WASM-powered syntax highlighting using the official `typst-syntax` crate).

**Architecture:** `CodeEditor.vue` becomes the single source of truth for format-aware editing. Currently it only handles Markdown with CodeMirror and falls back to a slot for Typst. After this change, it renders CodeMirror unconditionally, selecting `markdown()` or `typst()` extension based on the `format` prop. EditorPage.vue drops its redundant `v-if="format === 'markdown'"` + `<textarea v-else>` dual-path structure.

**Tech Stack:** Vue 3 + CodeMirror 6 + `codemirror-lang-typst` (v0.4.0) + vitest + @vue/test-utils

---

## Pre-flight Checklist

- [ ] Current branch is `main` and clean (`git status` shows no modified files)
- [ ] `cd frontend && npm test -- --run` passes all 448 tests
- [ ] Node.js version ≥ 18 (required by codemirror-lang-typst WASM)

---

## Task 1: Install codemirror-lang-typst dependency

**Files:**
- Modify: `frontend/package.json` (dependency added by npm)

- [ ] **Step 1: Install the package**

```bash
cd /Users/chenqimeng/Projects/peerpedia/frontend && npm install codemirror-lang-typst
```

- [ ] **Step 2: Verify the package installed correctly**

```bash
ls node_modules/codemirror-lang-typst/dist/index.js
# Expected: file exists

node -e "const t = require('codemirror-lang-typst'); console.log(typeof t.typst)"
# Expected: "function"
```

- [ ] **Step 3: Check package.json was updated**

```bash
grep "codemirror-lang-typst" package.json
# Expected: "codemirror-lang-typst": "^0.4.0"
```

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: install codemirror-lang-typst v0.4.0"
```

---

## Task 2: Update CodeEditor.vue — support both Markdown and Typst

**Files:**
- Modify: `frontend/src/components/CodeEditor.vue` (entire file)

### Current state (before edit — read from `frontend/src/components/CodeEditor.vue`)

The file currently has these key sections:
- **Line 4**: `import { markdown } from '@codemirror/lang-markdown'` — only Markdown extension
- **Line 21-25**: `extensions` computed — always pushes `markdown()`, no format branching
- **Line 38-51**: Template — `v-if="format === 'markdown'"` shows CodeMirror, `v-else` renders `<slot name="typst-fallback" />`

### Target state (after edit)

The file will:
- Import `typst` from the new package
- Branch `extensions` on `props.format` — `typst()` for Typst, `markdown()` for Markdown
- Remove the `v-if` / slot duality — always render CodeMirror
- Accept `placeholder` prop and forward it to CodeMirror

- [ ] **Step 1: Read the current file to confirm you have the latest version**

```bash
cat /Users/chenqimeng/Projects/peerpedia/frontend/src/components/CodeEditor.vue
```

- [ ] **Step 2: Replace the entire file content**

Write the following content to `/Users/chenqimeng/Projects/peerpedia/frontend/src/components/CodeEditor.vue`:

```vue
<script setup lang="ts">
import { shallowRef, computed } from 'vue'
import { Codemirror } from 'vue-codemirror'
import { markdown } from '@codemirror/lang-markdown'
import { typst } from 'codemirror-lang-typst'
import { oneDark } from '@codemirror/theme-one-dark'
import { EditorView } from 'codemirror'
import type { Extension } from '@codemirror/state'

const props = defineProps<{
  modelValue: string
  format: 'markdown' | 'typst'
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const codemirrorView = shallowRef<EditorView>()

const extensions = computed<Extension[]>(() => {
  const exts: Extension[] = [oneDark]
  if (props.format === 'typst') {
    exts.push(typst())
  } else {
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
  <div class="flex-1 w-full font-mono cm-wrapper">
    <Codemirror
      :model-value="modelValue"
      :extensions="extensions"
      :placeholder="placeholder"
      :indent-with-tab="true"
      :tab-size="2"
      @ready="onReady"
      @update:model-value="onUpdate"
    />
  </div>
</template>

<style>
/* Override oneDark background to match app page bg */
.cm-wrapper .cm-editor {
  background: #0d1117;
}
.cm-wrapper .cm-editor .cm-scroller {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}
</style>
```

- [ ] **Step 3: Verify the file was written correctly**

```bash
grep "codemirror-lang-typst" /Users/chenqimeng/Projects/peerpedia/frontend/src/components/CodeEditor.vue
# Expected: import { typst } from 'codemirror-lang-typst'

grep "typst()" /Users/chenqimeng/Projects/peerpedia/frontend/src/components/CodeEditor.vue
# Expected: exts.push(typst())

grep "slot" /Users/chenqimeng/Projects/peerpedia/frontend/src/components/CodeEditor.vue
# Expected: (no output — the slot is gone)
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/CodeEditor.vue
git commit -m "feat: add Typst syntax highlighting via codemirror-lang-typst

Replace format-conditional slot/textrea with unified CodeMirror rendering.
Markdown uses markdown() extension, Typst uses typst() (WASM parser).
Remove slot fallback — CodeEditor handles both formats internally."
```

---

## Task 3: Write xspec tests for CodeEditor.vue (Typst mode)

**Files:**
- Modify: `frontend/src/components/__tests__/CodeEditor.test.ts` (append new tests, update existing)

### Current test state

`CodeEditor.test.ts` has ~50 lines with these tests:
1. `renders a CodeMirror editor element` — mounts with `format: 'markdown'`
2. `displays initial modelValue content`
3. `updates displayed content when modelValue changes`
4. `exposes codemirrorView via defineExpose`
5. `renders Typst fallback slot when format is typst` — THIS TEST WILL FAIL after Task 2

- [ ] **Step 1: Read the current Typst fallback test (lines ~50-60)**

```bash
grep -n "typst\|Typst" /Users/chenqimeng/Projects/peerpedia/frontend/src/components/__tests__/CodeEditor.test.ts
```

- [ ] **Step 2: Replace the old Typst slot test with new xspec tests**

Find the test `renders Typst fallback slot when format is typst` and its entire `it()` block. Replace it and append the following new tests AFTER the last existing `});` (before the closing `})` of the describe block).

**Step 2a: Find and delete the old Typst slot test.** The old test looks like:

```typescript
  it('renders Typst fallback slot when format is typst', () => {
    // ... about 10 lines
  });
```

Delete the entire `it('renders Typst fallback slot...'` block.

**Step 2b: Append these new tests before the final `})` of the describe block:**

```typescript
  // ── Typst format (post codemirror-lang-typst) ─────────────────────

  it('renders CodeMirror for Typst format, NOT textarea', () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '= Title', format: 'typst' },
    })
    expect(wrapper.find('.cm-editor').exists()).toBe(true)
    expect(wrapper.find('textarea').exists()).toBe(false)
  })

  it('renders CodeMirror for Markdown format (regression check)', () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '# Title', format: 'markdown' },
    })
    expect(wrapper.find('.cm-editor').exists()).toBe(true)
    expect(wrapper.find('textarea').exists()).toBe(false)
  })

  it('displays Typst content in CodeMirror editor', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '= Introduction', format: 'typst' },
    })
    await nextTick()
    const editorEl = wrapper.find('.cm-content')
    expect(editorEl.exists()).toBe(true)
    expect(editorEl.text()).toContain('= Introduction')
  })

  it('exposes codemirrorView for Typst format', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '', format: 'typst' },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.codemirrorView).toBeDefined()
    expect(vm.codemirrorView.state).toBeDefined()
    // Confirm the doc content is accessible
    expect(vm.codemirrorView.state.doc.toString()).toBe('')
  })

  it('updates CodeMirror when switching format from Markdown to Typst', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: 'some content', format: 'markdown' },
    })
    await flushPromises()
    await wrapper.setProps({ format: 'typst' as const, modelValue: '= New Typst' })
    await flushPromises()
    await nextTick()
    const editorEl = wrapper.find('.cm-content')
    expect(editorEl.exists()).toBe(true)
    expect(editorEl.text()).toContain('= New Typst')
  })
```

- [ ] **Step 3: Verify the test file is valid**

```bash
cd /Users/chenqimeng/Projects/peerpedia/frontend && npx vitest run src/components/__tests__/CodeEditor.test.ts --reporter=verbose
# Expected: 7-8 tests total, ALL pass (old Typst slot test is gone, replaced by new ones)
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/__tests__/CodeEditor.test.ts
git commit -m "test: add xspec tests for Typst CodeMirror integration

SPEC-HL-1/2/3: Verify CodeMirror renders for Typst, not textarea.
Remove old 'renders Typst fallback slot' test (slot no longer exists).
Add format-switch regression test."
```

---

## Task 4: Update EditorPage.vue — remove textarea fallback

**Files:**
- Modify: `frontend/src/pages/EditorPage.vue` (lines 679-696)

### Context

`EditorPage.vue` currently has a redundant format branch: it checks `v-if="format === 'markdown'"` to render CodeEditor vs `<textarea>`. After Task 2, CodeEditor handles both formats internally, so EditorPage should just render `<CodeEditor>` unconditionally.

### Current code (lines 679-696)

```html
        <!-- CodeMirror for Markdown -->
        <CodeEditor
          v-if="format === 'markdown'"
          v-model="content"
          :format="format"
          :placeholder="'# Title\n\nWrite your article in Markdown...'"
          class="flex-1 w-full"
        />
        <!-- Plain textarea for Typst -->
        <textarea
          v-else
          v-model="content"
          class="flex-1 w-full bg-[#0d1117] text-ink font-mono text-sm leading-relaxed
                 p-4 resize-none border-none focus:outline-none
                 placeholder:text-ink-muted/30"
          placeholder="= Title\n\nWrite your article in Typst..."
          spellcheck="false"
        />
```

### Target code

```html
        <CodeEditor
          v-model="content"
          :format="format"
          :placeholder="format === 'markdown'
            ? '# Title\n\nWrite your article in Markdown...'
            : '= Title\n\nWrite your article in Typst...'"
          class="flex-1 w-full"
        />
```

- [ ] **Step 1: Delete lines 679-696 and insert the replacement**

Remove this exact block:
```
        <!-- CodeMirror for Markdown -->
        <CodeEditor
          v-if="format === 'markdown'"
          v-model="content"
          :format="format"
          :placeholder="'# Title\n\nWrite your article in Markdown...'"
          class="flex-1 w-full"
        />
        <!-- Plain textarea for Typst -->
        <textarea
          v-else
          v-model="content"
          class="flex-1 w-full bg-[#0d1117] text-ink font-mono text-sm leading-relaxed
                 p-4 resize-none border-none focus:outline-none
                 placeholder:text-ink-muted/30"
          placeholder="= Title\n\nWrite your article in Typst..."
          spellcheck="false"
        />
```

Replace with:
```html
        <CodeEditor
          v-model="content"
          :format="format"
          :placeholder="format === 'markdown'
            ? '# Title\n\nWrite your article in Markdown...'
            : '= Title\n\nWrite your article in Typst...'"
          class="flex-1 w-full"
        />
```

- [ ] **Step 2: Verify no other textarea references remain in EditorPage.vue**

```bash
grep -n "textarea" /Users/chenqimeng/Projects/peerpedia/frontend/src/pages/EditorPage.vue
# Expected: (no output — all textarea references removed)
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/EditorPage.vue
git commit -m "refactor: remove EditorPage textarea fallback for Typst

CodeEditor.vue now handles both formats internally. EditorPage no longer
needs a v-if/v-else branch to choose between CodeMirror and textarea.
Placeholder is format-aware via a ternary on the :placeholder prop.

Net change: -11 lines of textarea template, +2 lines of format-aware placeholder."
```

---

## Task 5: Update EditorPage tests — remove textarea assertions

**Files:**
- Modify: `frontend/src/pages/__tests__/EditorPage.test.ts` (lines 89-103, 629-649)

### Tests to change

**A. Lines 89-103** — `uses format from route query param`

Old code:
```typescript
  it('uses format from route query param', async () => {
    // Typst mode → textarea visible (not CodeMirror)
    mockRoute.query = { new: '1', format: 'typst' }
    // Re-mock to pick up new query
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: {
        stubs: { 'router-link': RouterLinkStub, 'router-view': true },
      },
    })
    await flushPromises()
    expect(wrapper.find('textarea').exists()).toBe(true)
    // Reset
    mockRoute.query = {}
  })
```

New code:
```typescript
  it('uses format from route query param', async () => {
    // Typst mode → CodeMirror renders with Typst extension
    mockRoute.query = { new: '1', format: 'typst' }
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: {
        stubs: { 'router-link': RouterLinkStub, 'router-view': true },
      },
    })
    await flushPromises()
    expect(wrapper.find('.cm-editor').exists()).toBe(true)
    expect(wrapper.find('textarea').exists()).toBe(false)
    // Reset
    mockRoute.query = {}
  })
```

**B. Lines 629-634** — Markdown mode has no textarea

Old code (this test is now redundant — both formats use CodeMirror):
```typescript
    const vm = wrapper.vm as any
    // Markdown mode: format defaults to 'markdown', no textarea in DOM
    expect(vm.format).toBe('markdown')
    const textareas = wrapper.findAll('textarea')
    expect(textareas.length).toBe(0)
```

Replace the textarea assertions with a CodeMirror assertion:
```typescript
    const vm = wrapper.vm as any
    // Both Markdown and Typst use CodeMirror (no textarea)
    expect(vm.format).toBe('markdown')
    const editor = wrapper.find('.cm-editor')
    expect(editor.exists()).toBe(true)
    const textareas = wrapper.findAll('textarea')
    expect(textareas.length).toBe(0)
```

**C. Lines 636-649** — `uses plain textarea for Typst mode`

Old entire test:
```typescript
  it('uses plain textarea for Typst mode', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    vm.format = 'typst'
    await flushPromises()
    const cm = wrapper.find('.cm-editor')
    expect(cm.exists()).toBe(false)
    const ta = wrapper.find('textarea')
    expect(ta.exists()).toBe(true)
  })
```

Replace with:
```typescript
  it('uses CodeMirror for Typst mode', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    vm.format = 'typst'
    await flushPromises()
    const cm = wrapper.find('.cm-editor')
    expect(cm.exists()).toBe(true)
    const ta = wrapper.find('textarea')
    expect(ta.exists()).toBe(false)
  })
```

**D. Lines 86-87** — Comment update for `has title input` test

The comment `// Typst mode → textarea visible (not CodeMirror)` on line 90 is already handled in edit A above.

- [ ] **Step 1: Make all four edits above**

- [ ] **Step 2: Run the EditorPage tests**

```bash
cd /Users/chenqimeng/Projects/peerpedia/frontend && npx vitest run src/pages/__tests__/EditorPage.test.ts --reporter=verbose
# Expected: ALL tests pass. Specifically verify:
# - "uses format from route query param" → PASS
# - "uses CodeMirror for Typst mode" → PASS
# - The "no textarea" assertions → PASS
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/__tests__/EditorPage.test.ts
git commit -m "test: update EditorPage tests for Typst CodeMirror

- uses format from route query param: expect .cm-editor, not textarea
- uses plain textarea for Typst mode → uses CodeMirror for Typst mode
- Markdown mode test: assert .cm-editor exists
- All 3 changed tests check for CodeMirror, not textarea"
```

---

## Task 6: Full test suite verification

- [ ] **Step 1: Run the complete frontend test suite**

```bash
cd /Users/chenqimeng/Projects/peerpedia/frontend && npm test -- --run
```

Expected output:
```
 Test Files  42 passed (42)
      Tests  ~452 passed
```

The test count should increase by ~4 tests (new CodeEditor tests minus one removed Typst slot test, plus updated EditorPage tests).

- [ ] **Step 2: Verify no skipped or failing tests**

```bash
cd /Users/chenqimeng/Projects/peerpedia/frontend && npm test -- --run 2>&1 | grep -E "FAIL|pass|skip"
# Expected: 0 FAIL, 0 skip
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test: verify full suite passes after Typst CodeMirror integration"
```

---

## Task 7: Manual E2E verification (Tauri desktop)

- [ ] **Step 1: Launch the Tauri app**

```bash
cd /Users/chenqimeng/Projects/peerpedia/frontend && npm run tauri dev
```

- [ ] **Step 2: Test Typst syntax highlighting**

1. Click "New Article" in the navbar
2. Select "Typst" from the format picker modal
3. In the editor, type:
   ```
   = Introduction
   
   This is a #strong[bold] statement with $x^2 + y^2 = z^2$ math.
   
   #list(
     [First item],
     [Second item],
   )
   ```
4. Verify:
   - `= Introduction` has a distinct color (heading style)
   - `#strong[...]` and `#list(...)` have function-call highlighting
   - `$x^2 + y^2 = z^2$` math is colored differently from body text
   - The editor background matches the dark theme (`#0d1117`)
   - No textarea is visible anywhere

- [ ] **Step 3: Test Markdown editor (regression check)**

1. Create a new Markdown article
2. Type `# Heading\n\n**bold** and *italic* text with $E=mc^2$`
3. Verify Markdown syntax highlighting works as before
4. Verify the editor layout is identical to before (no visual regression)

- [ ] **Step 4: Test format persistence**

1. Create a Typst article, save it
2. Navigate away, then reopen it from UserPage
3. Verify the editor still shows CodeMirror with Typst highlighting
4. Repeat for a Markdown article — verify no regression

---

## Reversion Plan

If `codemirror-lang-typst` causes issues in production, revert with these exact steps:

```bash
# 1. Uninstall the package
cd frontend && npm uninstall codemirror-lang-typst

# 2. Revert CodeEditor.vue to the old slot-based template
git checkout HEAD~5 -- frontend/src/components/CodeEditor.vue

# 3. Revert EditorPage.vue to restore textarea
git checkout HEAD~4 -- frontend/src/pages/EditorPage.vue

# 4. Revert tests
git checkout HEAD~3 -- frontend/src/components/__tests__/CodeEditor.test.ts
git checkout HEAD~2 -- frontend/src/pages/__tests__/EditorPage.test.ts

# 5. Verify tests pass
cd frontend && npm test -- --run
```

---

## File Change Summary

| File | Change | Lines |
|------|--------|-------|
| `frontend/package.json` | + `codemirror-lang-typst` | +1 |
| `frontend/src/components/CodeEditor.vue` | Rewrite: add typst(), remove slot/v-if | -5, +8 template |
| `frontend/src/components/__tests__/CodeEditor.test.ts` | -1 old test, +5 new tests | +40 |
| `frontend/src/pages/EditorPage.vue` | Remove textarea, unify CodeEditor | -13, +4 |
| `frontend/src/pages/__tests__/EditorPage.test.ts` | Update 3 tests: textarea → CodeMirror | -8, +9 |

**Net:** 3 files removed, 1 file added. ~40 lines net increase. Zero architectural changes.
