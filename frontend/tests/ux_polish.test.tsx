// UI and UX polish (specs/001-licence-to-kyb/ux-review.md, T112–T118) and the automatic
// accessibility check (T098). Strings come from copy.ts, never literals.
import { render, screen, waitFor, within } from '@testing-library/react';
import axe from 'axe-core';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { FormFieldView, RunView } from '../src/api/client';
import { App } from '../src/App';
import { copy, format } from '../src/copy';
import { fieldLabel } from '../src/text';

const passed = (value: string): FormFieldView => ({
  value,
  state: 'passed',
  status: 'present',
  origin: 'read',
  evidence_quote: value,
  rule_results: [],
});

const flagged: FormFieldView = {
  value: '2026-06-11',
  state: 'flagged',
  status: 'present',
  origin: 'read',
  evidence_quote: 'Expiry Date 11/06/2026',
  rule_results: [
    {
      rule_id: 'expiry',
      severity: 'warn',
      outcome: 'failed',
      reason_code: 'near_expiry',
      overridable: false,
      detail: { days: '10' },
    },
  ],
};

const VIEW: RunView = {
  run_id: 'run-1',
  applicant_name: 'Fuller Services LLC',
  created_at: '2026-11-22T08:00:00.000Z',
  status: 'awaiting_review',
  route: 'needs_review',
  reasons: [
    { code: 'near_expiry', field: 'expiry_date', rule_id: 'expiry', detail: { days: '10' } },
    { code: 'fallback_model', field: null, rule_id: null, detail: {} },
  ],
  required_documents: [],
  pages: 1,
  steps: [],
  form: {
    version: 1,
    fields: {
      legal_name_en: passed('Fuller Services LLC'),
      licence_number: passed('7828167'),
      expiry_date: flagged,
    },
  },
};

const SPANS = [
  {
    span_id: 's1',
    parent_id: null,
    kind: 'step',
    name: 'extract',
    latency_ms: 2000,
    input_tokens: 0,
    output_tokens: 0,
    cache_read_tokens: 0,
    cost_usd: 0,
    model: null,
    summary: 'ok',
  },
  {
    span_id: 'c1',
    parent_id: 's1',
    kind: 'model_call',
    name: 'extract_primary',
    latency_ms: 1500,
    input_tokens: 100,
    output_tokens: 50,
    cache_read_tokens: 0,
    cost_usd: 0.25,
    model: 'claude-opus-5-5',
    summary: 'ok',
  },
  {
    span_id: 's2',
    parent_id: null,
    kind: 'step',
    name: 'validate',
    latency_ms: 500,
    input_tokens: 0,
    output_tokens: 0,
    cache_read_tokens: 0,
    cost_usd: 0,
    model: null,
    summary: 'ok',
  },
];

let runs: unknown[] = [];

function serve() {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      const path = new URL(input instanceof Request ? input.url : input, 'http://localhost')
        .pathname;
      const body =
        path === '/api/runs'
          ? { runs }
          : path === '/api/metrics/summary'
            ? {
                runs: 0,
                refusal_rate: 0,
                fallback_rate: 0,
                review_rate: 0,
                cost_usd: 0,
                budget_tokens_remaining: 10,
              }
            : path === '/api/runs/run-1'
              ? VIEW
              : path === '/api/runs/run-1/trace'
                ? { spans: SPANS }
                : null;
      return Promise.resolve(
        new Response(body === null ? null : JSON.stringify(body), {
          status: body === null ? 404 : 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    }),
  );
}

/** A phone-width screen: every max-width media query matches. */
function narrowScreen() {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: query.includes('max-width'),
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    onchange: null,
    dispatchEvent: () => false,
  }));
}

function openAt(path: string) {
  serve();
  window.history.pushState({}, '', path);
  return render(<App />);
}

/** True when `a` comes before `b` in the document. */
const before = (a: Element, b: Element) =>
  Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

beforeEach(() => {
  document.cookie = 'csrf=token-123';
  runs = [];
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, '', '/');
});

