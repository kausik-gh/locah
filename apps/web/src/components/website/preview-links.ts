/** Keep an owner's draft credential on links within that draft, never external links. */
export function withPreviewToken(href: string, previewToken?: string): string {
  if (!previewToken || !href.startsWith('/') || href.startsWith('//')) return href
  const hashAt = href.indexOf('#')
  const path = hashAt >= 0 ? href.slice(0, hashAt) : href
  const hash = hashAt >= 0 ? href.slice(hashAt) : ''
  const separator = path.includes('?') ? '&' : '?'
  return `${path}${separator}preview_token=${encodeURIComponent(previewToken)}${hash}`
}
