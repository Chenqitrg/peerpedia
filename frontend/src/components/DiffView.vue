<script setup lang="ts">
import { computed } from 'vue'

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
      <span>{{ props.diff.files.length }} file(s) changed</span>
      <span class="text-success">+{{ totalAdditions }}</span>
      <span class="text-danger">-{{ totalDeletions }}</span>
    </div>

    <!-- Hunks -->
    <div
      v-for="(hunk, hi) in props.diff.hunks"
      :key="hi"
      class="border-b border-divider last:border-b-0"
    >
      <!-- Hunk header -->
      <div class="px-3 py-1 bg-[#161b22] text-ink-muted text-xs font-mono border-b border-divider">
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
        >{{ line.content }}</span>
      </div>
    </div>
  </div>
</template>
