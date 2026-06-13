<!-- SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors -->
<!-- SPDX-License-Identifier: CC-BY-NC-SA-4.0 -->

<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, CloudUpload, Trash2, CheckCircle } from 'lucide-vue-next'

export interface PendingItem {
  id: string
  title: string
  op_type: string  // "push" | "delete"
  updated_at: string
  offline_since?: string | null
}

const props = defineProps<{
  items: PendingItem[]
}>()

const emit = defineEmits<{
  resolve: [id: string, action: 'push' | 'discard' | 'confirm_delete' | 'restore']
}>()

const currentIndex = computed(() => props.items.length > 0 ? 0 : -1)
const current = computed(() => props.items.length > 0 ? props.items[0] : null)

function timeAgo(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime()
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return 'Less than 1 hour ago'
  if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days > 1 ? 's' : ''} ago`
}
</script>

<template>
  <div class="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center" role="alertdialog" aria-modal="true">
    <div class="bg-card border border-divider rounded-xl shadow-2xl p-6 max-w-lg w-full mx-4">
      <!-- Header -->
      <div class="flex items-center gap-3 mb-4">
        <AlertTriangle class="w-5 h-5 text-warning flex-shrink-0" />
        <div>
          <h2 class="font-heading font-semibold text-lg text-ink">Sync Required / 需要同步</h2>
          <p class="text-ink-muted text-sm">Resolve each item before continuing. 请逐条解决后继续。</p>
        </div>
      </div>

      <!-- Progress -->
      <p class="text-ink-muted text-xs mb-4">
        Item 1 of {{ items.length }}
      </p>

      <!-- Current item -->
      <div v-if="current" class="bg-[#0d1117] rounded-lg p-4 border border-divider mb-4">
        <div class="flex items-center gap-2 mb-1">
          <CloudUpload v-if="current.op_type === 'push'" class="w-4 h-4 text-accent" />
          <Trash2 v-else class="w-4 h-4 text-danger" />
          <span class="text-ink-muted text-xs">
            {{ current.op_type === 'push' ? 'Pending upload' : 'Pending delete' }}
            &mdash; Saved {{ timeAgo(current.updated_at) }}
          </span>
        </div>
        <p class="font-heading text-ink text-base">{{ current.title || 'Untitled' }}</p>
      </div>

      <!-- Actions -->
      <div v-if="current" class="flex justify-end gap-3">
        <template v-if="current.op_type === 'push'">
          <button
            class="px-4 py-2 text-sm text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-lg transition-colors duration-200"
            @click="emit('resolve', current.id, 'discard')"
          >
            Discard / 丢弃
          </button>
          <button
            class="px-4 py-2 text-sm font-bold bg-accent text-[#0d1117] rounded-lg hover:brightness-110 transition-all duration-200"
            @click="emit('resolve', current.id, 'push')"
          >
            Push to Server / 推送到服务器
          </button>
        </template>
        <template v-else>
          <button
            class="px-4 py-2 text-sm text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-lg transition-colors duration-200"
            @click="emit('resolve', current.id, 'restore')"
          >
            Restore from Server / 从服务器恢复
          </button>
          <button
            class="px-4 py-2 text-sm font-bold bg-danger text-white rounded-lg hover:brightness-110 transition-all duration-200"
            @click="emit('resolve', current.id, 'confirm_delete')"
          >
            Confirm Delete / 确认删除
          </button>
        </template>
      </div>

      <!-- Footer -->
      <p class="text-ink-muted text-xs mt-4 border-t border-divider pt-3">
        Changes older than 7 days will be marked expired.
      </p>
    </div>
  </div>
</template>
