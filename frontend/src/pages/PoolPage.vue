<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useOffline } from '../composables/useOffline'
import { getPool } from '../api/pool'
import { useAsyncResource } from '../composables/useAsyncResource'
import { useBookmarkToggle } from '../composables/useBookmarkToggle'
import ArticleCard from '../components/ArticleCard.vue'
import SkeletonCard from '../components/SkeletonCard.vue'
import ErrorState from '../components/ErrorState.vue'
import type { PoolResponse } from '../api/types'

const { t } = useI18n()

const { data: pool, loading, error, execute: loadPool } = useAsyncResource(
  () => getPool(),
  null as PoolResponse | null,
  { immediate: true },
)

// Debug: log errors to help diagnose Pool navigation issues
watch(error, (e) => {
  if (e) console.error('[PoolPage] API error:', e)
})

const poolArticles = computed(() => pool.value?.articles ?? [])

const { toggle: handleToggleBookmark } = useBookmarkToggle(poolArticles, (_msg: string) => {})

const { canRead, getFallback } = useOffline()
</script>

<template>
  <div class="pool-page animate-fade-in">
    <!-- Offline blocked -->
    <div v-if="!canRead('pool')" class="offline-blocked card p-12 text-center">
      <p class="text-ink-muted text-lg mb-2">{{ t(getFallback('pool')) }}</p>
    </div>

    <template v-else>
    <header class="mb-8">
      <h1 class="text-display-md text-ink mb-2">{{ t('pool.title') }}</h1>
      <p class="text-sm text-ink-muted">
        {{ t('pool.subtitle') }}
      </p>
    </header>

    <!-- Loading -->
    <SkeletonCard v-if="loading" />

    <!-- Error -->
    <ErrorState v-else-if="error" :message="error" @retry="loadPool()" />

    <!-- Empty -->
    <div v-else-if="poolArticles.length === 0" class="card p-12 text-center">
      <p class="text-ink-muted mb-4">{{ t('pool.empty') }}</p>
      <p class="text-xs text-ink-muted/60 mb-6">
        {{ t('pool.emptyHint') }}
      </p>
      <router-link to="/" class="btn-primary no-underline">{{ t('common.backToHome') }}</router-link>
    </div>

    <!-- Pool list -->
    <div v-else class="space-y-4">
      <ArticleCard
        v-for="article in poolArticles"
        :key="article.id"
        :article="article"
        @toggle-bookmark="handleToggleBookmark"
      />
    </div>
    </template>
  </div>
</template>
