<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getCitations } from '../api/articles'
import { useAsyncResource } from '../composables/useAsyncResource'
import SkeletonCard from '../components/SkeletonCard.vue'
import ErrorState from '../components/ErrorState.vue'
import type { CitationGraph } from '../api/types'
import { ArrowLeft, ExternalLink, BookOpen } from 'lucide-vue-next'

const route = useRoute()
const { t } = useI18n()
const router = useRouter()
const id = route.params.id as string

const { data: citationGraph, loading, error, execute: loadCitations } = useAsyncResource(
  () => getCitations(id),
  null as CitationGraph | null,
  { immediate: true },
)

function goBack() {
  router.push(`/articles/${id}`)
}
</script>

<template>
  <div class="citations-page animate-fade-in">
    <div class="flex items-center gap-3 mb-6">
      <button
        class="flex items-center justify-center w-8 h-8 rounded-lg
               text-ink-muted hover:text-ink hover:bg-[#21262d] transition-colors"
        :aria-label="t('citations.backToArticle')"
        @click="goBack"
      >
        <ArrowLeft class="w-4 h-4" stroke-width="2" />
      </button>
      <div>
        <h1 class="text-display-md font-heading font-bold text-ink">Citations</h1>
        <p class="text-xs text-ink-muted">References and citations for this article</p>
      </div>
    </div>

    <SkeletonCard v-if="loading" :count="3" />

    <ErrorState v-else-if="error" :message="error" @retry="loadCitations()" />

    <template v-else-if="citationGraph">
      <section class="mb-8">
        <h2 class="text-base font-heading font-semibold text-ink mb-3 flex items-center gap-2">
          <BookOpen class="w-4 h-4 text-accent" stroke-width="2" />
          References ({{ citationGraph.cites.length }})
        </h2>
        <div v-if="citationGraph.cites.length === 0" class="card p-6 text-center">
          <p class="text-sm text-ink-muted">No references found.</p>
        </div>
        <div v-else class="space-y-2">
          <div
            v-for="cite in citationGraph.cites"
            :key="cite.article_id"
            class="card p-4 hover:border-accent/30 transition-colors"
          >
            <router-link :to="`/articles/${cite.article_id}`" class="no-underline">
              <h3 class="text-sm font-heading font-semibold text-ink hover:text-accent transition-colors">
                {{ cite.title }}
              </h3>
            </router-link>
            <div class="flex items-center gap-3 mt-1.5 text-xs text-ink-muted">
              <span>{{ t('citation.forward') }}: {{ (cite.forward_prob * 100).toFixed(0) }}%</span>
              <span>{{ t('citation.backward') }}: {{ (cite.backward_prob * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>
      </section>

      <section>
        <h2 class="text-base font-heading font-semibold text-ink mb-3 flex items-center gap-2">
          <ExternalLink class="w-4 h-4 text-accent" stroke-width="2" />
          Cited by ({{ citationGraph.cited_by.length }})
        </h2>
        <div v-if="citationGraph.cited_by.length === 0" class="card p-6 text-center">
          <p class="text-sm text-ink-muted">Not cited by any articles yet.</p>
        </div>
        <div v-else class="space-y-2">
          <div
            v-for="cite in citationGraph.cited_by"
            :key="cite.article_id"
            class="card p-4 hover:border-accent/30 transition-colors"
          >
            <router-link :to="`/articles/${cite.article_id}`" class="no-underline">
              <h3 class="text-sm font-heading font-semibold text-ink hover:text-accent transition-colors">
                {{ cite.title }}
              </h3>
            </router-link>
            <div class="flex items-center gap-3 mt-1.5 text-xs text-ink-muted">
              <span>{{ t('citation.forward') }}: {{ (cite.forward_prob * 100).toFixed(0) }}%</span>
              <span>{{ t('citation.backward') }}: {{ (cite.backward_prob * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
