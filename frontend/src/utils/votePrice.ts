export type CampVotes = { riscv: number; x86: number; arm: number }

export const CAMP_BASE = { riscv: 96, x86: 108, arm: 102 } as const
const CAMP_STEP = { riscv: 1.8, x86: 1.35, arm: 1.5 } as const

export function displayPricesFromVotes(v: CampVotes): CampVotes {
  return {
    riscv: CAMP_BASE.riscv + v.riscv * CAMP_STEP.riscv,
    x86: CAMP_BASE.x86 + v.x86 * CAMP_STEP.x86,
    arm: CAMP_BASE.arm + v.arm * CAMP_STEP.arm,
  }
}
