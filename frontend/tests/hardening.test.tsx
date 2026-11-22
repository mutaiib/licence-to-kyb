// Findings of an independent frontend review: each test drives the app like a reviewer and
// checks what the page shows or what the server receives. Strings come from copy.ts.
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { FormFieldView, RunView, SpanView } from '../src/api/client';
import { App } from '../src/App';
import { ErrorBoundary } from '../src/components/ErrorBoundary';
import { copy, format } from '../src/copy';
import { errorText, fieldLabel } from '../src/text';

// ─── A fake server. `route` answers each request; it may return a promise to delay. ───────────
interface Sent {
  method: string;
  path: string;
  body: unknown;
}
interface Reply {
  status: number;
  body: unknown;
}
let sent: Sent[] = [];
let route: (request: Sent) => Reply | Promise<Reply>;

function serve() {
  sent = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = new URL(input instanceof Request ? input.url : input, 'http://localhost');
      const body = typeof init.body === 'string' ? (JSON.parse(init.body) as unknown) : null;
      const request = { method: (init.method ?? 'GET').toUpperCase(), path: url.pathname, body };
      sent.push(request);
      const reply = await route(request);
      return new Response(reply.status === 204 ? null : JSON.stringify(reply.body), {
        status: reply.status,
      });
    }),
  );
}

function openAt(path: string) {
  serve();
  window.history.pushState({}, '', path);
  render(<App />);
}

const ok = (body: unknown): Reply => ({ status: 200, body });

const flagged = (value: string): FormFieldView => ({
  value,
  state: 'flagged',
  status: 'present',
  origin: 'read',
  evidence_quote: value,
  rule_results: [
    {
      rule_id: 'evidence',
      severity: 'warn',
      outcome: 'failed',
      reason_code: 'evidence_mismatch',
      overridable: false,
      detail: {},
    },
  ],
});

function runView(fields: Record<string, FormFieldView>, overrides: Partial<RunView> = {}): RunView {
  return {
    run_id: 'run-1',
    applicant_name: 'Fuller Services LLC',
    created_at: '2026-11-22T08:00:00.000Z',
    status: 'awaiting_review',
    route: 'needs_review',
    reasons: [],
    required_documents: [],
    pages: 0,
    form_approved: false,
    steps: [],
    form: { version: 1, fields },
    ...overrides,
  };
}

/** The run after one more decision: the field is approved and the version goes up. */
function approved(view: RunView, name: string): RunView {
  const form = view.form;
  if (form === null) return view;
  const field = form.fields[name];
  if (field === undefined) return view;
  return {
    ...view,
    form: {
      version: form.version + 1,
      fields: { ...form.fields, [name]: { ...field, state: 'approved' } },
    },
  };
}

const button = (name: string) => screen.findByRole('button', { name });
const approveButton = (field: string) =>
  button(format('review.approve.field', { field: fieldLabel(field) }));

beforeEach(() => {
  document.cookie = 'csrf=token-123';
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, '', '/');
});

describe('sign out', () => {
  it('stays signed in and shows the reason when the server refuses the sign-out', async () => {
    route = (r) =>
      r.method === 'DELETE' ? { status: 403, body: { code: 'forbidden' } } : ok({ runs: [] });
    openAt('/');

    fireEvent.click(await button(copy['signout.button']));

    expect(await screen.findByText(errorText('forbidden'))).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: copy['signin.title'] })).toBeNull();
  });
});

describe('review actions', () => {
  it('sends the newest form version when two fields are approved quickly', async () => {
    let current = runView({
      licence_number: flagged('1234567'),
      expiry_date: flagged('2026-06-11'),
    });
    let release: () => void = () => undefined;
    route = (r) => {
      if (r.method === 'GET' && r.path === '/api/runs/run-1') return ok(current);
      if (r.method === 'GET') return ok({ runs: [] });
      const decision = (r.body as { decisions: { field: string }[] }).decisions[0];
      return new Promise((resolve) => {
        release = () => {
          if (decision !== undefined) current = approved(current, decision.field);
          resolve(ok(current));
        };
      });
    };
    openAt('/runs/run-1');

    fireEvent.click(await approveButton('licence_number'));
    fireEvent.click(await approveButton('expiry_date'));
    await act(async () => {
      release();
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(sent.filter((r) => r.method === 'POST')).toHaveLength(2);
    });
    await act(async () => {
      release();
      await Promise.resolve();
    });

    const versions = sent
      .filter((r) => r.method === 'POST')
      .map((r) => (r.body as { form_version: number }).form_version);
    expect(versions).toEqual([1, 2]);
  });

  it('keeps the typed value when the server refuses a correction', async () => {
    const view = runView({ licence_number: flagged('1234567') });
    route = (r) => {
      if (r.method === 'GET' && r.path === '/api/runs/run-1') return ok(view);
      if (r.method === 'GET') return ok({ runs: [] });
      return { status: 409, body: { code: 'blocking_rule_failed', field: 'licence_number' } };
    };
    openAt('/runs/run-1');

    fireEvent.click(
      await button(format('review.correct.field', { field: fieldLabel('licence_number') })),
    );
    fireEvent.change(screen.getByLabelText(copy['review.correct.label']), {
      target: { value: '7654321' },
    });
    fireEvent.click(screen.getByRole('button', { name: copy['review.save'] }));

    expect(await screen.findByText(errorText('blocking_rule_failed'))).toBeInTheDocument();
    expect(screen.getByLabelText(copy['review.correct.label'])).toHaveValue('7654321');
  });

  it('moves focus to the next flagged field, then to Approve form', async () => {
    let current = runView({
      licence_number: flagged('1234567'),
      expiry_date: flagged('2026-06-11'),
    });
    route = (r) => {
      if (r.method === 'GET' && r.path === '/api/runs/run-1') return ok(current);
      if (r.method === 'GET') return ok({ runs: [] });
      const decision = (r.body as { decisions: { field: string }[] }).decisions[0];
      if (decision !== undefined) current = approved(current, decision.field);
      return ok(current);
    };
    openAt('/runs/run-1');

    fireEvent.click(await approveButton('licence_number'));
    await waitFor(() => {
      expect(
        screen.getByRole('button', {
          name: format('review.approve.field', { field: fieldLabel('expiry_date') }),
        }),
      ).toHaveFocus();
    });

    fireEvent.click(await approveButton('expiry_date'));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: copy['review.approveForm'] })).toHaveFocus();
    });
  });

  it('names the field on each Override button', async () => {
    const field: FormFieldView = {
      ...flagged('1234567'),
      rule_results: [
        {
          rule_id: 'registry',
          severity: 'block',
          outcome: 'could_not_run',
          reason_code: 'registry_unavailable',
          overridable: true,
          detail: {},
        },
      ],
    };
    route = (r) =>
      r.path === '/api/runs/run-1' ? ok(runView({ licence_number: field })) : ok({ runs: [] });
    openAt('/runs/run-1');

    expect(
      await button(format('review.override.field', { field: fieldLabel('licence_number') })),
    ).toBeInTheDocument();
  });
});

