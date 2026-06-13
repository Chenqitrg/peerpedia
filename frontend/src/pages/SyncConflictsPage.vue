<!-- SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors -->
<!-- SPDX-License-Identifier: CC-BY-NC-SA-4.0 -->

<template>
  <div class="w-full max-w-2xl mx-auto pt-24 pb-8 px-4 animate-fade-in">
    <div class="flex items-center gap-3 mb-6">
      <AlertTriangle class="w-5 h-5 text-warning flex-shrink-0" />
      <div>
        <h1 class="font-heading font-semibold text-xl text-ink">{{ t('sync.conflictsTitle') }}</h1>
        <p class="text-sm text-ink-muted">{{ t('sync.conflictsSubtitle') }}</p>
      </div>
    </div>

    <!-- All resolved -->
    <div v-if="allResolved" class="text-center py-12">
      <CheckCircle class="w-12 h-12 text-success mx-auto mb-3" />
      <p class="text-ink text-lg mb-2">{{ t('sync.allResolved') }}</p>
      <p class="text-ink-muted text-sm">{{ t('sync.allResolvedHint') }}</p>
    </div>

    <!-- Item list -->
    <div v-else-if="currentItem" class="bg-card border border-divider rounded-xl p-6">
      <p class="text-ink-muted text-xs mb-4">{{ t('sync.progress', { current: currentIndex + 1, total: items.length }) }}</p>

      <div class="bg-[#0d1117] rounded-lg p-4 border border-divider mb-4">
        <div class="flex items-center gap-2 mb-1">
          <CloudUpload v-if="currentItem.op_type === 'push'" class="w-4 h-4 text-accent" />
          <Trash2 v-else class="w-4 h-4 text-danger" />
          <span class="text-ink-muted text-xs">
            {{ currentItem.op_type === 'push' ? t('sync.pendingUpload') : t('sync.pendingDelete') }}
            &mdash; {{ timeAgo(currentItem.updated_at) }}
          </span>
        </div>
        <p class="font-heading text-ink text-lg">{{ currentItem.title || t('sync.untitled') }}</p>
      </div>

      <div class="flex justify-end gap-3">
        <template v-if="currentItem.op_type === 'push'">
          <button class="px-4 py-2 text-sm text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-lg transition-colors"
            @click="resolve('discard')">{{ t('sync.discard') }}</button>
          <button class="px-4 py-2 text-sm font-bold bg-accent text-[#0d1117] rounded-lg hover:brightness-110 transition-all"
            @click="resolve('push')">{{ t('sync.pushToServer') }}</button>
        </template>
        <template v-else>
          <button class="px-4 py-2 text-sm text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-lg transition-colors"
            @click="resolve('restore')">{{ t('sync.restoreFromServer') }}</button>
          <button class="px-4 py-2 text-sm font-bold bg-danger text-white rounded-lg hover:brightness-110 transition-all"
            @click="resolve('confirm_delete')">{{ t('sync.confirmDelete') }}</button>
        </template>
      </div>
    </div>

    <p class="text-ink-muted text-xs mt-4 text-center">{{ t('sync.expiryNote') }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { AlertTriangle, CloudUpload, Trash2, CheckCircle } from 'lucide-vue-next'
import { useTauri } from '../composables/useTauri'
import { useUserStore } from '../stores/useUserStore'
import { useArticleStore } from '../stores/useArticleStore'
import { deleteArticle } from '../api/articles'

const { t } = useI18n()
const tauri = useTauri()
const userStore = useUserStore()
const articleStore = useArticleStore()

interface PendingItem {
  id: string; title: string; op_type: string; updated_at: string; offline_since?: string | null
}

const items = ref<PendingItem[]>([])
const currentIndex = ref(0)
const allResolved = ref(false)
const resolving = ref(false)

const currentItem = computed(() => items.value.length > 0 ? items.value[currentIndex.value] : null)

onMounted(async () => {
  const ops = await tauri.getPendingOps({ account_id: userStore.viewer?.id || 'local' })
  if (ops && Array.isArray(ops) && !('error' in ops)) {
    items.value = ops
  }
  if (items.value.length === 0) allResolved.value = true
})

async function resolve(action: 'push' | 'discard' | 'confirm_delete' | 'restore') {
  if (resolving.value || !currentItem.value) return
  resolving.value = true
  const id = currentItem.value.id

  if (action === 'push') {
    const draft = await tauri.getDraft({ id })
    if (draft && !('error' in draft)) {
      try {
        await articleStore.createArticle({
          id: draft.id, title: draft.title, content: draft.content,
          format: (draft.format as 'markdown' | 'typst') || 'markdown',
          commit_message: 'Offline save', self_review: { originality: 3, rigor: 3, completeness: 3, pedagogy: 3, impact: 3 },
        })
      } catch (e: unknown) { console.warn('Push failed:', e) }
    }
  } else if (action === 'confirm_delete') {
    try { await deleteArticle(id) } catch (e: unknown) { console.warn('Delete failed:', e) }
    try { await tauri.deleteArticle({ id, account_id: userStore.viewer?.id || 'local' }) } catch { /* best-effort */ }
  } else if (action === 'discard') {
    const history = await tauri.gitHistory({ article_id: id })
    if (history && Array.isArray(history)) {
      if (history.length === 1) {
        try { await tauri.deleteArticle({ id, account_id: userStore.viewer?.id || 'local' }) } catch { /* best-effort */ }
      } else {
        try { await tauri.gitResetHard({ article_id: id, commit_hash: history[1].hash }) } catch (e: unknown) { console.warn('gitResetHard failed:', e) }
      }
    }
  }

  await tauri.clearPending({ id })
  currentIndex.value++
  if (currentIndex.value >= items.value.length) allResolved.value = true
  resolving.value = false
}

function timeAgo(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime()
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return t('sync.lessThanHour')
  if (hours < 24) return t('sync.hoursAgo', { n: hours })
  const days = Math.floor(hours / 24)
  return t('sync.daysAgo', { n: days })
}
</script>
