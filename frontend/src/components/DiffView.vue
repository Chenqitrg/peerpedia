<!-- SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors -->
<!-- SPDX-License-Identifier: CC-BY-NC-SA-4.0 -->

<script setup lang="ts">
import { computed } from 'vue'
import { sanitizeHtml } from '../utils/sanitize'

export interface DiffLine {
  line_type: 'add' | 'del' | 'ctx'
  content: string
  old_lineno: number | null
  new_lineno: number | null
}

export interface DiffHunk {
  old_start: number
  old_lines: number
  new_start: number
  new_lines: number
  header: string
  lines: DiffLine[]
}

export interface DiffResult {
  files: string[]
  hunks: DiffHunk[]
}

const props = defineProps<{
  diff: DiffResult | null
}>()

const hasContent = computed(() => props.diff && props.diff.hunks.length > 0)
const totalAdditions = computed(() => {
  if (!props.diff) return 0
  return props.diff.hunks.reduce((sum, h) =>
    sum + h.lines.filter(l => l.line_type === 'add').length, 0
  )
})
const totalDeletions = computed(() => {
  if (!props.diff) return 0
  return props.diff.hunks.reduce((sum, h) =>
    sum + h.lines.filter(l => l.line_type === 'del').length, 0
  )
})

// ── Word-level diff ──────────────────────────────────────────────────

/** Split text into tokens: words, whitespace, and punctuation are separate. */
function tokenize(text: string): string[] {
  return text.split(/(\s+)/).filter(Boolean)
}

/** Compute LCS length table for two token arrays. */
function lcsTable(a: string[], b: string[]): number[][] {
  const dp: number[][] = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0))
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      dp[i][j] = a[i - 1] === b[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1])
    }
  }
  return dp
}

/** Backtrack LCS table to find which tokens in `a` are NOT in the LCS (i.e., deleted). */
function backtrackDeletions(a: string[], b: string[], dp: number[][]): Set<number> {
  const deleted = new Set<number>()
  let i = a.length, j = b.length
  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) { i--; j-- }
    else if (dp[i - 1][j] >= dp[i][j - 1]) { deleted.add(i - 1); i-- }
    else { j-- }
  }
  while (i > 0) { deleted.add(i - 1); i-- }
  return deleted
}

/** Backtrack LCS table to find which tokens in `b` are NOT in the LCS (i.e., inserted). */
function backtrackInsertions(a: string[], b: string[], dp: number[][]): Set<number> {
  const inserted = new Set<number>()
  let i = a.length, j = b.length
  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) { i--; j-- }
    else if (dp[i - 1][j] >= dp[i][j - 1]) { i-- }
    else { inserted.add(j - 1); j-- }
  }
  while (j > 0) { inserted.add(j - 1); j-- }
  return inserted
}

/** Render deleted line content with word-level highlighting by comparing against
 *  the corresponding added line. Returns HTML string. */
function highlightDeletedWords(delContent: string, addContent: string | null): string {
  if (!addContent) return `<span class="diff-word-del">${escapeHtml(delContent)}</span>`
  const delTokens = tokenize(delContent)
  const addTokens = tokenize(addContent)
  const dp = lcsTable(delTokens, addTokens)
  const deleted = backtrackDeletions(delTokens, addTokens, dp)
  // Only apply word-level highlighting when there's a meaningful partial diff
  // (at least one token matches and at least one token differs)
  if (deleted.size === 0) return escapeHtml(delContent)
  return delTokens.map((t, i) =>
    deleted.has(i) ? `<span class="diff-word-del">${escapeHtml(t)}</span>` : escapeHtml(t)
  ).join('')
}

/** Render added line content with word-level highlighting by comparing against
 *  the corresponding deleted line. Returns HTML string. */
