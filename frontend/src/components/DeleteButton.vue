<script setup lang="ts">
import { ref } from 'vue'
import { Trash2 } from 'lucide-vue-next'
import { useTauri } from '../composables/useTauri'
import { deleteArticle } from '../api/articles'

const props = defineProps<{
  articleId: string
  authorId?: string
}>()

const emit = defineEmits<{
  deleted: [articleId: string]
}>()

const showConfirm = ref(false)
const deleting = ref(false)
const tauri = useTauri()

async function handleDelete() {
  if (deleting.value) return
  deleting.value = true
  try {
    if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
      const result = await tauri.deleteArticle({
        id: props.articleId,
        account_id: props.authorId || '',
      })
      if (result && 'error' in result) return
    } else {
      await deleteArticle(props.articleId)
    }
    emit('deleted', props.articleId)
    showConfirm.value = false
  } catch {
    // Silent failure — article remains visible, user can retry
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <!-- Trigger: trash icon only, danger color on hover -->
  <button
    v-if="!showConfirm"
    class="flex items-center justify-center w-7 h-7 rounded cursor-pointer
           text-ink-muted hover:text-danger hover:bg-danger/10
           transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
    aria-label="Delete article"
    data-tooltip="Delete"
    @click="showConfirm = true"
  >
    <Trash2 class="w-3.5 h-3.5" stroke-width="2" />
  </button>

  <!-- Confirmation: "Confirm?" + solid red Delete + Cancel -->
  <div v-else class="flex items-center gap-1">
    <span class="text-xs text-ink-muted">Confirm?</span>
    <button
      class="px-2 py-1 text-xs font-semibold bg-danger text-white rounded
             hover:brightness-110 transition-all cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      :disabled="deleting"
      @click="handleDelete"
    >
      {{ deleting ? '...' : 'Delete' }}
    </button>
    <button
      class="px-2 py-1 text-xs text-ink-muted hover:text-ink rounded
             hover:bg-[#21262d] transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      @click="showConfirm = false"
    >
      Cancel
    </button>
  </div>
</template>
