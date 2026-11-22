// Review actions (User Story 2). The tests drive the page like a reviewer and check what the
// server receives and what the page shows. Strings come from copy.ts, never literals.
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { FormFieldView, RunView } from '../src/api/client';
import { App } from '../src/App';
import { copy, format } from '../src/copy';
import { errorText, fieldLabel } from '../src/text';

// ─── A fake server: GET returns the current run view; actions return the next one. ─────────────

interface Sent {
  method: string;
  path: string;
  body: unknown;
}

let sent: Sent[] = [];
let current: RunView;
type Answer = { status: number; body: unknown } | RunView;
let answer: (request: Sent) => Answer = () => current;

function serve(view: RunView) {
  current = view;
  sent = [];
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = new URL(input instanceof Request ? input.url : input, 'http://localhost');
      const body = typeof init.body === 'string' ? (JSON.parse(init.body) as unknown) : null;
      const request = { method: (init.method ?? 'GET').toUpperCase(), path: url.pathname, body };
      sent.push(request);
      let reply: { status: number; body: unknown };
      if (request.method === 'GET' && request.path === '/api/runs') {
        reply = { status: 200, body: { runs: [] } };
      } else if (request.method === 'GET' && request.path === `/api/runs/${current.run_id}`) {
        reply = { status: 200, body: current };
      } else {
        const next = answer(request);
        if ('run_id' in next) {
          current = next;
          reply = { status: 200, body: next };
        } else {
          reply = next;
        }
      }
      return Promise.resolve(
        new Response(JSON.stringify(reply.body), {
          status: reply.status,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    }),
  );
}

const actions = (path: string) =>
  sent.filter((r) => r.method === 'POST' && r.path.endsWith(`/${path}`));

beforeEach(() => {
  document.cookie = 'csrf=token-123';
  answer = () => current;
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, '', '/');
});

function openRun(view: RunView) {
  serve(view);
  window.history.pushState({}, '', `/runs/${view.run_id}`);
  render(<App />);
}

// ─── Fixtures ───────────────────────────────────────────────────────────────────────────────────

const passed: FormFieldView = {
  value: '1234567',
  state: 'passed',
  origin: 'read',
  status: 'present',
  evidence_quote: 'Licence No. 1234567',
  rule_results: [],
};

const nearExpiry: FormFieldView = {
  value: '2026-12-25',
  state: 'flagged',
  origin: 'read',
  status: 'present',
  evidence_quote: 'Expiry Date 25/12/2026',
  rule_results: [
    {
      rule_id: 'expiry',
      severity: 'warn',
      outcome: 'failed',
      reason_code: 'near_expiry',
      overridable: false,
      detail: { days: '20' },
    },
  ],
};

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

const withField = (view: RunView, name: string, field: Partial<FormFieldView>): RunView => {
  if (view.form === null) return view;
  const fields = { ...view.form.fields };
  fields[name] = { ...fields[name], ...field } as FormFieldView;
  return { ...view, form: { version: view.form.version + 1, fields } };
};

const button = (name: string) => screen.findByRole('button', { name });
const fieldAction = (
  key: 'review.approve.field' | 'review.correct.field' | 'review.enterValue.field',
  field: string,
) => button(format(key, { field: fieldLabel(field) }));

// ─── Tests ──────────────────────────────────────────────────────────────────────────────────────

