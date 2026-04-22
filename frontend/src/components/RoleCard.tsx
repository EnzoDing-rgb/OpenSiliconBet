import './RoleCard.css'

interface RoleCardProps {
  name: string
  school: string
  avatarSrc: string
  accent: string
  isLeft: boolean
}

export function RoleCard({ name, school, avatarSrc, accent, isLeft }: RoleCardProps) {
  return (
    <div className={`role-card ${isLeft ? 'left' : 'right'}`} style={{ ['--accent' as string]: accent }}>
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
