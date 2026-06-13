<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { getStatusInfo, useStatusLabel } from '../composables/useStatusMap'
import type { ArticleSummary } from '../api/types'
import { forkArticle } from '../api/articles'
import ScoreBadges from './ScoreBadges.vue'
import DeleteButton from './DeleteButton.vue'
import {
  FileText,
  Users,
  GitCommitHorizontal,
  Bookmark,
  BookmarkCheck,
  History,
  Edit,
  GitFork,
  GitCompare,
} from 'lucide-vue-next'

const props = defineProps<{
  article: ArticleSummary
  syncState?: 'synced' | 'conflict' | 'offline'
}>()

const emit = defineEmits<{
  (e: 'toggleBookmark', articleId: string, currentlyBookmarked: boolean): void
  (e: 'deleted', articleId: string): void
  (e: 'sync-resolve', articleId: string): void
}>()

const router = useRouter()
const { t } = useI18n()
const showDeleteConfirm = ref(false)

const progressPercent = computed(() => {
  const a = props.article
  if (a.status !== 'sedimentation' || !a.sink_duration_days || a.sink_duration_days === 0) return 0
  const elapsed = a.sink_duration_days - (a.days_remaining ?? 0)
  return Math.round((elapsed / a.sink_duration_days) * 100)
})

const statusLabel = useStatusLabel(() => props.article.status)
const statusClass = computed(() => getStatusInfo(props.article.status).class)

const authorNames = computed(() => {
  return props.article.authors?.map((a: any) => a.name) ?? []
})

function handleBookmarkClick() {
  emit('toggleBookmark', props.article.id, props.article.is_bookmarked)
}

function goToEdit() {
  router.push(`/edit/${props.article.id}`)
}

function goToHistory() {
  router.push(`/articles/${props.article.id}/history`)
}

async function goToFork() {
  try {
    const result = await forkArticle(props.article.id)
    router.push(`/edit/${result.id}`)
  } catch {
    // silent — error handled by the API interceptor
  }
}
</script>

