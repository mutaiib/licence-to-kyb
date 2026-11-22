/**
 * Every interface string in the app. Components read text from here only.
 *
 * The rules (ASD-STE100) and the full key list are in docs/ui-copy.md.
 * scripts/lint_copy.py checks each value in CI.
 */
export const copy = {
  app: {
    title: 'Trade licence to KYB',
  },
} as const;

export type Copy = typeof copy;
