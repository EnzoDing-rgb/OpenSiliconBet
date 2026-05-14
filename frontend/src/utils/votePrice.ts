/**
 * Demo-only: map vote counts -> three "display index" numbers (not real quotes).
 * Formula: base 100 each; multiplicative bump from share vs 1/3 (softmax-ish), bounded ~±4% per axis at typical skew.
 */
export type CampVotes = { riscv: number; x86: number; arm: number }

const BASE = { riscv: 100, x86: 100, arm: 100 } as const
const ALPHA = 0.15

export function displayPricesFromVotes(v: CampVotes): CampVotes {
  const tr = v.riscv + 1
  const tx = v.x86 + 1
  const ta = v.arm + 1
  const sum = tr + tx + ta
  const sr = tr / sum
  const sx = tx / sum
  const sa = ta / sum
  const third = 1 / 3
  return {
    riscv: BASE.riscv * (1 + ALPHA * (sr - third)),
    x86: BASE.x86 * (1 + ALPHA * (sx - third)),
    arm: BASE.arm * (1 + ALPHA * (sa - third)),
  }
}
