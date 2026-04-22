import type { Speaker } from '../types'
import jervisImg from '../assets/jervis.png'
import mearsheimerImg from '../assets/mearsheimer.png'

export const speakerMeta: Record<
  Speaker,
  { nameZh: string; subtitleZh: string; avatarSrc: string; accent: string }
> = {
  jervis: {
    nameZh: '罗伯特·杰维斯',
    subtitleZh: '认知学派 · 《知觉与错误知觉》作者',
    avatarSrc: jervisImg,
    accent: '#3b82f6',
  },
  mearsheimer: {
    nameZh: '约翰·米尔斯海默',
    subtitleZh: '进攻性现实主义 · 批判者',
    avatarSrc: mearsheimerImg,
    accent: '#ef4444',
  },
}

export function getAvatarSrc(speaker: Speaker): string {
  return speakerMeta[speaker].avatarSrc
}
