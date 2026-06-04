<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getUser } from '../api/users'
import type { UserProfile } from '../api/types'

const route = useRoute()
const id = route.params.id as string
const user = ref<UserProfile | null>(null)
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    user.value = await getUser(id)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="user-page max-w-content animate-fade-in">
    <!-- Loading -->
    <div v-if="loading" class="space-y-4 animate-pulse">
      <div class="flex items-center gap-4 mb-6">
        <div class="skeleton w-20 h-20 rounded-full" />
        <div class="space-y-2 flex-1">
          <div class="skeleton h-7 w-1/3" />
          <div class="skeleton h-4 w-1/4" />
        </div>
      </div>
    </div>

    <!-- Profile -->
    <div v-else-if="user">
      <!-- Header -->
      <section class="flex flex-col sm:flex-row items-start gap-6 mb-10">
        <!-- Avatar -->
        <div class="w-20 h-20 rounded-full bg-primary-100 flex items-center justify-center shrink-0">
          <span class="text-2xl font-heading font-bold text-primary-600">
            {{ (user.name || '?')[0].toUpperCase() }}
          </span>
        </div>

        <div class="flex-1 min-w-0">
          <h1 class="text-display-md text-ink mb-1">{{ user.name }}</h1>
          <p v-if="user.affiliation" class="text-ink-muted mb-3">
            {{ user.affiliation }}
          </p>

          <!-- Stats -->
          <div class="flex flex-wrap gap-4 text-sm">
            <span class="flex items-center gap-1.5 text-ink-muted">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
              </svg>
              {{ user.article_count ?? 0 }} articles
            </span>
            <span class="flex items-center gap-1.5 text-ink-muted">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
              </svg>
              {{ user.followers_count ?? 0 }} followers
            </span>
            <span class="flex items-center gap-1.5 text-ink-muted">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
              </svg>
              {{ user.following_count ?? 0 }} following
            </span>
          </div>
        </div>

        <button class="btn-outline shrink-0">Follow</button>
      </section>

      <!-- Expertise -->
      <section v-if="user.expertise?.length" class="mb-8">
        <h2 class="text-lg font-heading font-semibold text-ink mb-3">Expertise</h2>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="exp in user.expertise"
            :key="exp"
            class="badge bg-primary-100 text-primary-700"
          >
            {{ exp }}
          </span>
        </div>
      </section>

      <!-- Reputation -->
      <section v-if="user.reputation" class="card p-6">
        <h2 class="text-lg font-heading font-semibold text-ink mb-4">Reputation</h2>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
          <div v-for="[key, val] in Object.entries(user.reputation)" :key="key" class="space-y-1">
            <div class="text-2xl font-bold text-primary-600">{{ val }}</div>
            <div class="text-xs text-ink-muted capitalize">{{ key }}</div>
          </div>
        </div>
      </section>
    </div>

    <!-- Error state -->
    <div v-else class="card p-12 text-center">
      <svg class="w-16 h-16 text-ink-subtle mx-auto mb-4" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
      </svg>
      <p class="text-ink-muted">User not found.</p>
    </div>
  </div>
</template>
