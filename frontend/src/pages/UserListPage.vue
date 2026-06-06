<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getFollowers, getFollowing } from '../api/users'
import UserCard from '../components/UserCard.vue'
import ErrorState from '../components/ErrorState.vue'
import type { UserSummary } from '../api/types'
import { ArrowLeft } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const userId = computed(() => route.params.id as string)
const isFollowers = computed(() => route.path.endsWith('/followers'))

const users = ref<UserSummary[]>([])
const loading = ref(true)
const error = ref('')

const title = computed(() => isFollowers.value ? t('common.followers') : t('common.following'))

async function load() {
  loading.value = true
  error.value = ''
  try {
    users.value = isFollowers.value
      ? await getFollowers(userId.value)
      : await getFollowing(userId.value)
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

    <h1 class="text-display-md text-ink mb-2">{{ title }}</h1>
    <p class="text-sm text-ink-muted mb-6">
      {{ t('common.articles') }}
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
