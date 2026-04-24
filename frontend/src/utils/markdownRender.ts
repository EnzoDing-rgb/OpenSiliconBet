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

  const mdInline = (s: string) => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')

  const out: string[] = []
  const para: string[] = []

  let inFence = false
  const fenceBuf: string[] = []

  let inUl = false
  let inOl = false

  const closeLists = () => {
    if (inUl) {
      out.push('</ul>')
      inUl = false
    }
    if (inOl) {
      out.push('</ol>')
      inOl = false
    }
  }

  const flushParagraph = () => {
    if (para.length === 0) return
    const content = para.join(' ').trim()
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
        closeLists()
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
      closeLists()
      flushParagraph()
      continue
    }

    // Allow `### 标题` or `###标题` (no space after #) — models often omit the space.
    const hm = trimmed.match(/^(#{1,6})\s*(.+)$/)
    if (hm) {
      closeLists()
      flushParagraph()
      const level = hm[1].length
      const tagLevel = Math.min(6, Math.max(3, level))
      const tag = `h${tagLevel}`
      out.push(`<${tag} class="md-heading">${mdInline(hm[2])}</${tag}>`)
      continue
    }

    const ol = trimmed.match(/^(\d+)\.\s+(.+)$/)
    if (ol) {
      flushParagraph()
      if (inUl) {
        out.push('</ul>')
        inUl = false
      }
      if (!inOl) {
        out.push('<ol class="md-ol">')
        inOl = true
      }
      out.push(`<li>${mdInline(ol[2])}</li>`)
      continue
    }

    const ul = trimmed.match(/^[-*]\s+(.+)$/)
    if (ul) {
      flushParagraph()
      if (inOl) {
        out.push('</ol>')
        inOl = false
      }
      if (!inUl) {
        out.push('<ul class="md-ul">')
        inUl = true
      }
      out.push(`<li>${mdInline(ul[1])}</li>`)
      continue
    }

    closeLists()
    para.push(mdInline(trimmed))
  }

  if (inFence) {
    // Unclosed fence: still render as code for readability
    flushFence()
  }
  closeLists()
  flushParagraph()

  return out.join('')
}
