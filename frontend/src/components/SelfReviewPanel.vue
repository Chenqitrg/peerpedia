<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import StarRating from './StarRating.vue'
import { SCORE_DIMS } from '../api/constants'

const { t } = useI18n()

const open = defineModel<boolean>({ required: true })
const commitMsg = defineModel<string>('commitMsg', { default: '' })
const scores = defineModel<Record<string, number>>('scores', { required: true })
const keywords = defineModel<string>('keywords', { default: '' })
const categories = defineModel<string>('categories', { default: '' })
const abstract = defineModel<string>('abstract', { default: '' })

defineProps<{
  submitting: boolean
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
            {{ t('editor.commitMessage') }} <span class="text-danger">*</span>
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
