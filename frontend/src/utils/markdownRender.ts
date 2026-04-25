/** Strip BOM / ZWSP etc. that break heading detection when pasted from docs. */
function stripInvisibleMarkdownNoise(s: string): string {
  return s
    .replace(/\uFEFF/g, '')
    .replace(/\u200B/g, '')
    .replace(/\u200C/g, '')
    .replace(/\u200D/g, '')
    .replace(/\u2060/g, '')
}

/**
 * Small, dependency-free markdown → HTML for UI bubbles.
 * Supports: fenced ``` blocks, ### headings, **bold**, - / * / 1. lists, paragraphs, line breaks.
 * Not a full CommonMark implementation; tuned for this project's LLM outputs.
 */
export function markdownToSafeHtml(markdown: string): string {
  const text = stripInvisibleMarkdownNoise(markdown).replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const lines = text.split('\n')

  const esc = (s: string) =>
    s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;')

  const escAttr = (s: string) => esc(s).replace(/`/g, '&#096;')

  const mdInline = (s: string) => {
    const codeSpans: string[] = []
    const withoutCode = s.replace(/`([^`]+)`/g, (_, code: string) => {
      const token = `\u0000CODE${codeSpans.length}\u0000`
      codeSpans.push(`<code class="md-inline-code">${esc(code)}</code>`)
      return token
    })

    let html = esc(withoutCode)
    html = html.replace(
      /\[([^\]]+)\]\((https?:\/\/[^)\s]+|mailto:[^)\s]+)\)/g,
      (_, label: string, url: string) =>
        `<a href="${escAttr(url)}" target="_blank" rel="noreferrer">${label}</a>`
    )
    html = html
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^\*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
      .replace(/(^|[^_])_([^_\n]+)_/g, '$1<em>$2</em>')

    return html.replace(/\u0000CODE(\d+)\u0000/g, (_, idx: string) => codeSpans[Number(idx)] ?? '')
  }

  const out: string[] = []
  const para: string[] = []

  let inFence = false
  const fenceBuf: string[] = []

  let listType: 'ul' | 'ol' | null = null
  let listItem: string[] = []
  let inBlockquote = false

  const flushListItem = () => {
    if (listItem.length === 0) return
    out.push(`<li>${listItem.join('<br />')}</li>`)
    listItem = []
  }

  const closeList = () => {
    if (listType) {
      flushListItem()
      out.push(`</${listType}>`)
      listType = null
    }
  }

  const openList = (nextType: 'ul' | 'ol') => {
    if (listType === nextType) {
      flushListItem()
      return
    }
    closeList()
    out.push(`<${nextType} class="md-${nextType}">`)
    listType = nextType
  }

  const closeBlockquote = () => {
    if (!inBlockquote) return
    out.push('</blockquote>')
    inBlockquote = false
  }

  const flushParagraph = () => {
    if (para.length === 0) return
    const content = para.join('<br />').trim()
    if (content) out.push(`<p>${content}</p>`)
    para.length = 0
  }

  const flushFence = () => {
    if (fenceBuf.length === 0) return
    const code = esc(fenceBuf.join('\n'))
    fenceBuf.length = 0
    out.push(`<pre class="md-fence"><code>${code}</code></pre>`)
  }

  for (const raw of lines) {
    const trimmedRight = raw.trimEnd()
    const trimmed = trimmedRight.trim()

    // Fenced code blocks (often emitted by models even when not "real code")
    if (trimmed.startsWith('```')) {
      if (!inFence) {
        closeList()
        closeBlockquote()
        flushParagraph()
        inFence = true
      } else {
        flushFence()
        inFence = false
      }
      continue
    }
    if (inFence) {
      fenceBuf.push(raw)
      continue
    }

    if (!trimmed) {
      closeList()
      closeBlockquote()
      flushParagraph()
      continue
    }

    const hr = trimmed.match(/^([-*_])(?:\s*\1){2,}$/)
    if (hr) {
      closeList()
      closeBlockquote()
      flushParagraph()
      out.push('<hr class="md-hr" />')
      continue
    }

    const bq = trimmed.match(/^>\s?(.*)$/)
    if (bq) {
      closeList()
      flushParagraph()
      if (!inBlockquote) {
        out.push('<blockquote class="md-blockquote">')
        inBlockquote = true
      }
      if (bq[1].trim()) out.push(`<p>${mdInline(bq[1].trim())}</p>`)
      continue
    }

    // Allow `### 标题` or `###标题` (no space after #) — models often omit the space.
    const hm = trimmed.match(/^(#{1,6})\s*(.+)$/)
    if (hm) {
      closeList()
      closeBlockquote()
      flushParagraph()
      const level = hm[1].length
      const tagLevel = Math.min(6, Math.max(3, level))
      const tag = `h${tagLevel}`
      out.push(`<${tag} class="md-heading">${mdInline(hm[2])}</${tag}>`)
      continue
    }

    const ol = trimmed.match(/^(\d+)\.\s+(.+)$/)
    if (ol) {
      closeBlockquote()
      flushParagraph()
      openList('ol')
      listItem.push(mdInline(ol[2]))
      continue
    }

    const ul = trimmed.match(/^[-*]\s+(.+)$/)
    if (ul) {
      closeBlockquote()
      flushParagraph()
      openList('ul')
      listItem.push(mdInline(ul[1]))
      continue
    }

    if (listType && /^\s{2,}\S/.test(raw)) {
      listItem.push(mdInline(trimmed))
      continue
    }

    closeList()
    closeBlockquote()
    para.push(mdInline(trimmed))
  }

  if (inFence) {
    // Unclosed fence: still render as code for readability
    flushFence()
  }
  closeList()
  closeBlockquote()
  flushParagraph()

  return out.join('')
}
