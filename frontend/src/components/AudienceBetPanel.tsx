import { useCallback, useMemo, useState } from 'react'
import { displayPricesFromVotes, type CampVotes } from '../utils/votePrice'
import './AudienceBetPanel.css'

export type SeriesPoint = CampVotes & { index: number }

function seedPoint(): SeriesPoint {
  return { ...displayPricesFromVotes({ riscv: 0, x86: 0, arm: 0 }), index: 0 }
}

function stepPathForSeries(
  series: SeriesPoint[],
  key: keyof CampVotes,
  xAt: (i: number) => number,
  yAt: (v: number) => number,
): string {
  const n = series.length
  if (n === 0) return ''
  if (n === 1) return `M ${xAt(0).toFixed(1)} ${yAt(series[0][key]).toFixed(1)}`
  let d = `M ${xAt(0).toFixed(1)} ${yAt(series[0][key]).toFixed(1)}`
  for (let i = 1; i < n; i++) {
    const x = xAt(i)
    const yPrev = yAt(series[i - 1][key])
    const yCurr = yAt(series[i][key])
    d += ` L ${x.toFixed(1)} ${yPrev.toFixed(1)} L ${x.toFixed(1)} ${yCurr.toFixed(1)}`
  }
  return d
}

function ChartThreeLines({ series }: { series: SeriesPoint[] }) {
  const w = 420
  const h = 168
  const pad = { t: 12, r: 12, b: 30, l: 44 }
  const innerW = w - pad.l - pad.r
  const innerH = h - pad.t - pad.b

  const layout = useMemo(() => {
    if (series.length === 0) {
      return {
        ymin: 99,
        ymax: 101,
        yTicks: [99, 99.5, 100, 100.5, 101],
        paths: { riscv: '', x86: '', arm: '' },
        gridYs: [] as number[],
        xAt: (_i: number) => pad.l + innerW / 2,
        yAt: (_v: number) => pad.t + innerH / 2,
      }
    }
    const vals: number[] = []
    for (const p of series) {
      vals.push(p.riscv, p.x86, p.arm)
    }
    let ymin = Math.min(...vals)
    let ymax = Math.max(...vals)
    const mid = (ymin + ymax) / 2
    const minSpan = 0.85
    if (ymax - ymin < minSpan) {
      ymin = mid - minSpan / 2
      ymax = mid + minSpan / 2
    }
    const span = ymax - ymin || 1
    ymin -= span * 0.04
    ymax += span * 0.04
    const n = series.length
    const xAt = (i: number) => {
      if (n === 1) return pad.l + innerW / 2
      return pad.l + (i / (n - 1)) * innerW
    }
    const yAt = (v: number) => pad.t + innerH * (1 - (v - ymin) / (ymax - ymin))
    const tickCount = 5
    const yTicks: number[] = []
    for (let t = 0; t < tickCount; t++) {
      yTicks.push(ymin + (t / (tickCount - 1)) * (ymax - ymin))
    }
    const gridYs = yTicks
    return {
      ymin,
      ymax,
      yTicks,
      gridYs,
      xAt,
      yAt,
      paths: {
        riscv: stepPathForSeries(series, 'riscv', xAt, yAt),
        x86: stepPathForSeries(series, 'x86', xAt, yAt),
        arm: stepPathForSeries(series, 'arm', xAt, yAt),
      },
    }
  }, [series, innerW, innerH, pad.l, pad.t])

  return (
    <svg className="audience-bet-chart" viewBox={`0 0 ${w} ${h}`} aria-hidden>
      <rect x={0} y={0} width={w} height={h} className="audience-bet-chart__bg" rx={8} />
      {layout.gridYs.map((yv, i) => (
        <g key={`g-${i}`}>
          <line
            className="audience-bet-chart__grid"
            x1={pad.l}
            x2={pad.l + innerW}
            y1={layout.yAt(yv)}
            y2={layout.yAt(yv)}
          />
          <text
            className="audience-bet-chart__ylabel"
            x={pad.l - 6}
            y={layout.yAt(yv) + 3}
            textAnchor="end"
          >
            {yv.toFixed(2)}
          </text>
        </g>
      ))}
      <path className="audience-bet-chart__line audience-bet-chart__line--riscv" d={layout.paths.riscv} fill="none" />
      <path className="audience-bet-chart__line audience-bet-chart__line--x86" d={layout.paths.x86} fill="none" />
      <path className="audience-bet-chart__line audience-bet-chart__line--arm" d={layout.paths.arm} fill="none" />
      <text x={pad.l} y={h - 8} className="audience-bet-chart__axis">
        横轴：每次点击后采样（左→右）· 阶梯折线
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
