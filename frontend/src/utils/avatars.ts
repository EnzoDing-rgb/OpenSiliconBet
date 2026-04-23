import type { Speaker } from '../types'
import jervisImg from '../assets/jervis.png'
import mearsheimerImg from '../assets/mearsheimer.png'

export const speakerMeta: Record<
  Speaker,
  { nameZh: string; subtitleZh: string; avatarSrc: string; accent: string }
> = {
  jervis: {
    nameZh: '滴滴Researcher',
    subtitleZh: '平台治理与数据安全 · 案例研究者',
    avatarSrc: jervisImg,
    accent: '#3b82f6',
  },
  mearsheimer: {
    nameZh: 'ManusResearcher',
    subtitleZh: '技术主权与跨境合规 · 案例研究者',
    avatarSrc: mearsheimerImg,
    accent: '#ef4444',
  },
}

export function getAvatarSrc(speaker: Speaker): string {
  return speakerMeta[speaker].avatarSrc
}
