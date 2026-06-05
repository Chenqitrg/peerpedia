<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCitations } from '../api/articles'
import type { CitationGraph } from '../api/types'
import { ArrowLeft, ExternalLink, BookOpen } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const id = route.params.id as string
const citationGraph = ref<CitationGraph | null>(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  await loadCitations()
})

async function loadCitations() {
  loading.value = true
  error.value = ''
  try {
    citationGraph.value = await getCitations(id)
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to load citations'
  } finally {
    loading.value = false
  }
}

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
        aria-label="Back to article"
        @click="goBack"
      >
        <ArrowLeft class="w-4 h-4" stroke-width="2" />
      </button>
      <div>
        <h1 class="text-display-md font-heading font-bold text-ink">Citations</h1>
        <p class="text-xs text-ink-muted">References and citations for this article</p>
      </div>
    </div>

    <div v-if="loading" class="space-y-3 animate-pulse">
      <div v-for="i in 3" :key="i" class="card p-4">
        <div class="skeleton h-5 w-2/3 mb-2" />
        <div class="skeleton h-3 w-1/3" />
      </div>
    </div>

    <div v-else-if="error" class="card p-8 text-center">
      <p class="text-ink-muted">{{ error }}</p>
      <button class="btn-outline mt-4" @click="loadCitations">Retry</button>
    </div>

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
              <span>Forward: {{ (cite.forward_prob * 100).toFixed(0) }}%</span>
              <span>Backward: {{ (cite.backward_prob * 100).toFixed(0) }}%</span>
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
              <span>Forward: {{ (cite.forward_prob * 100).toFixed(0) }}%</span>
              <span>Backward: {{ (cite.backward_prob * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
