// Split-pane resize composable — extracted from EditorPage.vue.
//
// Usage:
//   const { splitRatio, splitterEl, isDragging, onSplitterMouseDown } = useSplitPane()

import { ref } from 'vue'

export function useSplitPane(initialRatio = 50, minRatio = 20, maxRatio = 80) {
  const splitRatio = ref(initialRatio)
  const isDragging = ref(false)
  const splitterEl = ref<HTMLElement | null>(null)

  function onMouseMove(e: MouseEvent) {
    if (!isDragging.value) return
    const container = splitterEl.value?.parentElement
    if (!container) return
    const rect = container.getBoundingClientRect()
    const pct = ((e.clientX - rect.left) / rect.width) * 100
    splitRatio.value = Math.min(maxRatio, Math.max(minRatio, pct))
  }

  function onMouseUp() {
    isDragging.value = false
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }

  function onSplitterMouseDown(e: MouseEvent) {
    isDragging.value = true
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
    e.preventDefault()
  }

  return { splitRatio, splitterEl, isDragging, onSplitterMouseDown }
}
