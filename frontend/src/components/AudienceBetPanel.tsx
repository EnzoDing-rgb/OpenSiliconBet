import { useCallback, useMemo, useState } from 'react'
import { displayPricesFromVotes, type CampVotes } from '../utils/votePrice'
import './AudienceBetPanel.css'

export type SeriesPoint = CampVotes & { index: number }

function seedPoint(): SeriesPoint {
  return { ...displayPricesFromVotes({ riscv: 0, x86: 0, arm: 0 }), index: 0 }
}

function ChartThreeLines({ series }: { series: SeriesPoint[] }) {
  const w = 400
  const h = 140
  const pad = { t: 14, r: 10, b: 26, l: 10 }
  const innerW = w - pad.l - pad.r
  const innerH = h - pad.t - pad.b

  const paths = useMemo(() => {
    if (series.length === 0) return { riscv: '', x86: '', arm: '' }
    const vals: number[] = []
    for (const p of series) {
      vals.push(p.riscv, p.x86, p.arm)
    }
    let ymin = Math.min(...vals)
    let ymax = Math.max(...vals)
    if (ymax - ymin < 1e-9) {
      ymin -= 0.25
      ymax += 0.25
    }
    const span = ymax - ymin || 1
    ymin -= span * 0.06
    ymax += span * 0.06
    const n = series.length
    const xAt = (i: number) => {
      if (n === 1) return pad.l + innerW / 2
      return pad.l + (i / (n - 1)) * innerW
    }
    const yAt = (v: number) => pad.t + innerH * (1 - (v - ymin) / (ymax - ymin))

    const line = (key: keyof CampVotes) =>
      series.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xAt(i).toFixed(1)} ${yAt(p[key]).toFixed(1)}`).join(' ')

    return {
      riscv: line('riscv'),
      x86: line('x86'),
      arm: line('arm'),
    }
  }, [series, innerW, innerH, pad.l, pad.t])

  return (
    <svg className="audience-bet-chart" viewBox={`0 0 ${w} ${h}`} aria-hidden>
      <rect x={0} y={0} width={w} height={h} className="audience-bet-chart__bg" rx={6} />
      <path className="audience-bet-chart__line audience-bet-chart__line--riscv" d={paths.riscv} fill="none" />
      <path className="audience-bet-chart__line audience-bet-chart__line--x86" d={paths.x86} fill="none" />
      <path className="audience-bet-chart__line audience-bet-chart__line--arm" d={paths.arm} fill="none" />
      <text x={pad.l} y={h - 6} className="audience-bet-chart__axis">
        横轴：每次点击后的采样点（左→右）
      </text>
    </svg>
  )
}

export function AudienceBetPanel() {
  const [votes, setVotes] = useState<CampVotes>({ riscv: 0, x86: 0, arm: 0 })
  const [series, setSeries] = useState<SeriesPoint[]>(() => [seedPoint()])

  const prices = useMemo(() => displayPricesFromVotes(votes), [votes])

  const bump = useCallback((key: keyof CampVotes) => {
    setVotes((v) => {
      const next = { ...v, [key]: v[key] + 1 }
      const p = displayPricesFromVotes(next)
      setSeries((s) => [...s, { ...p, index: s.length }])
      return next
    })
  }, [])

  const reset = useCallback(() => {
    setVotes({ riscv: 0, x86: 0, arm: 0 })
    setSeries([seedPoint()])
  }, [])

  return (
    <section className="audience-bet" aria-labelledby="audience-bet-title">
      <h2 id="audience-bet-title" className="audience-bet__title">
        押注演示（Which one you bet?）
      </h2>
      <p className="audience-bet__hint">
        点阵营 → 票数 +1（可连点）。展示价为启发式 demo 指数，非真实行情。刷新页面清空。
      </p>

      <div className="audience-bet__row">
        <button type="button" className="audience-bet__camp audience-bet__camp--riscv" onClick={() => bump('riscv')}>
          <span className="audience-bet__camp-name">RISC-V</span>
          <span className="audience-bet__camp-sub">点一下 +1 票</span>
          <span className="audience-bet__camp-count">{votes.riscv}</span>
          <span className="audience-bet__camp-price">展示 ≈ {prices.riscv.toFixed(2)}</span>
        </button>
        <button type="button" className="audience-bet__camp audience-bet__camp--x86" onClick={() => bump('x86')}>
          <span className="audience-bet__camp-name">x86</span>
          <span className="audience-bet__camp-sub">点一下 +1 票</span>
          <span className="audience-bet__camp-count">{votes.x86}</span>
          <span className="audience-bet__camp-price">展示 ≈ {prices.x86.toFixed(2)}</span>
        </button>
        <button type="button" className="audience-bet__camp audience-bet__camp--arm" onClick={() => bump('arm')}>
          <span className="audience-bet__camp-name">ARM</span>
          <span className="audience-bet__camp-sub">点一下 +1 票</span>
          <span className="audience-bet__camp-count">{votes.arm}</span>
          <span className="audience-bet__camp-price">展示 ≈ {prices.arm.toFixed(2)}</span>
        </button>
      </div>

      <div className="audience-bet__chart-wrap">
        <p className="audience-bet__chart-legend">
          <span className="lgd lgd--riscv">— RISC-V</span>
          <span className="lgd lgd--x86">— x86</span>
          <span className="lgd lgd--arm">— ARM</span>
        </p>
        <ChartThreeLines series={series} />
      </div>

      <div className="audience-bet__footer">
        <button type="button" className="audience-bet__reset" onClick={reset}>
          重置本页演示
        </button>
        <p className="audience-bet__legal">
          演示用 · 非行情 · 非投资建议 · 连点可刷票
        </p>
      </div>
    </section>
  )
}
