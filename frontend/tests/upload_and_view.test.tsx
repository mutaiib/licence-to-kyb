import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { RunView } from '../src/api/client';
import { App } from '../src/App';
import { copy, format, type CopyKey } from '../src/copy';
import { fieldValueText } from '../src/text';

// ─── A fake API: only `fetch` is replaced; every request is recorded. ───────────────────────────

interface Recorded {
  method: string;
  path: string;
  headers: Headers;
  body: BodyInit | null | undefined;
}

interface Reply {
  status: number;
  body?: unknown;
}
type Handler = (request: Recorded) => Reply | undefined;

let requests: Recorded[] = [];

function serve(handler: Handler) {
  requests = [];
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = new URL(input instanceof Request ? input.url : input, 'http://localhost');
      const request: Recorded = {
        method: (init.method ?? 'GET').toUpperCase(),
        path: url.pathname,
        headers: new Headers(init.headers),
        body: init.body,
      };
      requests.push(request);
      const reply = handler(request) ?? { status: 404, body: { code: 'not_found' } };
      return Promise.resolve(
        new Response(reply.body === undefined ? null : JSON.stringify(reply.body), {
          status: reply.status,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    }),
  );
}

/** A server where the reviewer has a valid session, plus extra routes. */
function signedIn(extra: Handler = () => undefined): Handler {
  return (request) => {
    if (request.method === 'GET' && request.path === '/api/runs') {
      return { status: 200, body: { runs: [] } };
    }
    return extra(request);
  };
}

function openAt(path: string) {
  window.history.pushState({}, '', path);
  render(<App />);
}

const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const fieldButton = (key: CopyKey) =>
  screen.findByRole('button', { name: new RegExp(escape(copy[key])) });

beforeEach(() => {
  document.cookie = 'csrf=token-123';
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, '', '/');
});

// ─── Fixtures ───────────────────────────────────────────────────────────────────────────────────

const EXPIRY_BOX = { page: 1, x: 0.62, y: 0.11, w: 0.2, h: 0.03 };
const NUMBER_BOX = { page: 1, x: 0.1, y: 0.4, w: 0.3, h: 0.05 };

function runView(overrides: Partial<RunView> = {}): RunView {
  return {
    run_id: 'run-1',
    status: 'awaiting_review',
    route: 'needs_review',
    reasons: [
      { code: 'near_expiry', field: 'expiry_date', rule_id: 'expiry', detail: { days: '20' } },
    ],
    required_documents: ['memorandum_of_association'],
    pages: 1,
    steps: [],
    form: {
      version: 1,
      fields: {
        licence_number: {
          value: '1234567',
          state: 'passed',
          origin: 'read',
          status: 'present',
          evidence_quote: 'Licence No. 1234567',
          evidence_box: NUMBER_BOX,
          rule_results: [],
        },
        expiry_date: {
          value: '2026-12-25',
          state: 'flagged',
          origin: 'read',
          status: 'present',
          evidence_quote: 'Expiry Date 25/12/2026',
          evidence_box: EXPIRY_BOX,
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
        },
      },
    },
    ...overrides,
  };
}

function serveRun(view: RunView) {
  serve(
    signedIn((request) =>
      request.method === 'GET' && request.path === `/api/runs/${view.run_id}`
        ? { status: 200, body: view }
        : undefined,
    ),
  );
}

// ─── Sign-in ────────────────────────────────────────────────────────────────────────────────────

