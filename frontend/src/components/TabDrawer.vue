<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useTabStore } from '../stores/useTabStore'
import { Edit, Eye, X } from 'lucide-vue-next'
import { getStatusInfo } from '../composables/useStatusMap'

const tabStore = useTabStore()
const expanded = ref(false)
const container = ref<HTMLElement | null>(null)
let collapseTimer: ReturnType<typeof setTimeout> | null = null

const emit = defineEmits<{ (e: 'close-tab', tabId: string): void }>()

function statusColor(status: string, active: boolean): string {
  const base = active ? 'opacity-100' : 'opacity-70'
  const info = getStatusInfo(status)
  switch (info.class) {
    case 'badge-published':    return `bg-success ${base}`
    case 'badge-sedimentation': return `bg-neutral/60 ${base}`
    default:                    return `bg-ink-muted/40 ${base}`  // badge-draft
  }
}

function onTriggerEnter() {
  if (collapseTimer) { clearTimeout(collapseTimer); collapseTimer = null }
  expanded.value = true
}

function onDrawerLeave() {
  collapseTimer = setTimeout(collapse, 200)
}

function onDrawerEnter() {
  if (collapseTimer) { clearTimeout(collapseTimer); collapseTimer = null }
}

function collapse() {
  if (collapseTimer) { clearTimeout(collapseTimer); collapseTimer = null }
  expanded.value = false
}

function onClickOutside(e: MouseEvent) {
  if (!expanded.value) return
  if (container.value && !container.value.contains(e.target as Node)) {
    collapse()
  }
}

function iconComponent(icon: 'edit' | 'eye') {
  return icon === 'edit' ? Edit : Eye
}

onMounted(() => document.addEventListener('click', onClickOutside))
onUnmounted(() => document.removeEventListener('click', onClickOutside))
</script>

<template>
  <div v-if="tabStore.tabs.length > 0" ref="container" class="tab-drawer-container">
    <!-- Collapsed: stacked tab edges -->
    <div class="tab-drawer-edges" @mouseenter="onTriggerEnter">
      <div
        v-for="tab in tabStore.tabs"
        :key="tab.id"
        class="tab-drawer-edge"
        :class="[
          statusColor(tab.status, tab.id === tabStore.activeTabId),
          tab.dirty ? 'tab-drawer-edge--dirty' : '',
        ]"
      />
    </div>

    <!-- Expanded drawer overlay -->
    <Transition name="drawer-slide">
      <div
        v-if="expanded"
        class="tab-drawer-panel"
        @mouseenter="onDrawerEnter"
        @mouseleave="onDrawerLeave"
      >
        <div class="tab-drawer-header">
          <span class="text-xs font-semibold uppercase tracking-wider text-ink-muted">Open Tabs</span>
          <span class="text-[10px] font-semibold text-ink-muted bg-[#21262d] rounded-full px-1.5 py-0.5 leading-none">
            {{ tabStore.tabs.length }}
          </span>
        </div>

        <div class="tab-drawer-list">
          <div
            v-for="tab in tabStore.tabs"
            :key="tab.id"
            class="tab-drawer-item"
            :class="{ 'tab-drawer-item--active': tab.id === tabStore.activeTabId }"
            role="button"
            tabindex="0"
            @click="tabStore.activateTab(tab.id)"
            @keydown.enter="tabStore.activateTab(tab.id)"
          >
            <component :is="iconComponent(tab.icon)" class="w-4 h-4 shrink-0 opacity-70" stroke-width="2" />
            <span
              class="w-2 h-2 rounded-full shrink-0"
              :class="statusColor(tab.status, tab.id === tabStore.activeTabId)"
              :title="tab.status"
            />
            <span class="tab-drawer-item-title">{{ tab.title }}</span>
            <span v-if="tab.dirty" class="tab-drawer-dirty-dot" />
            <button
              class="tab-drawer-close-btn"
              aria-label="Close tab"
              @click.stop="emit('close-tab', tab.id)"
            >
              <X :size="16" stroke-width="2" />
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* Container — positioned in App.vue's relative wrapper */
.tab-drawer-container { position: relative; z-index: 40; }

/* Collapsed edges (stacked vertically, left edge of viewport) */
.tab-drawer-edges {
  position: fixed; left: 0; top: 4rem; bottom: 0;
  width: 8px; display: flex; flex-direction: column;
  gap: 2px; padding-top: 4px; z-index: 41; cursor: default;
}
.tab-drawer-edge {
  width: 6px; min-height: 4px; flex-shrink: 0;
  border-radius: 0 3px 3px 0;
  transition: background-color 200ms ease, opacity 200ms ease;
}
.tab-drawer-edge--dirty::after {
  content: ''; display: block;
  width: 3px; height: 3px; border-radius: 50%;
  background: #7b8c9e; margin: 2px auto 0;
}

/* Expanded panel */
.tab-drawer-panel {
  position: fixed; left: 0; top: 4rem; bottom: 0;
  width: 220px; background-color: #0d1117;
  border-right: 1px solid #30363d;
  box-shadow: 4px 0 16px rgba(0, 0, 0, 0.4);
  border-radius: 0 0.5rem 0.5rem 0;
  z-index: 42; display: flex; flex-direction: column;
}

/* Header */
.tab-drawer-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 12px 8px; border-bottom: 1px solid #30363d;
}

/* Tab list */
.tab-drawer-list { flex: 1; overflow-y: auto; padding: 4px 0; }

/* Tab item — matches app's btn-ghost hover pattern */
.tab-drawer-item {
  display: flex; align-items: center; gap: 6px;
  width: 100%; padding: 6px 8px;
  background: transparent; border: none;
  border-left: 2px solid transparent;
  color: #6e7681; font-size: 0.75rem;
  cursor: pointer; text-align: left;
  transition: background-color 200ms ease, color 200ms ease;
}
.tab-drawer-item:hover {
  background-color: #21262d; color: #e6edf3;
}
.tab-drawer-item--active {
  background-color: rgba(123, 140, 158, 0.12);
  border-left-color: #7b8c9e; color: #e6edf3;
}
.tab-drawer-item--active:hover { background-color: rgba(123, 140, 158, 0.18); }
.tab-drawer-item:focus-visible {
  outline: 2px solid #7b8c9e; outline-offset: -2px; border-radius: 6px;
}

.tab-drawer-item-title { flex: 1; min-width: 0; line-height: 1.4; word-break: break-word; }

/* Dirty dot */
.tab-drawer-dirty-dot {
  flex-shrink: 0; width: 8px; height: 8px;
  border-radius: 50%; background-color: #7b8c9e;
}

/* Close button — visible on row hover */
.tab-drawer-close-btn {
  flex-shrink: 0; display: flex; align-items: center; justify-content: center;
  width: 20px; height: 20px; border: none; border-radius: 4px;
  background: transparent; color: inherit; cursor: pointer;
  opacity: 0; transition: opacity 150ms ease;
}
.tab-drawer-item:hover .tab-drawer-close-btn { opacity: 1; }
.tab-drawer-close-btn:hover { background-color: rgba(255, 255, 255, 0.1); }

/* Slide transition — uses transform for GPU acceleration */
.drawer-slide-enter-active { transition: transform 200ms ease; }
.drawer-slide-leave-active { transition: transform 200ms ease; }
.drawer-slide-enter-from,
.drawer-slide-leave-to { transform: translateX(-100%); }
</style>
