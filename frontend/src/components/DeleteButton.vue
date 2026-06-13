<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Trash2 } from 'lucide-vue-next'
import { useTauri } from '../composables/useTauri'
import { useUserStore } from '../stores/useUserStore'
import { deleteArticle } from '../api/articles'

const { t } = useI18n()

const props = defineProps<{
  articleId: string
  authorId?: string
}>()

const emit = defineEmits<{
  deleted: [articleId: string]
  error: [message: string]
}>()

const showConfirm = ref(false)
const deleting = ref(false)
const errorMessage = ref('')
const tauri = useTauri()
const userStore = useUserStore()

async function handleDelete() {
  if (deleting.value) return
  deleting.value = true
  errorMessage.value = ''
  try {
    const isOnline = !!userStore.token

    if (isOnline) {
      // Server-first: delete from server, then clean up local
      await deleteArticle(props.articleId)
      // If in Tauri mode, also clean local DB
      if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
        try {
          await tauri.deleteArticle({
            id: props.articleId,
            account_id: props.authorId || '',
          })
        } catch {
          // Local cleanup is best-effort — server already succeeded
        }
      }
    } else if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
      // Offline: local delete only
      const result = await tauri.deleteArticle({
        id: props.articleId,
        account_id: props.authorId || '',
      })
      if (result && 'error' in result) {
        errorMessage.value = 'Delete failed: ' + result.error
        emit('error', errorMessage.value)
        return
      }
    } else {
      // Neither online nor Tauri — shouldn't happen
      errorMessage.value = 'Cannot delete: not connected'
      emit('error', errorMessage.value)
      return
    }

    emit('deleted', props.articleId)
    showConfirm.value = false
  } catch (e: any) {
    errorMessage.value = e?.response?.data?.detail || 'Delete failed — try again'
    emit('error', errorMessage.value)
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
    :aria-label="t('article.delete')"
    data-tooltip="Delete"
    @click="showConfirm = true"
  >
    <Trash2 class="w-3.5 h-3.5" stroke-width="2" />
  </button>

  <!-- Confirmation: "Confirm?" + solid red Delete + Cancel -->
  <div v-else class="flex flex-col gap-1">
    <div v-if="errorMessage" class="text-xs text-danger">{{ errorMessage }}</div>
    <div class="flex items-center gap-1">
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
  </div>
</template>