function highlightAddedWords(addContent: string, delContent: string | null): string {
  if (!delContent) return `<span class="diff-word-add">${escapeHtml(addContent)}</span>`
  const addTokens = tokenize(addContent)
  const delTokens = tokenize(delContent)
  const dp = lcsTable(delTokens, addTokens)
  const inserted = backtrackInsertions(delTokens, addTokens, dp)
  // Only apply word-level highlighting when there's a meaningful partial diff
  if (inserted.size === 0) return escapeHtml(addContent)
  return addTokens.map((t, i) =>
    inserted.has(i) ? `<span class="diff-word-add">${escapeHtml(t)}</span>` : escapeHtml(t)
  ).join('')
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** Check if a line is a git "no newline" marker that should be hidden. */
function isNoNewline(line: DiffLine): boolean {
  return line.content.startsWith('\\ ') && line.content.includes('No newline')
}

/** Process hunk lines to produce word-highlighted HTML content.
 *  Pairs consecutive del/add runs for word-level diff. */
function processedHunks(hunks: DiffHunk[]): ProcessedHunk[] {
  return hunks.map(hunk => {
    // Filter out git noise lines that break del↔add pairing
    const lines = hunk.lines.filter(l => !isNoNewline(l))
    if (lines.length === 0) return { ...hunk, lines: [] }
    const processed: ProcessedHunk['lines'] = lines.map(l => ({
      ...l,
      displayContent: escapeHtml(l.content),
    }))

    // Pair consecutive del and add runs for word highlighting
    let i = 0
    while (i < lines.length) {
      if (lines[i].line_type === 'del') {
        // Collect consecutive deletions
        const delStart = i
        while (i < lines.length && lines[i].line_type === 'del') i++
        const delEnd = i
        // Collect consecutive additions
        const addStart = i
        while (i < lines.length && lines[i].line_type === 'add') i++
        const addEnd = i

        // Pair up deletions with additions (one-to-one within the run)
        const delCount = delEnd - delStart
        const addCount = addEnd - addStart
        const pairCount = Math.min(delCount, addCount)
        for (let j = 0; j < pairCount; j++) {
          const delLine = lines[delStart + j]
          const addLine = lines[addStart + j]
          processed[delStart + j].displayContent = highlightDeletedWords(
            delLine.content, addLine.content
          )
          processed[addStart + j].displayContent = highlightAddedWords(
            addLine.content, delLine.content
          )
        }
        // Unpaired deletions: highlight all words
        for (let j = pairCount; j < delCount; j++) {
          processed[delStart + j].displayContent = highlightDeletedWords(
            lines[delStart + j].content, null
          )
        }
        // Unpaired additions: highlight all words
        for (let j = pairCount; j < addCount; j++) {
          processed[addStart + j].displayContent = highlightAddedWords(
            lines[addStart + j].content, null
          )
        }
      } else {
        i++
      }
    }

    return {
      ...hunk,
      lines: processed,
    }
  })
}

interface ProcessedLine extends DiffLine {
  displayContent: string
}

interface ProcessedHunk {
  old_start: number
  old_lines: number
  new_start: number
  new_lines: number
  header: string
  lines: ProcessedLine[]
}

const processedHunksList = computed(() => {
  if (!props.diff) return []
  return processedHunks(props.diff.hunks)
})
</script>

<template>
  <div v-if="!diff" class="text-sm text-ink-muted text-center py-8">
    Select two commits to compare
  </div>
  <div v-else-if="!hasContent" class="text-sm text-ink-muted text-center py-8">
    No differences — identical content
  </div>
  <div v-else class="diff-view font-mono text-xs leading-relaxed">
    <!-- Summary bar -->
    <div class="flex items-center gap-3 px-3 py-1.5 bg-[#21262d] rounded-t-lg border-b border-divider text-xs">
      <span>{{ props.diff?.files.length ?? 0 }} file(s) changed</span>
      <span class="text-success">+{{ totalAdditions }}</span>
      <span class="text-danger">-{{ totalDeletions }}</span>
    </div>

    <!-- Hunks -->
    <div
      v-for="(hunk, hi) in processedHunksList"
      :key="hi"
      class="border-b border-divider last:border-b-0"
    >
      <!-- Hunk header -->
      <div class="px-3 py-1 bg-card text-ink-muted text-xs font-mono border-b border-divider">
        @@ -{{ hunk.old_start }},{{ hunk.old_lines }} +{{ hunk.new_start }},{{ hunk.new_lines }} @@
        <span v-if="hunk.header" class="ml-2 text-ink-muted/60">{{ hunk.header }}</span>
      </div>

      <!-- Lines -->
      <div
        v-for="(line, li) in hunk.lines"
        :key="li"
        class="flex px-3 hover:bg-white/[0.02]"
        :class="{
          'bg-success/10': line.line_type === 'add',
          'bg-danger/10': line.line_type === 'del',
        }"
      >
        <!-- Line numbers -->
        <span class="inline-block w-10 text-right text-ink-muted/40 select-none shrink-0">
          {{ line.old_lineno ?? '' }}
        </span>
        <span class="inline-block w-px mx-2 bg-divider/30" />
        <span class="inline-block w-10 text-right text-ink-muted/40 select-none shrink-0">
          {{ line.new_lineno ?? '' }}
        </span>
        <!-- Prefix + content -->
        <span class="inline-block w-4 text-center shrink-0 select-none font-bold"
          :class="{
            'text-success': line.line_type === 'add',
            'text-danger': line.line_type === 'del',
            'text-ink-muted/30': line.line_type === 'ctx',
          }"
        >
          {{ line.line_type === 'add' ? '+' : line.line_type === 'del' ? '-' : ' ' }}
        </span>
        <span
          class="whitespace-pre-wrap break-all flex-1 pl-1"
          :class="{
            'text-success': line.line_type === 'add',
            'text-danger': line.line_type === 'del',
            'text-ink-muted': line.line_type === 'ctx',
          }"
          v-html="sanitizeHtml(line.displayContent)"
        />
      </div>
    </div>
  </div>
</template>
