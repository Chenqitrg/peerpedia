import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ThreadReplyInput from '../ThreadReplyInput.vue'

describe('ThreadReplyInput', () => {
  it('renders an input and a send button', () => {
    const wrapper = mount(ThreadReplyInput)
    expect(wrapper.find('input').exists()).toBe(true)
    expect(wrapper.find('button').exists()).toBe(true)
  })

  it('send button is disabled when input is empty', () => {
    const wrapper = mount(ThreadReplyInput, { props: { modelValue: '' } })
    const btn = wrapper.find('button')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('typing enables the send button', async () => {
    const wrapper = mount(ThreadReplyInput, { props: { modelValue: '' } })
    const input = wrapper.find('input')
    await input.setValue('hello')
    const btn = wrapper.find('button')
    expect(btn.attributes('disabled')).toBeUndefined()
  })

  it('clicking send emits the text and clears input', async () => {
    const wrapper = mount(ThreadReplyInput, { props: { modelValue: '' } })
    const input = wrapper.find('input')
    await input.setValue('hello world')
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('send')).toBeTruthy()
    expect(wrapper.emitted('send')![0]).toEqual(['hello world'])
    expect((input.element as HTMLInputElement).value).toBe('')
  })

  it('Enter key emits send', async () => {
    const wrapper = mount(ThreadReplyInput, { props: { modelValue: '' } })
    const input = wrapper.find('input')
    await input.setValue('test message')
    await input.trigger('keyup.enter')
    expect(wrapper.emitted('send')).toBeTruthy()
    expect(wrapper.emitted('send')![0]).toEqual(['test message'])
  })

  it('empty input does not emit on Enter', async () => {
    const wrapper = mount(ThreadReplyInput, { props: { modelValue: '' } })
    await wrapper.find('input').trigger('keyup.enter')
    expect(wrapper.emitted('send')).toBeFalsy()
  })

  it('shows "Sending..." placeholder when disabled', () => {
    const wrapper = mount(ThreadReplyInput, { props: { modelValue: '', disabled: true } })
    const input = wrapper.find('input')
    expect(input.attributes('placeholder')).toBe('Sending...')
  })
})
