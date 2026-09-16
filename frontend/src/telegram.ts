import { init, miniApp, retrieveRawInitData, viewport } from '@tma.js/sdk-react'

let initData: string | undefined

export function setupTelegram() {
  try {
    init()
    initData = retrieveRawInitData()
    if (miniApp.mount.isAvailable()) miniApp.mount()
    if (miniApp.ready.isAvailable()) miniApp.ready()
    if (viewport.mount.isAvailable()) {
      void viewport.mount().then(() => {
        if (viewport.expand.isAvailable()) viewport.expand()
      })
    }
  } catch {
    initData = undefined
  }
}

export function getTelegramInitData() {
  return initData
}
