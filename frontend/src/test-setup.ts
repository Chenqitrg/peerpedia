import { vi } from 'vitest'
import { config } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import enUS from './locales/en-US.json'

// Ensure localStorage is available as a global for all test environments
// (Node with experimental globalThis.localStorage, jsdom, etc.)
// Use a shared mock store to avoid conflicts between environments.
const _lsStore: Record<string, string> = {}
const _mockStorage = {
  getItem: vi.fn((key: string) => _lsStore[key] ?? null),
  setItem: vi.fn((key: string, value: string) => { _lsStore[key] = value }),
  removeItem: vi.fn((key: string) => { delete _lsStore[key] }),
  clear: vi.fn(() => { for (const k of Object.keys(_lsStore)) delete _lsStore[k] }),
  get length() { return Object.keys(_lsStore).length },
  key: vi.fn((index: number) => Object.keys(_lsStore)[index] ?? null),
}

Object.defineProperty(globalThis, 'localStorage', {
  value: _mockStorage,
  writable: true,
  configurable: true,
})

// Register vue-i18n globally for all tests
const i18n = createI18n({
  legacy: false,
  locale: 'en-US',
  fallbackLocale: 'en-US',
  messages: { 'en-US': enUS },
})

config.global.plugins = [...(config.global.plugins || []), i18n]
