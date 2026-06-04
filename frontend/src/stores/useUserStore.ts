import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const stored = localStorage.getItem('viewer')
  const viewer = ref<any>(stored ? JSON.parse(stored) : null)

  function setViewer(user: any) {
    viewer.value = user
    localStorage.setItem('viewer', JSON.stringify(user))
  }

  function clearViewer() {
    viewer.value = null
    localStorage.removeItem('viewer')
  }

  return {
    viewer,
    setViewer,
    clearViewer,
  }
})
