// Runs, daily summary and trace pages (US5). Strings come from copy.ts, never literals.
import { render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from '../src/App';
import { copy, format } from '../src/copy';
import { stepLabel } from '../src/text';

const SPANS = [
  {
    span_id: 's1',
    parent_id: null,
    kind: 'step',
    name: 'extract',
    latency_ms: 2400,
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
    latency_ms: 1800,
    input_tokens: 1200,
    output_tokens: 300,
    cache_read_tokens: 800,
    cost_usd: 0.0123,
    model: 'claude-opus-5-5',
    summary: 'ok',
  },
  {
    span_id: 's2',
    parent_id: null,
    kind: 'step',
    name: 'resolve',
    latency_ms: 900,
    input_tokens: 0,
    output_tokens: 0,
    cache_read_tokens: 0,
    cost_usd: 0,
    model: null,
    summary: 'ok',
  },
  {
    span_id: 't1',
    parent_id: 's2',
    kind: 'tool_call',
    name: 'licence_lookup_registry',
    latency_ms: 40,
    input_tokens: 0,
    output_tokens: 0,
    cache_read_tokens: 0,
    cost_usd: 0,
    model: null,
    summary: 'registry_unavailable',
  },
];

const SUMMARY = {
  runs: 4,
  refusal_rate: 0.25,
  fallback_rate: 0,
  review_rate: 0.5,
  cost_usd: 1.234,
  budget_tokens_remaining: 950000,
};

const RUNS = [
  {
    run_id: 'run-1',
    created_at: '2026-11-22T08:00:00Z',
    applicant_name: 'Fuller Services LLC',
    route: 'needs_review',
    status: 'awaiting_review',
    cost_usd: 0.31,
    duration_ms: 41000,
  },
];

function serve() {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      const path = new URL(input instanceof Request ? input.url : input, 'http://localhost')
        .pathname;
      const body =
        path === '/api/runs'
          ? { runs: RUNS }
          : path === '/api/metrics/summary'
            ? SUMMARY
            : path === '/api/runs/run-1/trace'
              ? { spans: SPANS }
              : null;
      return Promise.resolve(
        new Response(JSON.stringify(body ?? { code: 'not_found' }), {
          status: body ? 200 : 404,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    }),
  );
}

function openAt(path: string) {
  serve();
  window.history.pushState({}, '', path);
  render(<App />);
}

beforeEach(() => {
  document.cookie = 'csrf=token-123';
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, '', '/');
});

describe('runs page', () => {
  it('shows each daily rate with its label', async () => {
    openAt('/runs');

    const summary = await screen.findByRole('region', { name: copy['runs.summary.title'] });
    expect(within(summary).getByText(copy['runs.summary.refusals'])).toBeInTheDocument();
    expect(within(summary).getByText('25%')).toBeInTheDocument();
    expect(within(summary).getByText(copy['runs.summary.review'])).toBeInTheDocument();
    expect(within(summary).getByText('50%')).toBeInTheDocument();
    expect(within(summary).getByText(copy['runs.summary.budget'])).toBeInTheDocument();
  });

  it('links each run to its form and to its trace', async () => {
    openAt('/runs');

    const name = await screen.findByRole('link', { name: 'Fuller Services LLC' });
    expect(name).toHaveAttribute('href', '/runs/run-1');
    expect(screen.getByRole('link', { name: copy['runs.trace.link'] })).toHaveAttribute(
      'href',
      '/runs/run-1/trace',
    );
  });
});

describe('trace page', () => {
  it('nests each call under its step', async () => {
    openAt('/runs/run-1/trace');

    const extract = await screen.findByRole('listitem', { name: stepLabel('extract') });
    expect(within(extract).getByText('extract_primary')).toBeInTheDocument();
    const resolve = screen.getByRole('listitem', { name: stepLabel('resolve') });
    expect(within(resolve).getByText('licence_lookup_registry')).toBeInTheDocument();
    expect(within(extract).queryByText('licence_lookup_registry')).toBeNull();
  });

  it('shows the tokens, the cost and the outcome of a call', async () => {
    openAt('/runs/run-1/trace');

    expect(
      await screen.findByText(format('trace.tokens.value', { input: '1200', output: '300' })),
    ).toBeInTheDocument();
    expect(screen.getByText('$0.0123')).toBeInTheDocument();
    expect(screen.getByText('registry_unavailable')).toBeInTheDocument();
    expect(screen.getByText(copy['trace.masked'])).toBeInTheDocument();
  });
});