describe('sign-in', () => {
  it.each([
    { status: 401, code: 'invalid_credentials', key: 'error.invalid_credentials' },
    { status: 429, code: 'rate_limited', key: 'error.rate_limited' },
  ] as const)('shows the $code string when the server refuses the sign-in', async (row) => {
    serve((request) => {
      if (request.path === '/api/session' && request.method === 'POST') {
        return { status: row.status, body: { code: row.code } };
      }
      return { status: 401, body: { code: 'session_expired' } };
    });
    openAt('/');

    fireEvent.change(await screen.findByLabelText(copy['signin.username.label']), {
      target: { value: 'reviewer' },
    });
    fireEvent.change(screen.getByLabelText(copy['signin.password.label']), {
      target: { value: 'wrong' },
    });
    fireEvent.click(screen.getByRole('button', { name: copy['signin.button'] }));

    expect(await screen.findByText(copy[row.key])).toBeInTheDocument();
  });

  it('opens the upload page after a successful sign-in', async () => {
    let session = false;
    serve((request) => {
      if (request.path === '/api/session' && request.method === 'POST') {
        session = true;
        return { status: 200, body: { reviewer: 'reviewer' } };
      }
      return session
        ? { status: 200, body: { runs: [] } }
        : { status: 401, body: { code: 'session_expired' } };
    });
    openAt('/');

    fireEvent.change(await screen.findByLabelText(copy['signin.username.label']), {
      target: { value: 'reviewer' },
    });
    fireEvent.change(screen.getByLabelText(copy['signin.password.label']), {
      target: { value: 'secret' },
    });
    fireEvent.click(screen.getByRole('button', { name: copy['signin.button'] }));

    expect(await screen.findByRole('heading', { name: copy['upload.title'] })).toBeInTheDocument();
  });

  it('returns to sign-in with the session string when the session expires', async () => {
    serve((request) =>
      request.path === '/api/runs'
        ? { status: 200, body: { runs: [] } }
        : { status: 401, body: { code: 'session_expired' } },
    );
    openAt('/runs/run-1');

    expect(await screen.findByText(copy['error.session_expired'])).toBeInTheDocument();
    expect(screen.getByRole('button', { name: copy['signin.button'] })).toBeInTheDocument();
  });
});

// ─── Upload ─────────────────────────────────────────────────────────────────────────────────────

