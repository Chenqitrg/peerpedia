<template>
  <span class="network-status-badge" :data-tooltip="label">
    <span class="status-dot" :class="online ? 'online' : 'offline'" />
    <span class="status-label">{{ label }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useNetworkStatus } from '@/composables/useNetworkStatus'

const props = withDefaults(defineProps<{
  forceOffline?: boolean
}>(), {
  forceOffline: false,
})

const { isOnline } = useNetworkStatus()
const online = computed(() => props.forceOffline ? false : isOnline.value)
const label = computed(() => online.value ? '在线' : '离线')
</script>

<style scoped>
.network-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.05);
  font-size: 12px;
  color: #8b949e;
  cursor: default;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.online {
  background: #3fb950;
  box-shadow: 0 0 6px rgba(63, 185, 80, 0.4);
}

.status-dot.offline {
  background: #6e7681;
  box-shadow: none;
}

.status-label {
  white-space: nowrap;
}
</style>
