import { VStack } from '@astryxdesign/core/VStack';
import type { CSSProperties } from 'react';

import { pageImageUrl, type EvidenceBox } from '../api/client';
import { format } from '../copy';

// The page image fills the pane; the frame is the positioning context for the highlight.
// Stack has no position prop, so these two inline styles set it. Colours and widths are tokens.
const frameStyle: CSSProperties = { position: 'relative' };
/** Keeps the outline clear of the glyphs it frames. */
const OUTSET = 'var(--spacing-1)';

const imageStyle: CSSProperties = { display: 'block', width: '100%', height: 'auto' };
const highlightBase: CSSProperties = {
  position: 'absolute',
  pointerEvents: 'none',
  border: 'calc(var(--border-width) * 2) solid var(--color-accent)',
  borderRadius: 'var(--radius-inner)',
  boxShadow: 'var(--shadow-low)',
};

const percent = (fraction: number) => `${String(fraction * 100)}%`;

/**
 * One licence page with a box around the text that a field value came from.
 * `box` is in fractions of the page (0 to 1), as the API returns it.
 */
export function EvidenceViewer({
  runId,
  page,
  box,
}: {
  runId: string;
  page: number;
  box: EvidenceBox | null;
}) {
  return (
    <VStack style={frameStyle}>
      <img
        src={pageImageUrl(runId, page)}
        alt={format('review.page.label', { page: String(page) })}
        style={imageStyle}
      />
      {box !== null && box.page === page && (
        <VStack
          aria-hidden="true"
          data-testid="evidence-highlight"
          style={{
            ...highlightBase,
            left: `calc(${percent(box.x)} - ${OUTSET})`,
            top: `calc(${percent(box.y)} - ${OUTSET})`,
            width: `calc(${percent(box.w)} + 2 * ${OUTSET})`,
            height: `calc(${percent(box.h)} + 2 * ${OUTSET})`,
          }}
        />
      )}
    </VStack>
  );
}
