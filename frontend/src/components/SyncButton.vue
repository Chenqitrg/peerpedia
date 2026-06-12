<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Wifi, WifiOff } from 'lucide-vue-next'
import { useNetworkStatus } from '../composables/useNetworkStatus'

const { t } = useI18n()
const { connectionState, flash, connect, disconnect } = useNetworkStatus()

const label = computed(() => {
  switch (connectionState.value) {
    case 'connecting': return t('nav.syncConnecting')
    case 'synced': return t('nav.syncSynced')
    default: return t('nav.syncIdle')
  }
})

const ariaLabel = computed(() =>
  connectionState.value === 'synced'
    ? t('nav.syncDisconnectAria')
    : t('nav.syncConnectAria')
)

function handleClick() {
  if (connectionState.value === 'synced' || connectionState.value === 'connecting') {
    disconnect()
  } else {
    connect()
  }
}
</script>

<template>
  <button
    class="sync-btn"
    :class="{
      'sync-btn--idle': connectionState === 'idle' && !flash,
      'sync-btn--connecting': connectionState === 'connecting',
      'sync-btn--synced': connectionState === 'synced',
      'sync-btn--flash': flash,
    }"
    :aria-label="ariaLabel"
    @click="handleClick"
  >
    <!-- Dot -->
    <span
      class="sync-dot"
      :class="{
        'sync-dot--idle': connectionState === 'idle' && !flash,
        'sync-dot--connecting': connectionState === 'connecting',
        'sync-dot--synced': connectionState === 'synced',
        'sync-dot--flash': flash,
      }"
    />
    <!-- Icon -->
    <Wifi v-if="connectionState === 'connecting' || connectionState === 'synced'" class="w-3.5 h-3.5" stroke-width="2" />
    <WifiOff v-else class="w-3.5 h-3.5" stroke-width="2" />
    <!-- Label -->
    <span class="sync-label">{{ label }}</span>
  </button>
</template>

<style scoped>
.sync-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: none;
  border-radius: 8px;
  background: #21262d;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: background-color 200ms ease;
  min-height: 28px;
}
.sync-btn:hover {
  background: #30363d;
}
.sync-btn:focus-visible {
  outline: 2px solid #7b8c9e;
  outline-offset: 2px;
  border-radius: 8px;
}

/* Label text */
.sync-label {
  color: #6e7681;
  transition: color 300ms ease;
}
.sync-btn--connecting .sync-label {
  color: #e6edf3;
}
.sync-btn--synced .sync-label {
  color: #238636;
}

/* Dot */
.sync-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  transition: background-color 300ms ease, box-shadow 300ms ease;
}
.sync-dot--idle {
  background-color: #6e7681;
}
.sync-dot--connecting {
  background-color: #e6edf3;
  animation: pulse-dot 1.2s ease-in-out infinite;
}
.sync-dot--synced {
  background-color: #238636;
  box-shadow: 0 0 6px rgba(35, 134, 54, 0.4);
}
.sync-dot--flash {
  background-color: #d73a49;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
