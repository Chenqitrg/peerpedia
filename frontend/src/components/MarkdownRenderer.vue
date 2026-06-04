<script setup lang="ts">
defineProps<{ content: string }>()
</script>

<template>
  <div class="prose-custom" v-html="content" />
</template>
