<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import ReputationBadges from './ReputationBadges.vue'
import { Users, BookOpen, MapPin } from 'lucide-vue-next'
import type { UserSummary } from '../api/types'

const { t } = useI18n()
const router = useRouter()

const props = defineProps<{
  user: UserSummary
}>()

function goToUser() {
  router.push(`/user/${props.user.id}`)
}
</script>

<template>
  <article
    class="card p-4 hover:border-accent/30 transition-colors duration-200 cursor-pointer"
    @click="goToUser"
  >
    <div class="flex items-start gap-3">
      <!-- Avatar -->
      <div
        class="w-10 h-10 rounded-full bg-accent/15 flex items-center justify-center
               text-accent font-semibold text-sm shrink-0 mt-0.5"
      >
        {{ user.name.charAt(0).toUpperCase() }}
      </div>

      <!-- Info -->
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-0.5">
          <span class="text-sm font-semibold text-ink truncate">{{ user.name }}</span>
        </div>
        <div v-if="user.affiliation" class="flex items-center gap-1 text-[11px] text-ink-muted mb-1">
          <MapPin class="w-3 h-3 shrink-0" stroke-width="2" />
          <span class="truncate">{{ user.affiliation }}</span>
        </div>
        <div class="flex items-center gap-3 text-xs text-ink-muted">
          <span class="flex items-center gap-1">
            <BookOpen class="w-3 h-3" stroke-width="2" />
            {{ user.article_count }} {{ t('common.articles') }}
          </span>
        </div>
        <div v-if="user.reputation" class="mt-1.5">
          <ReputationBadges :reputation="user.reputation" />
        </div>
      </div>
    </div>
  </article>
</template>
