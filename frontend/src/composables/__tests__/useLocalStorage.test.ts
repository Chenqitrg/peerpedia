import { describe, it, expect, beforeEach } from 'vitest'
import { loadString, saveString, loadJSON, saveJSON, remove } from '../useLocalStorage'

describe('useLocalStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  describe('string', () => {
    it('returns null for missing key', () => {
      expect(loadString('nonexistent')).toBeNull()
    })

    it('returns fallback for missing key', () => {
      expect(loadString('nonexistent', 'default')).toBe('default')
    })

    it('round-trips a string', () => {
      saveString('key', 'hello')
      expect(loadString('key')).toBe('hello')
    })

    it('returns stored value ignoring fallback', () => {
      saveString('key', 'actual')
      expect(loadString('key', 'fallback')).toBe('actual')
    })

    it('handles empty string', () => {
      saveString('key', '')
      expect(loadString('key')).toBe('')
    })

    it('handles unicode', () => {
      saveString('key', '你好世界 🌍')
      expect(loadString('key')).toBe('你好世界 🌍')
    })
  })

  describe('JSON', () => {
    it('returns null for missing key', () => {
      expect(loadJSON('nonexistent')).toBeNull()
    })

    it('returns fallback for missing key', () => {
      expect(loadJSON('nonexistent', { x: 1 })).toEqual({ x: 1 })
    })

    it('round-trips an object', () => {
      const obj = { name: 'test', count: 42 }
      saveJSON('key', obj)
      expect(loadJSON('key')).toEqual(obj)
    })

    it('round-trips an array', () => {
      const arr = [1, 'two', { three: true }]
      saveJSON('key', arr)
      expect(loadJSON('key')).toEqual(arr)
    })

    it('round-trips null', () => {
      saveJSON('key', null)
      expect(loadJSON('key')).toBeNull()
    })

    it('returns fallback on corrupt JSON', () => {
      localStorage.setItem('key', 'not-json{{{')
      expect(loadJSON('key', { fallback: true })).toEqual({ fallback: true })
    })

    it('returns null when no fallback on corrupt JSON', () => {
      localStorage.setItem('key', '{broken')
      expect(loadJSON('key')).toBeNull()
    })
  })

  describe('remove', () => {
    it('removes a stored key', () => {
      saveString('key', 'value')
      expect(loadString('key')).toBe('value')
      remove('key')
      expect(loadString('key')).toBeNull()
    })

    it('is a no-op on missing key', () => {
      expect(() => remove('nonexistent')).not.toThrow()
    })
  })

  describe('isolation', () => {
    it('each key is independent', () => {
      saveString('a', '1')
      saveJSON('b', { x: 2 })
      expect(loadString('a')).toBe('1')
      expect(loadJSON('b')).toEqual({ x: 2 })
      remove('a')
      expect(loadString('a')).toBeNull()
      expect(loadJSON('b')).toEqual({ x: 2 })
    })
  })
})