describe('long input', () => {
  it('keeps a business name within the 200 characters the server accepts', async () => {
    route = () => ok({ runs: [] });
    openAt('/');

    const input = await screen.findByLabelText(copy['upload.applicantName.label']);
    fireEvent.change(input, { target: { value: 'A'.repeat(250) } });

    expect((input as HTMLInputElement).value).toHaveLength(200);
  });
});

describe('unexpected data', () => {
  it('shows the page for a field state and a reason code it does not know', async () => {
    const odd = { ...flagged('1234567'), state: 'new_state' } as unknown as FormFieldView;
    const view = runView(
      { licence_number: odd },
      {
        reasons: [
          { code: 'new_reason', field: null, rule_id: null, detail: {} },
        ] as unknown as RunView['reasons'],
      },
    );
    route = (r) => (r.path === '/api/runs/run-1' ? ok(view) : ok({ runs: [] }));
    openAt('/runs/run-1');

    expect(await screen.findByRole('heading', { name: 'Fuller Services LLC' })).toBeInTheDocument();
  });

  it('shows the upload page for a malformed address', async () => {
    route = () => ok({ runs: [] });
    openAt('/runs/%E0%A4%A');

    expect(await screen.findByLabelText(copy['upload.applicantName.label'])).toBeInTheDocument();
  });

  it('shows a message instead of a blank page when a part of the page fails', () => {
    function Broken(): never {
      throw new Error('broken');
    }
    vi.spyOn(console, 'error').mockImplementation(() => undefined);

    render(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>,
    );

    expect(screen.getByText(copy['app.crashed'])).toBeInTheDocument();
  });
});

describe('runs and trace', () => {
  it('shows the connection error, not "no runs", when the list fails to load', async () => {
    let calls = 0;
    route = (r) => {
      if (r.path !== '/api/runs') return { status: 404, body: { code: 'not_found' } };
      calls += 1;
      return calls === 1 ? ok({ runs: [] }) : { status: 500, body: { code: 'network' } };
    };
    openAt('/runs');

    expect(await screen.findByText(errorText('network'))).toBeInTheDocument();
    expect(screen.queryByText(copy['runs.empty'])).toBeNull();
  });

  it('names the business in each Trace link', async () => {
    const run = {
      run_id: 'run-1',
      applicant_name: 'Fuller Services LLC',
      created_at: '2026-11-22T08:00:00.000Z',
      status: 'done',
      route: 'ready',
      cost_usd: 0,
      duration_ms: 1000,
    };
    route = (r) =>
      r.path === '/api/runs'
        ? ok({ runs: [run] })
        : ok({
            runs: 1,
            refusal_rate: 0,
            fallback_rate: 0,
            review_rate: 0,
            cost_usd: 0,
            budget_tokens_remaining: 10,
          });
    openAt('/runs');

    expect(
      await screen.findByRole('link', {
        name: format('runs.trace.linkFor', { name: 'Fuller Services LLC' }),
      }),
    ).toBeInTheDocument();
  });

  it('shows a tool error as a sentence, not as a code', async () => {
    const span: SpanView = {
      span_id: 's1',
      parent_id: null,
      kind: 'tool_call',
      name: 'licence_lookup_registry',
      latency_ms: 20,
      input_tokens: 0,
      output_tokens: 0,
      cache_read_tokens: 0,
      cost_usd: 0,
      model: null,
      summary: 'registry_unavailable',
    };
    route = (r) =>
      r.path === '/api/runs/run-1/trace'
        ? ok({ run_id: 'run-1', applicant_name: 'Fuller Services LLC', spans: [span] })
        : r.path === '/api/runs/run-1'
          ? ok(runView({}))
          : ok({ runs: [] });
    openAt('/runs/run-1/trace');

    expect(await screen.findByText(copy['span.registry_unavailable'])).toBeInTheDocument();
    expect(screen.queryByText('registry_unavailable')).toBeNull();
  });
});
