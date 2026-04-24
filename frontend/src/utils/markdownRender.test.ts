import { describe, expect, it } from 'vitest'
import { markdownToSafeHtml } from './markdownRender'

describe('markdownToSafeHtml', () => {
  it('renders ATX heading with space', () => {
    const html = markdownToSafeHtml('### 主张\n\n正文')
    expect(html).toContain('<h3')
    expect(html).toContain('主张')
    expect(html).toContain('<p>')
    expect(html).toContain('正文')
  })

  it('renders ATX heading without space after hashes', () => {
    const html = markdownToSafeHtml('###主张\n\n段落')
    expect(html).toContain('<h3')
    expect(html).toContain('主张')
    expect(html).toContain('段落')
  })

  it('strips BOM and ZWSP so headings still parse', () => {
    const html = markdownToSafeHtml('\uFEFF### 开场\n\u200B## 不应匹配为标题')
    expect(html).toContain('开场')
    // second line: ## after strip is still ## at line start — should be heading h3 (clamped)
    expect(html).toMatch(/md-heading/)
  })

  it('renders **bold** in paragraph', () => {
    const html = markdownToSafeHtml('这是**重点**句')
    expect(html).toContain('<strong>重点</strong>')
  })

  it('escapes HTML then applies bold', () => {
    const html = markdownToSafeHtml('a <b>x</b> and **y**')
    expect(html).toContain('&lt;b&gt;')
    expect(html).toContain('<strong>y</strong>')
  })

  it('ordered list', () => {
    const html = markdownToSafeHtml('1. 第一项\n2. 第二项')
    expect(html).toContain('<ol')
    expect(html).toContain('<li>')
    expect(html).toContain('第一项')
    expect(html).toContain('第二项')
  })

  it('unordered list', () => {
    const html = markdownToSafeHtml('- a\n* b')
    expect(html).toContain('<ul')
    expect(html.match(/<li>/g)?.length).toBe(2)
  })

  it('fenced code block', () => {
    const html = markdownToSafeHtml('```\nline1\nline2\n```')
    expect(html).toContain('<pre')
    expect(html).toContain('line1')
    expect(html).toContain('line2')
    expect(html).not.toContain('<strong>')
  })

  it('mixed sample like judge output', () => {
    const md = `### 对比维度

**滴滴案**侧重数据主权。

1. 监管介入
2. 企业整改

- 要点 A
- 要点 B

收尾。`
    const html = markdownToSafeHtml(md)
    expect(html).toContain('对比维度')
    expect(html).toContain('<strong>滴滴案</strong>')
    expect(html).toContain('<ol')
    expect(html).toContain('<ul')
    expect(html).toContain('收尾')
  })

  it('unclosed fence still renders code', () => {
    const html = markdownToSafeHtml('```\nonly')
    expect(html).toContain('<pre')
    expect(html).toContain('only')
  })
})