describe('review page', () => {
  it('puts the form actions before the fields (T112)', async () => {
    openAt('/runs/run-1');

    const approveForm = await screen.findByRole('button', { name: copy['review.approveForm'] });
    const firstField = screen.getByRole('button', {
      name: new RegExp(`^${fieldLabel('expiry_date')}`),
    });
    expect(before(approveForm, firstField)).toBe(true);
  });

  it('lists the flagged fields first and keeps passed fields closed (T113)', async () => {
    openAt('/runs/run-1');

    const toExamine = await screen.findByRole('region', {
      name: format('review.toExamine', { count: '1' }),
    });
    expect(
      within(toExamine).getByRole('button', { name: new RegExp(`^${fieldLabel('expiry_date')}`) }),
    ).toBeInTheDocument();
    const passedGroup = screen.getByRole('button', {
      name: new RegExp(format('review.passedFields', { count: '2' })),
    });
    expect(passedGroup).toHaveAttribute('aria-expanded', 'false');
  });

  it('names the business, links to the trace, and shows only run-level reasons (T114)', async () => {
    openAt('/runs/run-1');

    expect(await screen.findByRole('heading', { name: 'Fuller Services LLC' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: copy['review.trace.link'] })).toHaveAttribute(
      'href',
      '/runs/run-1/trace',
    );
    const reasons = screen.getByRole('list', { name: copy['review.reasons.title'] });
    expect(within(reasons).getAllByRole('listitem')).toHaveLength(1); // fallback_model only
  });

  it('shows the licence page right after the fields to examine on a phone (T118)', async () => {
    narrowScreen();
    openAt('/runs/run-1');

    const toExamine = await screen.findByRole('region', {
      name: format('review.toExamine', { count: '1' }),
    });
    const page = screen.getByRole('img', { name: format('review.page.label', { page: '1' }) });
    const passedGroup = screen.getByRole('button', {
      name: new RegExp(format('review.passedFields', { count: '2' })),
    });
    expect(before(toExamine, page)).toBe(true);
    expect(before(page, passedGroup)).toBe(true);
  });
});

describe('runs page', () => {
  it('has one status column and no separate route column (T115)', async () => {
    runs = [
      {
        run_id: 'run-1',
        created_at: VIEW.created_at,
        applicant_name: 'Fuller Services LLC',
        route: 'needs_review',
        status: 'awaiting_review',
        cost_usd: 0,
        duration_ms: 1000,
      },
    ];
    openAt('/runs');

    await screen.findByRole('table');
    expect(
      screen.getByRole('columnheader', { name: copy['runs.column.status'] }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: copy['runs.column.route'] })).toBeNull();
  });

  it('shows a list, not a table, on a phone (T115)', async () => {
    runs = [
      {
        run_id: 'run-1',
        created_at: VIEW.created_at,
        applicant_name: 'Fuller Services LLC',
        route: 'needs_review',
        status: 'awaiting_review',
        cost_usd: 0,
        duration_ms: 1000,
      },
    ];
    narrowScreen();
    openAt('/runs');

    expect(await screen.findByRole('link', { name: /Fuller Services LLC/ })).toBeInTheDocument();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('links an empty list to the upload page (T115)', async () => {
    openAt('/runs');

    expect(await screen.findByRole('link', { name: copy['nav.upload'] })).toHaveAttribute(
      'href',
      '/',
    );
  });
});

describe('trace page', () => {
  it('names the business and shows the totals (T116)', async () => {
    openAt('/runs/run-1/trace');

    expect(await screen.findByRole('heading', { name: 'Fuller Services LLC' })).toBeInTheDocument();
    expect(
      await screen.findByText(
        format('trace.totals', { seconds: '2.5', cost: '0.2500', calls: '1' }),
      ),
    ).toBeInTheDocument();
  });
});

describe('upload page', () => {
  it('says what happens after upload and how to fill the business name (T117)', async () => {
    openAt('/');

    expect(await screen.findByText(copy['upload.intro'])).toBeInTheDocument();
    expect(screen.getByText(copy['upload.applicantName.help'])).toBeInTheDocument();
  });
});

describe('accessibility (T098)', () => {
  it.each(['/', '/runs', '/runs/run-1', '/runs/run-1/trace'])(
    'finds no WCAG 2.2 AA problem on %s',
    async (path) => {
      const { container } = openAt(path);
      await waitFor(() => {
        expect(container.querySelector('h1')).not.toBeNull();
      });

      const result = await axe.run(container, {
        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] },
        rules: { 'color-contrast': { enabled: false } }, // jsdom has no layout; checked in the browser
      });

      expect(result.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
    },
  );
});
