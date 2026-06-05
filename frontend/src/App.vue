<template>
  <div id="app" class="min-h-screen bg-page flex flex-col">
    <NavBar />
    <main class="flex-1 w-full max-w-content mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-12">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import NavBar from './components/NavBar.vue'
</script>
