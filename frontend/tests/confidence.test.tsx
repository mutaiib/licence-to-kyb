// Confidence on the review page (US3, T071): a flagged field shows its score, the score it
// needs, and in words the evidence behind a low score.
import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { FormFieldView } from '../src/api/client';
import { ConfidenceDetails } from '../src/components/ConfidenceDetails';
import { copy } from '../src/copy';

const lowScore: NonNullable<FormFieldView['confidence']> = {
  score: 0.81,
  threshold: 0.9,
  signals: { agreement: 0, grounding: 1, rules: 1, ocr: 0.97 },
};

describe('confidence details', () => {
  it('shows the score and the score the field needs', () => {
    render(<ConfidenceDetails confidence={lowScore} />);

    expect(screen.getByText('0.81')).toBeInTheDocument();
    expect(screen.getByText('0.90')).toBeInTheDocument();
  });

  it('names the weak evidence behind a low score and only that', () => {
    render(<ConfidenceDetails confidence={lowScore} />);

    const reasons = screen.getByRole('list', { name: copy['confidence.weak.title'] });
    expect(within(reasons).getByText(copy['signal.agreement'])).toBeInTheDocument();
    expect(within(reasons).queryByText(copy['signal.grounding'])).toBeNull();
    expect(within(reasons).queryByText(copy['signal.ocr'])).toBeNull();
  });

  it('shows no weak evidence when every signal is strong', () => {
    render(
      <ConfidenceDetails confidence={{ score: 0.99, threshold: 0.9, signals: { agreement: 1 } }} />,
    );

    expect(screen.queryByRole('list', { name: copy['confidence.weak.title'] })).toBeNull();
  });

  it('shows the score alone for a field with no threshold', () => {
    render(<ConfidenceDetails confidence={{ score: 0.95, threshold: null, signals: {} }} />);

    expect(screen.getByText('0.95')).toBeInTheDocument();
    expect(screen.queryByText(copy['review.threshold.label'])).toBeNull();
  });
});
