import { useCallback, useEffect, useMemo, useState } from 'react'
import { CAMP_BASE, displayPricesFromVotes, type CampVotes } from '../utils/votePrice'
import { getBetState, postBetVote, postBetReset } from '../api'
import './AudienceBetPanel.css'

function ChartThreeBars({ prices }: { prices: CampVotes }) {
  const w = 420
  const h = 220
  const pad = { t: 16, r: 12, b: 36, l: 46 }
  const innerW = w - pad.l - pad.r
  const innerH = h - pad.t - pad.b
  const camps = [
    { key: 'riscv' as const, label: 'RISC-V', color: '#4ade80' },
    { key: 'x86' as const, label: 'x86', color: '#60a5fa' },
    { key: 'arm' as const, label: 'ARM', color: '#c084fc' },
  ]

  const vals = camps.flatMap((camp) => [CAMP_BASE[camp.key], prices[camp.key]])
  const ymin = Math.min(...vals) - 6
  const ymax = Math.max(...vals) + 6
  const yAt = (v: number) => pad.t + innerH * (1 - (v - ymin) / (ymax - ymin))
  const barSlot = innerW / camps.length
  const barW = Math.min(68, barSlot * 0.52)
  const tickCount = 5
  const ticks = Array.from({ length: tickCount }, (_, i) => ymin + (i / (tickCount - 1)) * (ymax - ymin))

  return (
    <svg className="audience-bet-chart" viewBox={`0 0 ${w} ${h}`} aria-hidden>
      <rect x={0} y={0} width={w} height={h} className="audience-bet-chart__bg" rx={8} />
      {ticks.map((yv, i) => (
        <g key={`g-${i}`}>
          <line
            className="audience-bet-chart__grid"
            x1={pad.l}
            x2={pad.l + innerW}
            y1={yAt(yv)}
            y2={yAt(yv)}
          />
          <text className="audience-bet-chart__ylabel" x={pad.l - 6} y={yAt(yv) + 3} textAnchor="end">
            {yv.toFixed(0)}
          </text>
        </g>
      ))}
      {camps.map((camp, i) => {
        const x = pad.l + barSlot * i + (barSlot - barW) / 2
        const base = CAMP_BASE[camp.key]
        const total = prices[camp.key]
        const baseY = yAt(base)
        const totalY = yAt(total)
        const zeroY = yAt(ymin)
        return (
          <g key={camp.key}>
            <rect
              className="audience-bet-chart__bar-base"
              x={x}
              y={baseY}
              width={barW}
              height={Math.max(0, zeroY - baseY)}
              rx={10}
            />
            <rect
              className={`audience-bet-chart__bar audience-bet-chart__bar--${camp.key}`}
              x={x}
              y={totalY}
              width={barW}
              height={Math.max(0, baseY - totalY)}
              rx={10}
            />
            <text className="audience-bet-chart__bar-value" x={x + barW / 2} y={Math.max(20, totalY - 8)} textAnchor="middle">
              {total.toFixed(2)}
            </text>
            <text className="audience-bet-chart__bar-label" x={x + barW / 2} y={h - 12} textAnchor="middle">
              {camp.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

export function AudienceBetPanel() {
  const [votes, setVotes] = useState<CampVotes>({ riscv: 0, x86: 0, arm: 0 })

  const prices = useMemo(() => displayPricesFromVotes(votes), [votes])

  // Poll server for live vote counts every 2 seconds
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      try {
        const state = await getBetState()
        if (!cancelled) setVotes(state)
      } catch { /* network not ready yet */ }
    }
    poll()
    const timer = setInterval(poll, 2000)
    return () => { cancelled = true; clearInterval(timer) }
  }, [])

  const bump = useCallback(async (key: keyof CampVotes) => {
    try {
      const state = await postBetVote(key)
      setVotes(state)
    } catch { /* offline, ignore */ }
  }, [])

  const reset = useCallback(async () => {
    try {
      const state = await postBetReset()
      setVotes(state)
    } catch { /* offline, ignore */ }
  }, [])

  return (
    <section className="audience-bet" aria-labelledby="audience-bet-title">
      <h2 id="audience-bet-title" className="audience-bet__title">
        押注演示（Which one you bet?）
      </h2>
      <p className="audience-bet__hint">
        点阵营 → 票数 +1（可连点）。实时投票，所有人看到的票数一致。展示价为启发式 demo 指数，非真实行情。
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
          <span className="lgd lgd--base">浅色 = base</span>
          <span className="lgd lgd--riscv">绿色增量 = RISC-V</span>
          <span className="lgd lgd--x86">蓝色增量 = x86</span>
          <span className="lgd lgd--arm">紫色增量 = ARM</span>
        </p>
        <ChartThreeBars prices={prices} />
      </div>

      <div className="audience-bet__qr">
        <img
          className="audience-bet__qr-img"
          src={`https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(window.location.origin)}`}
          alt="扫码参与实时投票"
          width={150}
          height={150}
        />
        <div className="audience-bet__qr-text">
          <p className="audience-bet__qr-label">扫码参与实时投票</p>
          <p className="audience-bet__qr-url">{window.location.origin}</p>
        </div>
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
