// When the server is down or answers with something that is not data, the page says so and
// recovers; it never crashes and never asks a signed-in reviewer to sign in again.
// Strings come from copy.ts, never literals.
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { getRun, REQUEST_TIMEOUT_MS, type RunView } from '../src/api/client';
import { App } from '../src/App';
import { copy } from '../src/copy';

type Reply = { status: number; body: string } | 'down';
let reply: (path: string) => Reply;

function serve() {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      const path = new URL(input instanceof Request ? input.url : input, 'http://localhost')
        .pathname;
      const r = reply(path);
      if (r === 'down') return Promise.reject(new TypeError('Failed to fetch'));
      return Promise.resolve(new Response(r.body, { status: r.status }));
    }),
  );
}

const json = (body: unknown) => ({ status: 200, body: JSON.stringify(body) });
const html = { status: 200, body: '<!doctype html><html><body></body></html>' };

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

describe('a server that is down or answers with a web page', () => {
  it('shows the connection error, not a crash, when a reply is not data', async () => {
    reply = () => html;
    openAt('/runs');

    expect(await screen.findByText(copy['error.network'])).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: copy['signin.title'] })).toBeNull();
  });

  it('shows the connection error, not the sign-in page, and recovers on Try again', async () => {
    reply = () => 'down';
    openAt('/runs');

    expect(await screen.findByText(copy['error.network'])).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: copy['signin.title'] })).toBeNull();

    reply = (path) =>
      path === '/api/metrics/summary'
        ? json({
            runs: 0,
            refusal_rate: 0,
            fallback_rate: 0,
            review_rate: 0,
            cost_usd: 0,
            budget_tokens_remaining: 10,
          })
        : json({ runs: [] });
    fireEvent.click(screen.getByRole('button', { name: copy['app.tryAgain'] }));

    expect(await screen.findByRole('heading', { name: copy['runs.title'] })).toBeInTheDocument();
  });
});

describe('the review page while a run processes', () => {
  const view: RunView = {
    run_id: 'run-1',
    applicant_name: 'Fuller Services LLC',
    created_at: '2026-11-22T08:00:00.000Z',
    status: 'processing',
    route: null,
    reasons: [],
    required_documents: [],
    pages: 0,
    form_approved: false,
    steps: [],
    form: null,
  };

  it('keeps checking after one failed request', async () => {
    let runRequests = 0;
    reply = (path) => {
      if (path === '/api/runs') return json({ runs: [] });
      runRequests += 1;
      if (runRequests === 1) return json(view); // the page opens: processing
      if (runRequests === 2) return 'down'; // one failed check
      return json({ ...view, status: 'rejected', route: 'reject' });
    };
    openAt('/runs/run-1');

    expect(
      await screen.findByText(copy['route.reject.detail'], {}, { timeout: 5000 }),
    ).toBeInTheDocument();
  });
});

describe('a request that never gets a reply', () => {
  it('ends with the connection error after the time limit, so later actions can run', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_input: RequestInfo | URL, init: RequestInit = {}) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener('abort', () => {
              reject(new DOMException('aborted', 'AbortError'));
            });
          }),
      ),
    );

    const pending = getRun('run-1');
    await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS + 1);

    expect(await pending).toEqual({ ok: false, code: 'network' });
    vi.useRealTimers();
  });
});
