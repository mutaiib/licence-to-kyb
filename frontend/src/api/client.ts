/**
 * A typed wrapper over `fetch` for the backend API (specs/001-licence-to-kyb/contracts/http-api.md).
 *
 * - Types come from `generated.ts` (`npm run types`), never by hand.
 * - Every request sends the session cookie. State-changing requests send `X-CSRF-Token` with the
 *   value of the `csrf` cookie.
 * - Failures return the API's code. The client never reads message text.
 * - A `401 session_expired` also tells the app that the reviewer is signed out.
 */
import type { components, paths } from './generated';

type Schemas = components['schemas'];
export type RunView = Schemas['RunView'];
export type RunCreated = Schemas['RunCreated'];
export type FormFieldView = Schemas['FormFieldView'];
export type FormPerson = Schemas['FormPerson'];
export type FormActivity = Schemas['FormActivity'];
export type EvidenceBox = Schemas['EvidenceBox'];
export type StepView = Schemas['StepView'];
export type ReasonCode = Schemas['ReasonView']['code'];
export type ReviewRequest = Schemas['ReviewIn'];
export type Decision = Schemas['DecisionIn'];
export type SubmitResult = Schemas['SubmitOut'];
export type RunStatus = RunView['status'];
export type Route = NonNullable<RunView['route']>;
export type FieldState = FormFieldView['state'];
type SessionOut = paths['/api/session']['post']['responses'][200]['content']['application/json'];
type RunList = paths['/api/runs']['get']['responses'][200]['content']['application/json'];

/** API error codes plus `network`, which the client uses when the server cannot be reached. */
export type ErrorCode = string;

export type Result<T> = { ok: true; data: T } | { ok: false; code: ErrorCode };

export type UploadResult =
  | { kind: 'created'; run: RunCreated }
  | { kind: 'refused'; reasonCode: ReasonCode }
  | { kind: 'failed'; code: ErrorCode };

const CSRF_COOKIE = 'csrf';
const CSRF_HEADER = 'X-CSRF-Token';
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

type Listener = () => void;
const sessionExpiredListeners = new Set<Listener>();

/** Calls `listener` whenever a request returns `401 session_expired`. Returns an unsubscribe. */
export function onSessionExpired(listener: Listener): () => void {
  sessionExpiredListeners.add(listener);
  return () => {
    sessionExpiredListeners.delete(listener);
  };
}

function readCookie(name: string): string | null {
  for (const part of document.cookie.split(';')) {
    const [key, ...rest] = part.trim().split('=');
    if (key === name) {
      return decodeURIComponent(rest.join('='));
    }
  }
  return null;
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return (await response.json()) as unknown;
  } catch {
    return null;
  }
}

function field(body: unknown, name: string): string | null {
  if (typeof body === 'object' && body !== null && name in body) {
    const value = (body as Record<string, unknown>)[name];
    return typeof value === 'string' ? value : null;
  }
  return null;
}

interface Raw {
  status: number;
  body: unknown;
}

async function send(method: string, path: string, body?: BodyInit): Promise<Raw | null> {
  const headers = new Headers();
  if (typeof body === 'string') {
    headers.set('Content-Type', 'application/json');
  }
  if (!SAFE_METHODS.has(method)) {
    const token = readCookie(CSRF_COOKIE);
    if (token !== null) {
      headers.set(CSRF_HEADER, token);
    }
  }
  let response: Response;
  try {
    response = await fetch(path, { method, headers, body, credentials: 'include' });
  } catch {
    return null;
  }
  const json = response.status === 204 ? null : await readJson(response);
  if (response.status === 401 && field(json, 'code') === 'session_expired') {
    sessionExpiredListeners.forEach((listener) => {
      listener();
    });
  }
  return { status: response.status, body: json };
}

function toResult<T>(raw: Raw | null, okStatuses: readonly number[]): Result<T> {
  if (raw === null) {
    return { ok: false, code: 'network' };
  }
  if (okStatuses.includes(raw.status)) {
    return { ok: true, data: raw.body as T };
  }
  return { ok: false, code: field(raw.body, 'code') ?? 'network' };
}

export async function signIn(username: string, password: string): Promise<Result<SessionOut>> {
  const body: paths['/api/session']['post']['requestBody']['content']['application/json'] = {
    username,
    password,
  };
  return toResult(await send('POST', '/api/session', JSON.stringify(body)), [200]);
}

export async function signOut(): Promise<Result<null>> {
  return toResult(await send('DELETE', '/api/session'), [204]);
}

export async function listRuns(): Promise<Result<RunList>> {
  return toResult(await send('GET', '/api/runs'), [200]);
}

export async function getRun(runId: string): Promise<Result<RunView>> {
  return toResult(await send('GET', `/api/runs/${encodeURIComponent(runId)}`), [200]);
}

export async function createRun(file: File, applicantName: string): Promise<UploadResult> {
  const form = new FormData();
  form.append('file', file);
  form.append('applicant_name', applicantName);
  const raw = await send('POST', '/api/runs', form);
  if (raw === null) {
    return { kind: 'failed', code: 'network' };
  }
  if (raw.status === 200 || raw.status === 202) {
    return { kind: 'created', run: raw.body as RunCreated };
  }
  const reasonCode = field(raw.body, 'reason_code');
  if (raw.status === 422 && reasonCode !== null) {
    return { kind: 'refused', reasonCode: reasonCode as ReasonCode };
  }
  return { kind: 'failed', code: field(raw.body, 'code') ?? 'network' };
}

// ─── Reviewer actions (User Story 2). Each action carries a new random ID, so a repeated
// request (for example after a network retry) changes nothing on the server. ──────────────────

export function newId(): string {
  return crypto.randomUUID();
}

const runPath = (runId: string, action: string) =>
  `/api/runs/${encodeURIComponent(runId)}/${action}`;

export async function reviewRun(runId: string, request: ReviewRequest): Promise<Result<RunView>> {
  return toResult(await send('POST', runPath(runId, 'review'), JSON.stringify(request)), [200]);
}

export async function submitRun(runId: string, formVersion: number): Promise<Result<SubmitResult>> {
  const body = { action_id: newId(), form_version: formVersion };
  return toResult(await send('POST', runPath(runId, 'submit'), JSON.stringify(body)), [200]);
}

export async function reopenRun(runId: string, reason: string): Promise<Result<RunView>> {
  const body = { action_id: newId(), reason };
  return toResult(await send('POST', runPath(runId, 'reopen'), JSON.stringify(body)), [200]);
}

export async function retryRun(runId: string): Promise<Result<RunCreated>> {
  const body = { action_id: newId() };
  return toResult(await send('POST', runPath(runId, 'retry'), JSON.stringify(body)), [202]);
}

/** The URL of a page image (1-based page number). */
export function pageImageUrl(runId: string, page: number): string {
  return `/api/runs/${encodeURIComponent(runId)}/pages/${String(page)}`;
}
