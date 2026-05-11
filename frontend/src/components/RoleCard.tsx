import './RoleCard.css'

interface RoleCardProps {
  name: string
  school: string
  avatarSrc: string
  accent: string
  isLeft: boolean
  /** 圆桌席位：更小头像、纵向排布，适合绝对定位席位 */
  variant?: 'default' | 'seat'
}

export function RoleCard({ name, school, avatarSrc, accent, isLeft, variant = 'default' }: RoleCardProps) {
  const seat = variant === 'seat'
  return (
    <div
      className={`role-card ${isLeft ? 'left' : 'right'}${seat ? ' role-card--seat' : ''}`}
      style={{ ['--accent' as string]: accent }}
    >
      <div className="avatar-wrap">
        <img className="avatar-img" src={avatarSrc} alt={name} />
      </div>
      <div className="info">
        <h3 className="name">{name}</h3>
        <p className="school">{school}</p>
      </div>
    </div>
  )
}
