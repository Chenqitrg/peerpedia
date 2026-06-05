import { computed, type MaybeRefOrGetter, toValue } from 'vue'

type ArticleStatus = 'draft' | 'sedimentation' | 'published' | string

const STATUS_LABELS: Record<string, string> = {
  published: 'Published',
  sedimentation: 'In Pool',
  draft: 'Draft',
}

const STATUS_CLASSES: Record<string, string> = {
  published: 'badge-published',
  sedimentation: 'badge-sedimentation',
}

const DEFAULT_CLASS = 'badge-draft'

/**
 * Shared status label / CSS class mapping used by ArticleCard and ArticlePage.
 */
export function useStatusMap(status: MaybeRefOrGetter<ArticleStatus>) {
  const statusLabel = computed(() => {
    const s = toValue(status)
    return STATUS_LABELS[s] || s
  })

  const statusClass = computed(() => {
    const s = toValue(status)
    return STATUS_CLASSES[s] || DEFAULT_CLASS
  })

  return { statusLabel, statusClass }
}