function chooseFile(name: string, type: string, size = 1024) {
  const file = new File(['%PDF-1.7'], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  fireEvent.change(
    screen.getByLabelText(copy['upload.file.label'], { selector: 'input[type="file"]' }),
    {
      target: { files: [file] },
    },
  );
}

async function fillUpload(name = 'licence.pdf', type = 'application/pdf', size = 1024) {
  await screen.findByRole('heading', { name: copy['upload.title'] });
  chooseFile(name, type, size);
  fireEvent.change(screen.getByLabelText(copy['upload.applicantName.label']), {
    target: { value: 'Falcon Trading LLC' },
  });
}

const uploads = () => requests.filter((r) => r.method === 'POST' && r.path === '/api/runs');

describe('upload', () => {
  it('shows the file limits before the reviewer uploads anything', async () => {
    serve(signedIn());
    openAt('/');

    expect(await screen.findByText(copy['upload.instruction'])).toBeInTheDocument();
    expect(uploads()).toHaveLength(0);
  });

  it('refuses an 11 MB file in the browser and does not send it', async () => {
    serve(signedIn(() => ({ status: 202, body: { run_id: 'run-1', status: 'processing' } })));
    openAt('/');

    await fillUpload('big.pdf', 'application/pdf', 11 * 1024 * 1024);
    fireEvent.click(screen.getByRole('button', { name: copy['upload.button'] }));

    expect(await screen.findByText(copy['reason.too_large'])).toBeInTheDocument();
    expect(uploads()).toHaveLength(0);
  });

  it('shows the reason string when the server refuses the file', async () => {
    serve(
      signedIn((request) =>
        request.path === '/api/runs'
          ? { status: 422, body: { reason_code: 'too_many_pages', run_id: 'run-9' } }
          : undefined,
      ),
    );
    openAt('/');

    await fillUpload();
    fireEvent.click(screen.getByRole('button', { name: copy['upload.button'] }));

    expect(await screen.findByText(copy['reason.too_many_pages'])).toBeInTheDocument();
  });

  it('sends the file with the CSRF token from the cookie', async () => {
    serve(
      signedIn((request) =>
        request.path === '/api/runs'
          ? { status: 200, body: { run_id: 'run-1', status: 'awaiting_review', duplicate: true } }
          : undefined,
      ),
    );
    openAt('/');

    await fillUpload();
    fireEvent.click(screen.getByRole('button', { name: copy['upload.button'] }));

    await waitFor(() => {
      expect(uploads()).toHaveLength(1);
    });
    const [upload] = uploads();
    expect(upload?.headers.get('X-CSRF-Token')).toBe('token-123');
    const body = upload?.body as FormData;
    expect(body.get('applicant_name')).toBe('Falcon Trading LLC');
    expect((body.get('file') as File).name).toBe('licence.pdf');
  });

  it('shows the duplicate string with a link to the existing run', async () => {
    serve(
      signedIn((request) =>
        request.path === '/api/runs'
          ? { status: 200, body: { run_id: 'run-7', status: 'awaiting_review', duplicate: true } }
          : undefined,
      ),
    );
    openAt('/');

    await fillUpload();
    fireEvent.click(screen.getByRole('button', { name: copy['upload.button'] }));

    expect(await screen.findByText(copy['upload.duplicate'])).toBeInTheDocument();
    expect(screen.getByRole('link', { name: copy['upload.openRun'] })).toHaveAttribute(
      'href',
      '/runs/run-7',
    );
  });

  it('shows each processing step with its status as text until the run stops', async () => {
    let polls = 0;
    serve(
      signedIn((request) => {
        if (request.method === 'POST' && request.path === '/api/runs') {
          return { status: 202, body: { run_id: 'run-1', status: 'processing' } };
        }
        if (request.path === '/api/runs/run-1') {
          polls += 1;
          const finished = polls > 1;
          return {
            status: 200,
            body: runView({
              status: finished ? 'awaiting_review' : 'processing',
              steps: [
                { name: 'preprocess', state: 'done', duration_ms: 120 },
                { name: 'extract', state: finished ? 'done' : 'running' },
                { name: 'validate', state: finished ? 'done' : 'pending' },
              ],
            }),
          };
        }
        return undefined;
      }),
    );
    openAt('/');

    await fillUpload();
    fireEvent.click(screen.getByRole('button', { name: copy['upload.button'] }));

    const progress = await screen.findByRole('list', { name: copy['progress.title'] });
    const step = (key: CopyKey) =>
      within(progress).getByText(copy[key]).closest('li') as HTMLElement;
    await waitFor(() => {
      expect(
        within(step('progress.extract')).getByText(copy['progress.status.running']),
      ).toBeInTheDocument();
    });
    expect(
      within(step('progress.preprocess')).getByText(copy['progress.status.done']),
    ).toBeInTheDocument();
    expect(
      within(step('progress.validate')).getByText(copy['progress.status.waiting']),
    ).toBeInTheDocument();

    expect(
      await screen.findByRole('link', { name: copy['upload.openRun'] }, { timeout: 3000 }),
    ).toHaveAttribute('href', '/runs/run-1');
    expect(
      within(step('progress.validate')).getByText(copy['progress.status.done']),
    ).toBeInTheDocument();
  });
});

// ─── Review (read-only) ─────────────────────────────────────────────────────────────────────────

const highlight = () => screen.getByTestId('evidence-highlight');
// The highlight frames the evidence box with a small token-sized outset.
const boxStyle = (box: { x: number; y: number; w: number; h: number }) => ({
  left: `calc(${String(box.x * 100)}% - var(--spacing-1))`,
  top: `calc(${String(box.y * 100)}% - var(--spacing-1))`,
  width: `calc(${String(box.w * 100)}% + 2 * var(--spacing-1))`,
  height: `calc(${String(box.h * 100)}% + 2 * var(--spacing-1))`,
});

describe('review page', () => {
  it('expands flagged fields and shows their reason and evidence text', async () => {
    serveRun(runView());
    openAt('/runs/run-1');

    const flagged = await fieldButton('field.expiry_date');
    expect(flagged).toHaveAttribute('aria-expanded', 'true');
    expect(await fieldButton('field.licence_number')).toHaveAttribute('aria-expanded', 'false');
    const reason = format('reason.near_expiry', { days: '20' });
    expect(screen.getAllByText(reason).length).toBeGreaterThan(0);
    expect(screen.getByText('Expiry Date 25/12/2026')).toBeInTheDocument();
  });

  it('moves the evidence highlight to the field the reviewer selects', async () => {
    serveRun(runView());
    openAt('/runs/run-1');

    await fieldButton('field.expiry_date');
    expect(highlight().style).toMatchObject(boxStyle(EXPIRY_BOX));

    fireEvent.click(await fieldButton('field.licence_number'));

    await waitFor(() => {
      expect(highlight().style).toMatchObject(boxStyle(NUMBER_BOX));
    });
  });

  it('shows the page image of the run', async () => {
    serveRun(runView());
    openAt('/runs/run-1');

    const image = await screen.findByRole('img', {
      name: format('review.page.label', { page: '1' }),
    });
    expect(image).toHaveAttribute('src', '/api/runs/run-1/pages/1');
  });

  it.each([
    'passed',
    'flagged',
    'approved',
    'corrected',
    'overridden',
    'needs_examination',
  ] as const)('shows the %s status as text on the field', async (state) => {
    const view = runView();
    const field = view.form?.fields.licence_number;
    if (view.form && field) {
      view.form.fields = { licence_number: { ...field, state } };
    }
    serveRun(view);
    openAt('/runs/run-1');

    const button = await fieldButton('field.licence_number');
    expect(within(button).getByText(copy[`state.${state}`])).toBeInTheDocument();
  });

  it.each([
    { status: 'not_present', key: 'state.not_present' },
    { status: 'unclear', key: 'state.unclear' },
  ] as const)('shows the $status field status instead of a value', async (row) => {
    const view = runView();
    const field = view.form?.fields.licence_number;
    if (view.form && field) {
      view.form.fields = {
        licence_number: {
          ...field,
          value: row.status === 'unclear' ? '12?45' : null,
          status: row.status,
          state: 'needs_examination',
          evidence_box: null,
        },
      };
    }
    serveRun(view);
    openAt('/runs/run-1');

    const button = await fieldButton('field.licence_number');
    expect(within(button).getByText(copy[row.key])).toBeInTheDocument();
    expect(button).toHaveAttribute('aria-expanded', 'true');
  });

  it('fills a run-level reason from its own detail values', async () => {
    serveRun(
      runView({
        reasons: [{ code: 'shares_total', field: null, rule_id: null, detail: { total: '90' } }],
      }),
    );
    openAt('/runs/run-1');

    const reasons = await screen.findByRole('list', { name: copy['review.reasons.title'] });
    expect(
      within(reasons).getByText(format('reason.shares_total', { total: '90' })),
    ).toBeInTheDocument();
  });

  it.each([
    { route: 'ready', label: 'route.ready', detail: 'route.ready.detail' },
    { route: 'needs_review', label: 'route.needs_review', detail: 'route.needs_review.detail' },
    { route: 'reject', label: 'route.reject', detail: 'route.reject.detail' },
  ] as const)('shows the $route route with its detail', async (row) => {
    serveRun(runView({ route: row.route }));
    openAt('/runs/run-1');

    expect(await screen.findByText(copy[row.detail])).toBeInTheDocument();
    expect(screen.getAllByText(copy[row.label]).length).toBeGreaterThan(0);
  });

  it('lists the documents to request and the run reasons', async () => {
    serveRun(
      runView({
        required_documents: ['memorandum_of_association', 'identity_document', 'identity_document'],
        reasons: [{ code: 'ubo_needs_examination', field: null, rule_id: null, detail: {} }],
      }),
    );
    openAt('/runs/run-1');

    const documents = await screen.findByRole('list', {
      name: copy['review.requiredDocuments.title'],
    });
    expect(
      within(documents).getByText(copy['document.memorandum_of_association']),
    ).toBeInTheDocument();
    expect(within(documents).getAllByText(copy['document.identity_document'])).toHaveLength(1);
    const reasons = screen.getByRole('list', { name: copy['review.reasons.title'] });
    expect(within(reasons).getByText(copy['reason.ubo_needs_examination'])).toBeInTheDocument();
  });

  it('shows the not-found string for a run that does not exist', async () => {
    serve(signedIn());
    openAt('/runs/missing');

    expect(await screen.findByText(copy['error.not_found'])).toBeInTheDocument();
  });
});

describe('legal form value', () => {
  it('shows the legal form as words, not as its code', () => {
    const field = {
      value: 'llc',
      state: 'passed' as const,
      status: 'present' as const,
      origin: 'read' as const,
      rule_results: [],
    };
    expect(fieldValueText(field, 'legal_form')).toBe(copy['legalForm.llc']);
  });
});
