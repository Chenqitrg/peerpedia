<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getFollowers, getFollowing, getUsers } from '../api/users'
import { useUserStore } from '../stores/useUserStore'
import { useTauri } from '../composables/useTauri'
import { useNetworkStatus } from '../composables/useNetworkStatus'
import UserCard from '../components/UserCard.vue'
import ErrorState from '../components/ErrorState.vue'
import type { UserSummary } from '../api/types'
import { ArrowLeft, UsersRound, UserCheck } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()
const tauri = useTauri()
const { isOnline } = useNetworkStatus()

const userId = computed(() => route.params.id as string)
const isFollowers = computed(() => route.path.endsWith('/followers'))

const users = ref<UserSummary[]>([])
const loading = ref(true)
const error = ref('')

const title = computed(() => isFollowers.value ? t('common.followers') : t('common.following'))

async function load() {
  loading.value = true
  error.value = ''
  const isLocal = userStore.isTauriMode || userStore.isBrowserLocal
  try {
    if (isLocal) {
      const result = isFollowers.value
        ? await tauri.getFollowers({ user_id: userId.value })
        : await tauri.getFollowing({ user_id: userId.value })
      if (result && !('error' in result) && Array.isArray(result) && result.length > 0) {
        // Resolve names: fetch server user list to map IDs to names
        let nameMap: Map<string, string> = new Map()
        if (isOnline.value) {
          try {
            const serverUsers = await getUsers()
            for (const u of serverUsers) nameMap.set(u.id, u.name)
          } catch { /* server unreachable, use IDs as names */ }
        }
        users.value = result.map(a => ({
          id: a.id,
          name: nameMap.get(a.id) || a.id.slice(0, 8) + '…',
          anonymous_name: '',
          article_count: 0,
          reputation: {},
        })) as UserSummary[]
      }
    } else {
      users.value = isFollowers.value
        ? await getFollowers(userId.value)
        : await getFollowing(userId.value)
    }
  } catch (e: any) {
    error.value = e.userMessage || t('common.error')
  } finally {
    loading.value = false
  }
}

watch([userId, isFollowers], load, { immediate: true })
</script>

<template>
  <div class="user-list-page animate-fade-in">
    <button
      class="flex items-center gap-1 text-xs text-ink-muted hover:text-ink transition-colors mb-4"
      @click="router.push(`/user/${userId}`)"
    >
      <ArrowLeft class="w-3.5 h-3.5" stroke-width="2" />
      {{ t('common.backToHome') }}
    </button>

    <h1 class="text-display-md text-ink mb-2 flex items-center gap-2">
      <UsersRound v-if="isFollowers" class="w-5 h-5 text-accent" stroke-width="1.5" />
      <UserCheck v-else class="w-5 h-5 text-accent" stroke-width="1.5" />
      {{ title }}
    </h1>
    <p class="text-sm text-ink-muted mb-6">
      {{ users.length }} {{ isFollowers ? t('common.followers') : t('common.following') }}
    </p>

    <div v-if="loading" class="space-y-2 animate-pulse">
      <div v-for="i in 5" :key="i" class="skeleton h-16 w-full rounded-lg" />
    </div>

    <ErrorState v-else-if="error" :message="error" @retry="load()" />

    <div v-else-if="users.length === 0" class="card p-12 text-center">
      <p class="text-ink-muted">
        {{ isFollowers ? 'No followers yet.' : 'Not following anyone yet.' }}
      </p>
    </div>

    <div v-else class="space-y-2">
      <UserCard v-for="u in users" :key="u.id" :user="u" />
    </div>
  </div>
</template>