<template>
  <article
    class="card p-5 hover:border-accent/30 transition-colors duration-200 animate-fade-in"
  >
    <!-- Title row -->
    <div class="flex items-start gap-2 mb-2">
      <FileText class="w-4 h-4 text-ink-muted mt-1 shrink-0" stroke-width="2" />
      <router-link
        :to="`/articles/${article.id}`"
        class="no-underline hover:no-underline flex-1 min-w-0"
      >
        <h3 class="text-lg font-heading font-semibold text-ink leading-tight line-clamp-2 hover:underline decoration-accent/30 underline-offset-2">
          {{ article.title || t('card.untitled') }}
        </h3>
      </router-link>
      <!-- L4 conflict icon -->
      <button
        v-if="syncState === 'conflict'"
        class="sync-icon-btn"
        :title="t('sync.conflictTooltip')"
        @click.stop="emit('sync-resolve', article.id)"
      >
        <GitCompare :size="16" stroke-width="2" class="text-warning" />
      </button>
    </div>

    <!-- Authors row with badges -->
    <div class="flex items-center justify-between gap-2 mb-3">
      <div class="flex items-center gap-1.5 text-sm text-ink-muted min-w-0 flex-1">
        <Users class="w-3.5 h-3.5 shrink-0" stroke-width="2" />
        <span class="truncate">
          <template v-for="(author, idx) in article.authors" :key="author.id">
            <router-link
              :to="`/user/${author.id}`"
              class="text-ink-muted hover:text-accent transition-colors no-underline"
            >
              {{ author.name }}
            </router-link>
            <span v-if="idx < article.authors.length - 1">, </span>
          </template>
        </span>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <!-- Forked badge -->
        <span
          v-if="article.forked_from"
          class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-mono text-neutral bg-neutral/10 rounded"
        >
          <GitFork class="w-3 h-3" stroke-width="2" />
          {{ t('card.forkBadge') }}
        </span>
        <!-- Version badge -->
        <span
          v-if="article.commit_count > 1"
          class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-mono text-ink-muted bg-[#21262d] rounded"
        >
          v{{ article.commit_count }}
        </span>
      </div>
    </div>

    <!-- Abstract (preferred) or content preview -->
    <p class="text-sm text-ink-muted/80 leading-relaxed mb-3 line-clamp-3">
      {{ article.abstract || article.content_preview || t('card.noPreview') }}
    </p>

    <!-- Sink progress bar (only for sedimentation) -->
    <div
      v-if="article.status === 'sedimentation' && article.days_remaining != null"
      class="mb-3"
    >
      <div class="flex items-center gap-2 mb-1.5">
        <div class="flex-1 h-1.5 bg-divider rounded-full overflow-hidden">
          <div
            class="h-full bg-neutral rounded-full transition-all duration-500"
            :style="{ width: `${progressPercent}%` }"
          />
        </div>
        <span class="text-xs text-ink-muted whitespace-nowrap font-mono">
          {{ article.days_remaining }}{{ t('card.dRemaining') }}
        </span>
      </div>
    </div>

    <!-- Footer: scores, hash, actions -->
    <div class="flex items-center justify-between gap-4 pt-3 border-t border-divider">
      <!-- Scores -->
      <div class="flex items-center gap-2 text-xs font-mono text-ink-muted">
        <ScoreBadges :score="article.score" :highlight-first="true" />
      </div>

      <!-- Right side -->
      <div class="flex items-center gap-0.5">
        <!-- Commit hash -->
        <span
          v-if="article.commit_hash"
          class="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 text-xs font-mono text-ink-muted bg-[#21262d] rounded mr-1"
        >
          <GitCommitHorizontal class="w-3 h-3" stroke-width="2" />
          {{ article.commit_hash.substring(0, 7) }}
        </span>

        <!-- Actions -->
        <button
          v-if="!article.is_own_article"
          class="flex items-center justify-center w-7 h-7 rounded
                 text-ink-muted hover:text-accent hover:bg-accent/10
                 transition-colors duration-200"
          :aria-label="article.is_bookmarked ? 'Remove bookmark' : 'Add bookmark'"
          :data-tooltip="article.is_bookmarked ? 'Remove bookmark' : 'Add bookmark'"
          @click="handleBookmarkClick"
        >
          <BookmarkCheck v-if="article.is_bookmarked" class="w-3.5 h-3.5 text-accent" stroke-width="2" />
          <Bookmark v-else class="w-3.5 h-3.5" stroke-width="2" />
        </button>

        <router-link
          :to="`/articles/${article.id}/history`"
          class="flex items-center justify-center w-7 h-7 rounded
                 text-ink-muted hover:text-accent hover:bg-accent/10
                 transition-colors duration-200"
          :aria-label="t('card.history')"
          :data-tooltip="t('card.history')"
        >
          <History class="w-3.5 h-3.5" stroke-width="2" />
        </router-link>

        <button
          v-if="article.is_own_article && !showDeleteConfirm"
          class="flex items-center justify-center w-7 h-7 rounded
                 text-ink-muted hover:text-accent hover:bg-accent/10
                 transition-colors duration-200"
          :aria-label="t('card.edit')"
          :data-tooltip="t('card.edit')"
          @click="goToEdit"
        >
          <Edit class="w-3.5 h-3.5" stroke-width="2" />
        </button>

        <DeleteButton
          v-if="article.is_own_article"
          :article-id="article.id"
          :author-id="article.authors?.[0]?.id"
          @deleted="(id: string) => emit('deleted', id)"
        />

        <button
          class="flex items-center justify-center w-7 h-7 rounded
                 text-ink-muted hover:text-accent hover:bg-accent/10
                 transition-colors duration-200"
          :aria-label="t('card.fork')"
          :data-tooltip="t('card.fork')"
          @click="goToFork"
        >
          <GitFork class="w-3.5 h-3.5" stroke-width="2" />
        </button>

        <!-- Status badge -->
        <span :class="`${statusClass} ml-2 text-xs`">
          {{ statusLabel }}
        </span>
      </div>
    </div>
  </article>
</template>

<style scoped>
.sync-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  transition: background-color 150ms ease;
}
.sync-icon-btn:hover {
  background-color: rgba(123, 140, 158, 0.15);
}
.text-warning {
  color: #9e6a03;
}
</style>
