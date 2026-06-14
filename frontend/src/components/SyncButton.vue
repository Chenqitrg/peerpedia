<!-- SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors -->
<!-- SPDX-License-Identifier: CC-BY-NC-SA-4.0 -->

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Wifi, WifiOff } from 'lucide-vue-next'
import { useNetworkStatus } from '../composables/useNetworkStatus'
import { useAutoSync } from '../composables/useAutoSync'

const { t } = useI18n()
const { connectionState, flash, connect, disconnect } = useNetworkStatus()
const { pendingCount } = useAutoSync()

const tooltip = computed(() => {
  switch (connectionState.value) {
    case 'connecting': return t('nav.syncConnecting')
    case 'synced': return t('nav.syncDisconnectAria')
    default:
      return pendingCount.value > 0
        ? `${pendingCount.value} pending sync(s)`
        : t('nav.syncConnectAria')
  }
})

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
      'sync-btn--synced': connectionState === 'synced',
      'sync-btn--flash': flash,
    }"
    :title="tooltip"
    :aria-label="tooltip"
    @click="handleClick"
  >
    <Wifi
      v-if="connectionState === 'connecting' || connectionState === 'synced'"
      class="sync-icon"
      :class="{
        'sync-icon--connecting': connectionState === 'connecting',
        'sync-icon--synced': connectionState === 'synced',
      }"
      stroke-width="2"
    />
    <WifiOff
      v-else
      class="sync-icon"
      :class="{ 'sync-icon--flash': flash }"
      stroke-width="2"
    />
    <span
      v-if="connectionState === 'idle' && pendingCount > 0"
      class="sync-badge"
    >{{ pendingCount }}</span>
    <span
      class="sync-dot"
      :class="{
        'sync-dot--idle': connectionState === 'idle' && !flash,
        'sync-dot--connecting': connectionState === 'connecting',
        'sync-dot--synced': connectionState === 'synced',
        'sync-dot--flash': flash,
      }"
    />
  </button>
</template>

<style scoped>
.sync-btn {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  color: #6e7681;
  transition: background-color 200ms ease, color 200ms ease;
  flex-shrink: 0;
}
.sync-btn:hover {
  background: #21262d;
  color: #e6edf3;
}
.sync-btn:focus-visible {
  outline: 2px solid #7b8c9e;
  outline-offset: 2px;
}

/* Background tint on synced */
.sync-btn--synced {
  color: #79c0ff;
}

/* Flash: red background briefly */
.sync-btn--flash {
  color: #d73a49;
}

/* Icon */
.sync-icon {
  width: 16px;
  height: 16px;
  transition: color 300ms ease, filter 300ms ease;
}
.sync-icon--connecting {
  color: #e6edf3;
  animation: sync-pulse 1.2s ease-in-out infinite;
}
.sync-icon--synced {
  color: #79c0ff;
  filter: drop-shadow(0 0 4px rgba(121, 192, 255, 0.4));
}
.sync-icon--flash {
  color: #d73a49;
}

/* Pending count badge — red number below WiFi icon */
.sync-badge {
  position: absolute;
  bottom: -5px;
  right: -5px;
  min-width: 15px;
  height: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background-color: #d73a49;
  color: #fff;
  font-size: 9px;
  font-weight: 700;
  line-height: 1;
  padding: 0 3px;
  box-shadow: 0 0 0 1.5px #161b22;
}

/* Corner dot — 7px, positioned bottom-right */
.sync-dot {
  position: absolute;
  bottom: 4px;
  right: 4px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  border: 1.5px solid #161b22;
  flex-shrink: 0;
  transition: background-color 300ms ease, box-shadow 300ms ease;
}
.sync-dot--idle {
  background-color: #6e7681;
}
.sync-dot--connecting {
  background-color: #e6edf3;
  animation: sync-pulse 1.2s ease-in-out infinite;
}
.sync-dot--synced {
  background-color: #79c0ff;
  box-shadow: 0 0 5px rgba(121, 192, 255, 0.35);
}
.sync-dot--flash {
  background-color: #d73a49;
}

@keyframes sync-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
</style>
