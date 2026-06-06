import { vi } from 'vitest'
import { config } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import enUS from './locales/en-US.json'

// Node 22+ ships an experimental localStorage global that conflicts with jsdom.
// It's configurable, so delete it and install a mock before any module touches it.
delete (globalThis as any).localStorage
const store: Record<string, string> = {}
;(globalThis as any).localStorage = {
  getItem: vi.fn((key: string) => store[key] ?? null),
  setItem: vi.fn((key: string, value: string) => { store[key] = value }),
  removeItem: vi.fn((key: string) => { delete store[key] }),
  clear: vi.fn(() => { for (const k of Object.keys(store)) delete store[k] }),
  get length() { return Object.keys(store).length },
  key: vi.fn((index: number) => Object.keys(store)[index] ?? null),
}

// Register vue-i18n globally for all tests
const i18n = createI18n({
  legacy: false,
  locale: 'en-US',
  fallbackLocale: 'en-US',
  messages: { 'en-US': enUS },
})

config.global.plugins = [...(config.global.plugins || []), i18n]