describe('review actions', () => {
  it('offers retry processing only after a processing failure', async () => {
    const failed = runView(
      { licence_number: passed },
      { reasons: [{ code: 'processing_failed', field: null, rule_id: null, detail: {} }] },
    );
    answer = () => ({ status: 202, body: { run_id: 'run-1', status: 'processing' } });
    openRun(failed);

    fireEvent.click(await button(copy['review.retry']));

    await waitFor(() => {
      expect(actions('retry')).toHaveLength(1);
    });
  });

  it('offers no form approval or submit when there is no form to approve', async () => {
    openRun({
      ...runView({}),
      form: null,
      reasons: [{ code: 'processing_failed', field: null, rule_id: null, detail: {} }],
    });

    await button(copy['review.retry']);
    expect(screen.queryByRole('button', { name: copy['review.approveForm'] })).toBeNull();
    expect(screen.queryByRole('button', { name: copy['review.submit'] })).toBeNull();
    expect(screen.getByRole('button', { name: copy['review.reject'] })).toBeInTheDocument();
  });

  it('does not offer retry processing when processing did not fail', async () => {
    openRun(runView({ expiry_date: nearExpiry }));

    await fieldAction('review.approve.field', 'expiry_date');
    expect(screen.queryByRole('button', { name: copy['review.retry'] })).toBeNull();
  });

  it('enters a value for a field that is not on the licence and marks it as from the reviewer', async () => {
    const missing: FormFieldView = {
      ...passed,
      value: null,
      status: 'not_present',
      state: 'needs_examination',
      evidence_quote: null,
    };
    const view = runView({ chamber_number: missing });
    answer = () =>
      withField(view, 'chamber_number', {
        value: '98005',
        status: 'present',
        origin: 'entered_by_reviewer',
        state: 'corrected',
      });
    openRun(view);

    fireEvent.click(await fieldAction('review.enterValue.field', 'chamber_number'));
    fireEvent.change(screen.getByLabelText(copy['review.correct.label']), {
      target: { value: '98005' },
    });
    fireEvent.click(screen.getByRole('button', { name: copy['review.save'] }));

    await screen.findByText(copy['state.entered_by_reviewer']);
    const [review] = actions('review');
    expect(review?.body).toMatchObject({
      form_version: 1,
      decisions: [{ field: 'chamber_number', action: 'correct', value: '98005' }],
    });
  });

  it('offers approve form only after every flagged field has a decision', async () => {
    const view = runView({ licence_number: passed, expiry_date: nearExpiry });
    answer = () => withField(view, 'expiry_date', { state: 'approved' });
    openRun(view);

    expect(await screen.findByText(copy['next.examine.one'])).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: copy['review.approveForm'] })).toBeNull();

    fireEvent.click(await fieldAction('review.approve.field', 'expiry_date'));

    expect(await button(copy['review.approveForm'])).toBeEnabled();
    expect(screen.getByText(copy['review.allDecided'])).toBeInTheDocument();
  });

  it('offers an override for a failed check that its rule marks as overridable', async () => {
    const inferred: FormFieldView = {
      ...passed,
      state: 'flagged',
      rule_results: [
        {
          rule_id: 'number_format',
          severity: 'block',
          outcome: 'failed',
          reason_code: 'number_format',
          overridable: true,
          detail: { authority: 'DET' },
        },
      ],
    };
    openRun(runView({ licence_number: inferred }));

    expect(
      await button(format('review.override.field', { field: fieldLabel('licence_number') })),
    ).toBeInTheDocument();
  });

  it('asks for a reason before it overrides a check that could not run', async () => {
    const unchecked: FormFieldView = {
      ...passed,
      state: 'flagged',
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
    openRun(runView({ licence_number: unchecked }));

    fireEvent.click(
      await button(format('review.override.field', { field: fieldLabel('licence_number') })),
    );
    const save = screen.getByRole('button', { name: copy['review.save'] });
    expect(save).toHaveAttribute('aria-disabled', 'true');

    fireEvent.change(screen.getByLabelText(copy['review.override.reason.label']), {
      target: { value: 'Checked by phone' },
    });
    fireEvent.click(save);

    await waitFor(() => {
      expect(actions('review')[0]?.body).toMatchObject({
        decisions: [{ rule_id: 'registry', action: 'override', reason: 'Checked by phone' }],
      });
    });
  });

  it('asks for a form approval before submit on a ready run that nobody approved', async () => {
    openRun(runView({ licence_number: passed }, { status: 'awaiting_submit', route: 'ready' }));

    expect(await button(copy['review.approveForm'])).toBeEnabled();
    expect(screen.queryByRole('button', { name: copy['review.submit'] })).toBeNull();
    expect(screen.queryByText(copy['review.ready'])).toBeNull();
  });

  it('replaces submit with approve form after a change', async () => {
    const approved = runView(
      { licence_number: passed },
      { status: 'awaiting_submit', form_approved: true },
    );
    answer = () => ({
      ...withField(approved, 'licence_number', { value: '7654321', state: 'corrected' }),
      status: 'awaiting_review',
    });
    openRun(approved);

    expect(await button(copy['review.submit'])).toBeEnabled();

    fireEvent.click(await fieldAction('review.correct.field', 'licence_number'));
    fireEvent.change(screen.getByLabelText(copy['review.correct.label']), {
      target: { value: '7654321' },
    });
    fireEvent.click(screen.getByRole('button', { name: copy['review.save'] }));

    expect(await button(copy['review.approveForm'])).toBeEnabled();
    expect(screen.queryByRole('button', { name: copy['review.submit'] })).toBeNull();
  });

  it('moves focus to the next flagged field after a decision', async () => {
    const flaggedForm: FormFieldView = { ...nearExpiry, value: 'llc' };
    const view = runView({ expiry_date: nearExpiry, legal_form: flaggedForm });
    answer = () => withField(view, 'expiry_date', { state: 'approved' });
    openRun(view);

    fireEvent.click(await fieldAction('review.approve.field', 'expiry_date'));

    const next = await fieldAction('review.approve.field', 'legal_form');
    await waitFor(() => {
      expect(next).toHaveFocus();
    });
  });

  it.each([
    'blocking_rule_failed',
    'not_overridable',
    'undecided_fields',
    'stale_version',
    'reason_required',
  ])('shows the string for the refusal code %s', async (code) => {
    answer = () => ({ status: 409, body: { code, field: null, rule_id: null } });
    openRun(runView({ expiry_date: nearExpiry }));

    fireEvent.click(await fieldAction('review.approve.field', 'expiry_date'));

    expect(await screen.findByText(errorText(code))).toBeInTheDocument();
  });
});
