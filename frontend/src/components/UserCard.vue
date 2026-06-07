<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/useUserStore'
import { followUser, unfollowUser } from '../api/users'
import { useTauri } from '../composables/useTauri'
import ReputationBadges from './ReputationBadges.vue'
import { BookOpen, MapPin } from 'lucide-vue-next'
import type { UserSummary } from '../api/types'

const { t } = useI18n()
const router = useRouter()
const userStore = useUserStore()
const tauri = useTauri()

const props = defineProps<{
  user: UserSummary
}>()

const isFollowing = ref(false)
const followLoading = ref(false)
const isLocal = userStore.isTauriMode || userStore.isBrowserLocal

function goToUser() {
  router.push(`/user/${props.user.id}`)
}

async function handleFollow(e: Event) {
  e.stopPropagation()
  if (!userStore.viewer || followLoading.value) return
  followLoading.value = true
  try {
    if (isLocal) {
      if (isFollowing.value) {
        await tauri.unfollowUser({ follower_id: userStore.viewer.id, followed_id: props.user.id })
      } else {
        await tauri.followUser({ follower_id: userStore.viewer.id, followed_id: props.user.id })
      }
    } else {
      if (isFollowing.value) {
        await unfollowUser(props.user.id)
      } else {
        await followUser(props.user.id)
      }
    }
    isFollowing.value = !isFollowing.value
  } catch { /* ignore */ }
  finally { followLoading.value = false }
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

      <!-- Follow button -->
      <button
        v-if="userStore.viewer && userStore.viewer.id !== user.id"
        class="text-[11px] px-2.5 py-1 rounded-xl font-semibold shrink-0 transition-colors duration-200"
        :class="isFollowing
          ? 'border border-accent/30 text-accent hover:bg-accent/10'
          : 'bg-accent text-[#0d1117] hover:brightness-110'"
        :disabled="followLoading"
        @click="handleFollow"
      >
        {{ isFollowing ? t('common.following') : t('common.follow') }}
      </button>
    </div>
  </article>
</template>
