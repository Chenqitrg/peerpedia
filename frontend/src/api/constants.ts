/** Shared score dimension definitions — single source of truth. */
export const SCORE_DIMS = [
  { key: 'originality', label: 'O', fullLabel: 'Originality' },
  { key: 'rigor', label: 'R', fullLabel: 'Rigor' },
  { key: 'completeness', label: 'C', fullLabel: 'Completeness' },
  { key: 'pedagogy', label: 'P', fullLabel: 'Pedagogy' },
  { key: 'impact', label: 'I', fullLabel: 'Impact' },
] as const

export type ScoreDimKey = (typeof SCORE_DIMS)[number]['key']
