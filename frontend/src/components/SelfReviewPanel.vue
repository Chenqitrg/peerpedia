<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '../stores/useUserStore'
import StarRating from './StarRating.vue'
import { SCORE_DIMS } from '../api/constants'
import { SlidersHorizontal } from 'lucide-vue-next'

const { t } = useI18n()
const userStore = useUserStore()

const open = defineModel<boolean>({ required: true })
const commitMsg = defineModel<string>('commitMsg', { default: '' })
const scores = defineModel<Record<string, number>>('scores', { required: true })
const keywords = defineModel<string>('keywords', { default: '' })
const categories = defineModel<string>('categories', { default: '' })
const abstract = defineModel<string>('abstract', { default: '' })
const contributions = defineModel<Record<string, number>>('contributions', { required: true })

defineProps<{
  submitting: boolean
  totalContribution: number
}>()

const emit = defineEmits<{
  submit: []
}>()

const show = computed({
  get: () => open.value,
  set: (v) => { open.value = v },
})
</script>

<template>
  <Transition name="slide-up">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      @click.self="open = false"
    >
      <div class="bg-card border border-divider rounded-2xl shadow-2xl w-full max-w-lg mx-4 p-6 animate-fade-in max-h-[90vh] overflow-y-auto">
        <h3 class="text-lg font-heading font-semibold text-ink mb-1">{{ t('editor.selfAssessment') }}</h3>
        <p class="text-xs text-ink-muted mb-5">{{ t('editor.selfAssessmentHint') }}</p>

        <!-- Commit message -->
        <div class="mb-5">
          <label class="text-xs font-semibold text-ink-muted block mb-1.5">
            {{ t('editor.commitMessage') }} <span class="text-[#d73a49]">*</span>
          </label>
          <input
            v-model="commitMsg"
            type="text"
            :placeholder="t('editor.commitMessagePlaceholder')"
            class="w-full bg-[#0d1117] border border-divider rounded-lg px-3 py-2 text-sm text-ink placeholder:text-ink-muted/50 focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>

        <!-- 5-dim scores — use StarRating like the article review panel -->
        <div class="mb-5">
          <label class="text-xs font-semibold text-ink-muted block mb-3">{{ t('editor.scores1to5') }}</label>
          <div class="space-y-2">
            <div
              v-for="dim in SCORE_DIMS"
              :key="dim.key"
              class="flex items-center gap-3 py-1.5 px-3 rounded-lg hover:bg-[#21262d] transition-colors"
            >
              <span class="text-xs text-ink-muted w-28 shrink-0">{{ dim.fullLabel }}</span>
              <StarRating
                :modelValue="scores[dim.key]"
                size="sm"
                @update:modelValue="v => scores[dim.key] = v"
              />
              <span class="text-xs text-ink font-mono w-4 text-right">{{ scores[dim.key] }}</span>
            </div>
          </div>
        </div>

        <!-- Keywords -->
        <div class="mb-4">
          <label class="text-xs font-semibold text-ink-muted block mb-1.5">{{ t('editor.keywords') }}</label>
          <input
            v-model="keywords"
            type="text"
            :placeholder="t('editor.keywordsPlaceholder')"
            class="w-full bg-[#0d1117] border border-divider rounded-lg px-3 py-2 text-sm text-ink placeholder:text-ink-muted/50 focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>

        <!-- Categories -->
        <div class="mb-4">
          <label class="text-xs font-semibold text-ink-muted block mb-1.5">{{ t('editor.categories') }}</label>
          <input
            v-model="categories"
            type="text"
            :placeholder="t('editor.categoriesPlaceholder')"
            class="w-full bg-[#0d1117] border border-divider rounded-lg px-3 py-2 text-sm text-ink placeholder:text-ink-muted/50 focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>

        <!-- Abstract -->
        <div class="mb-5">
          <label class="text-xs font-semibold text-ink-muted block mb-1.5">{{ t('editor.abstract') }}</label>
          <textarea
            v-model="abstract"
            rows="3"
            :placeholder="t('editor.abstractPlaceholder2')"
            class="w-full bg-[#0d1117] border border-divider rounded-lg px-3 py-2 text-sm text-ink placeholder:text-ink-muted/50 focus:outline-none focus:ring-1 focus:ring-accent resize-none"
          />
        </div>

        <!-- Contribution -->
        <div class="mb-6">
          <label class="text-xs font-semibold text-ink-muted flex items-center gap-1.5 mb-3">
            <SlidersHorizontal class="w-3 h-3" />
            {{ t('editor.contribution') || 'Contribution' }}
          </label>
          <div
            v-for="(pct, authorId) in contributions"
            :key="authorId"
            class="flex items-center gap-3 mb-2"
          >
            <span class="text-xs text-ink-muted w-20 truncate">
              {{ authorId === userStore.viewer?.id ? 'You' : authorId.substring(0, 8) }}
            </span>
            <input
              type="range"
              :value="pct"
              min="0"
              max="100"
              class="flex-1 h-1.5 accent-accent"
              @input="contributions[authorId] = Number(($event.target as HTMLInputElement).value)"
            />
            <span class="text-xs text-ink font-mono w-8 text-right">{{ pct }}%</span>
          </div>
          <p v-if="totalContribution !== 100" class="text-[10px] text-[#d73a49]">
            {{ t('editor.contributionMustTotal100') || 'Contributions must total 100%. Currently:' }} {{ totalContribution }}%
          </p>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-3">
          <button
            class="btn-outline flex-1"
            @click="open = false"
          >
            {{ t('editor.cancel') }}
          </button>
          <button
            class="btn-primary flex-1"
            :disabled="submitting"
            @click="emit('submit')"
          >
            {{ submitting ? t('editor.submitting') : t('editor.publishToPool') }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
