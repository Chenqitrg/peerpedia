<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getUsers } from '../api/users'
import { useUserStore } from '../stores/useUserStore'
import ReputationBadges from '../components/ReputationBadges.vue'
import { followUser, unfollowUser } from '../api/users'
import { useTauri } from '../composables/useTauri'
import { useOffline } from '../composables/useOffline'
import { useAsyncResource } from '../composables/useAsyncResource'
import ErrorState from '../components/ErrorState.vue'
import type { UserSummary } from '../api/types'
import { Users, UserPlus, UserCheck, Landmark } from 'lucide-vue-next'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()
const tauri = useTauri()
const { canRead, getFallback } = useOffline()
const following = ref<Set<string>>(new Set())

const isLocal = computed(() => userStore.isTauriMode || userStore.isBrowserLocal)

const { data: users, loading, error, execute } = useAsyncResource(
  async () => {
    // Block data fetch when offline or in local mode — schools requires
    // a server connection and should never show local accounts.
    if (!canRead('schools')) return [] as UserSummary[]
    const list = await getUsers()
    list.sort((a: UserSummary, b: UserSummary) => b.article_count - a.article_count)
    return list
  },
  [] as UserSummary[],
  { immediate: canRead('schools') },
)

async function toggleFollow(u: UserSummary) {
  if (!userStore.viewer) return
  const isCurrentlyFollowing = following.value.has(u.id)
  // Optimistic UI update — toggle immediately.
  if (isCurrentlyFollowing) {
    following.value.delete(u.id)
  } else {
    following.value.add(u.id)
  }
  // Persist locally in dev-mock mode, via REST API otherwise.
  if (isLocal.value) {
    if (isCurrentlyFollowing) {
      await tauri.unfollowUser({ follower_id: userStore.viewer.id, followed_id: u.id })
    } else {
      await tauri.followUser({ follower_id: userStore.viewer.id, followed_id: u.id })
    }
  } else {
    try {
      if (isCurrentlyFollowing) {
        await unfollowUser(u.id)
      } else {
        await followUser(u.id)
      }
    } catch {
      // Revert on failure when server is available.
      if (isCurrentlyFollowing) {
        following.value.add(u.id)
      } else {
        following.value.delete(u.id)
      }
    }
  }
}

function goToUser(id: string) {
  router.push(`/user/${id}`)
}
</script>

<template>
  <div class="schools-page animate-fade-in max-w-content mx-auto px-4 py-8">
    <!-- Offline blocked -->
    <div v-if="!canRead('schools')" class="offline-blocked card p-12 text-center">
      <p class="text-ink-muted text-lg mb-2">{{ t(getFallback('schools')) }}</p>
    </div>

    <template v-else>
    <!-- Header -->
    <div class="mb-8">
      <div class="flex items-center gap-3 mb-2">
        <Landmark class="w-6 h-6 text-accent" stroke-width="1.5" />
        <h1 class="text-display-md font-heading font-bold text-ink">{{ t('nav.schools') }}</h1>
      </div>
      <p class="text-sm text-ink-muted">
        {{ t('schools.subtitle') }}
      </p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-3 animate-pulse">
      <div v-for="i in 5" :key="i" class="skeleton h-16 w-full rounded-lg" />
    </div>

    <!-- Error -->
    <ErrorState v-else-if="error" :message="error" @retry="execute()" />

    <!-- User list -->
    <div v-else class="space-y-2">
      <div
        v-for="u in users"
        :key="u.id"
        class="card p-4 hover:border-accent/30 transition-colors duration-200 cursor-pointer"
        @click="goToUser(u.id)"
      >
        <div class="flex items-start gap-3">
          <div
            class="w-10 h-10 rounded-full bg-accent/15 flex items-center justify-center
                   text-accent font-semibold text-sm shrink-0 mt-0.5"
          >
            {{ u.name.charAt(0).toUpperCase() }}
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-0.5">
              <span class="text-sm font-semibold text-ink truncate">{{ u.name }}</span>
            </div>
            <div v-if="u.affiliation" class="text-[11px] text-ink-muted mb-0.5">
              {{ u.affiliation }}
            </div>
            <div class="flex items-center gap-3 text-xs text-ink-muted mb-1">
              <span>{{ u.article_count }} {{ t('common.articles') }}</span>
            </div>
            <ReputationBadges v-if="u.reputation" :reputation="u.reputation" />
            <div v-if="u.expertise && u.expertise.length" class="flex flex-wrap gap-1 mt-1.5">
              <span
                v-for="tag in u.expertise.slice(0, 3)"
                :key="tag"
                class="text-[10px] px-1.5 py-0.5 rounded bg-[#21262d] text-ink-muted/70"
              >{{ tag }}</span>
            </div>
          </div>
          <button
            v-if="userStore.viewer && u.id !== userStore.viewer.id"
            class="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg shrink-0
                   transition-colors duration-150"
            :class="following.has(u.id)
              ? 'bg-accent/10 text-accent border border-accent/30 hover:bg-accent/20'
              : 'bg-accent text-[#0d1117] hover:brightness-110'"
            @click.stop="toggleFollow(u)"
        >
          <UserCheck v-if="following.has(u.id)" class="w-3 h-3" stroke-width="2" />
          <UserPlus v-else class="w-3 h-3" stroke-width="2" />
          {{ following.has(u.id) ? 'Following' : 'Follow' }}
        </button>
        </div>
      </div>
    </div>
    </template>
  </div>
</template>
