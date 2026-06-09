// Commit message popup state machine — extracted from EditorPage.vue.
// Manages the popup lifecycle: open → user types → confirm/cancel.
//
// Usage:
//   const { showCommitPopup, tempCommitMsg, openCommitPopup, confirmCommit, cancelCommit } =
//     useCommitFlow((msg) => { commitMsg.value = msg; saveDraft() })

import { ref } from 'vue'

export function useCommitFlow(onConfirm: (message: string) => Promise<void>) {
  const showCommitPopup = ref(false)
  const tempCommitMsg = ref('')

  /** Open the popup, seeding with the current commit message. */
  function openCommitPopup(currentMsg: string) {
    tempCommitMsg.value = currentMsg
    showCommitPopup.value = true
  }

  /** Confirm: trim message, await onConfirm, close popup. */
  async function confirmCommit() {
    const msg = tempCommitMsg.value.trim() || 'Save draft'
    showCommitPopup.value = false
    await onConfirm(msg)
  }

  /** Cancel and close the popup. */
  function cancelCommit() {
    showCommitPopup.value = false
  }

  return { showCommitPopup, tempCommitMsg, openCommitPopup, confirmCommit, cancelCommit }
}
