import apiClient from './client'
import type { CompilePreviewPayload, CompilePreviewResponse } from './types'

export async function compilePreview(payload: CompilePreviewPayload): Promise<CompilePreviewResponse> {
  const res = await apiClient.post('/compile-preview', payload)
  return res.data
}
