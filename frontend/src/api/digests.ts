import type { DigestArchiveItem, DigestDetail } from '../types/digest'
import { apiBlob, apiRequest } from './client'

export function listDigests() {
  return apiRequest<DigestArchiveItem[]>('/digests')
}

export function getDigest(date: string) {
  return apiRequest<DigestDetail>(`/digests/${date}`)
}

export async function downloadDigestPdf(date: string) {
  const blob = await apiBlob(`/digests/${date}/pdf`)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `daily_digest_${date}.pdf`
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000)
}
