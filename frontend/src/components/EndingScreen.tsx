import { useEffect, useState } from 'react'
import './EndingScreen.css'

export function EndingScreen() {
  const [phase, setPhase] = useState<'fade' | 'show'>('fade')

  useEffect(() => {
    // Staggered entrance animation
    const t1 = setTimeout(() => setPhase('show'), 200)
    return () => clearTimeout(t1)
  }, [])

  return (
    <div className={`ending-overlay ${phase === 'show' ? 'ending-overlay--visible' : ''}`}>
      <div className="ending-bg-particles">
        {Array.from({ length: 12 }).map((_, i) => (
          <span key={i} className="ending-particle" style={{
            '--dx': `${(Math.random() - 0.5) * 300}px`,
            '--dy': `${(Math.random() - 0.5) * 300}px`,
            '--delay': `${i * 0.15}s`,
            '--size': `${4 + Math.random() * 6}px`,
            left: `${Math.random() * 100}%`,
            top: `${Math.random() * 100}%`,
          } as React.CSSProperties} />
        ))}
      </div>

      <div className="ending-content">
        <div className="ending-badge">公众科学日 · 分会场</div>
        <h1 className="ending-title">谢谢大家</h1>
        <p className="ending-subtitle">感谢收看</p>
        <div className="ending-divider" />
        <p className="ending-meta">
          RISC-V 三国杀 · 论坛交锋 demo
        </p>
        <p className="ending-meta-sub">
          RISC-V vs x86 vs ARM — Agent 时代算力格局
        </p>
      </div>
    </div>
  )
}
