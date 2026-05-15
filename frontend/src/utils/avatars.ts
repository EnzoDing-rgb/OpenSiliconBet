import type { Speaker } from '../types'
import lexFace from '../assets/faces/lex.png'
import wuweiFace from '../assets/faces/wuwei.png'
import liptanFace from '../assets/faces/liptan.png'
import cookFace from '../assets/faces/cook.png'
import jensenFace from '../assets/faces/jensen.png'

export type SpeakerMeta = {
  nameZh: string
  subtitleZh: string
  avatarSrc: string
  accent: string
}

/** 头像来自项目方提供的肖像素材（`src/assets/faces/`），仅用于本 demo UI。 */
export const speakerMeta: Record<Speaker, SpeakerMeta> = {
  lex: {
    nameZh: 'Lex Fridman',
    subtitleZh: 'Lex Fridman from MIT',
    avatarSrc: lexFace,
    accent: '#64748b',
  },
  wuwei: {
    nameZh: '神秘 RISC-V 专家',
    subtitleZh: 'RISC-V 阵营',
    avatarSrc: wuweiFace,
    accent: '#22c55e',
  },
  liptan: {
    nameZh: '陈立武',
    subtitleZh: 'x86 · Intel',
    avatarSrc: liptanFace,
    accent: '#3b82f6',
  },
  cook: {
    nameZh: '蒂姆·库克',
    subtitleZh: 'ARM · Apple',
    avatarSrc: cookFace,
    accent: '#a855f7',
  },
  jensen: {
    nameZh: '黄仁勋',
    subtitleZh: 'NVIDIA',
    avatarSrc: jensenFace,
    accent: '#eab308',
  },
}

export function getAvatarSrc(speaker: Speaker): string {
  return speakerMeta[speaker].avatarSrc
}

export function speakerLabelZh(s: Speaker): string {
  return speakerMeta[s].nameZh
}
