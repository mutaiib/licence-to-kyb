// The review page's state: the current run view, the last error, and where keyboard focus goes
// next. Every action sends one request and shows the view the server returns.
//
// Actions run one at a time, in click order: each request reads the newest form version, so
// two quick clicks never send a stale version, and a slow reply never replaces a newer view.
import { useEffect, useRef, useState } from 'react';

import {
  getRun,
  newId,
  reopenRun,
  retryRun,
  reviewRun,
  submitRun,
  type ReviewRequest,
  type RunView,
} from '../api/client';
import type { NewDecision } from '../components/FieldActions';
import type { FormHandlers } from '../components/FormActions';
import { isUndecided } from '../text';

const POLL_MS = 1000;

/** Where focus goes after a decision: a field's first action, or the Next step button. */
export const NEXT_STEP = '__next_step__';

/** A request to move focus. `n` changes with every request, so the same target can be
 * focused again. */
export interface FocusRequest {
  target: string;
  n: number;
}

/** The first undecided field after `after` in form order, or else the first one. */
function nextUndecided(view: RunView, after: string): string | null {
  const names = Object.entries(view.form?.fields ?? {})
    .filter(([, field]) => isUndecided(field))
    .map(([name]) => name);
  const order = Object.keys(view.form?.fields ?? {});
  const later = names.find((name) => order.indexOf(name) > order.indexOf(after));
  return later ?? names[0] ?? null;
}

type Reply = { ok: true; data: RunView } | { ok: false; code: string };

export function useReviewActions(initial: RunView) {
  const [view, setView] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [focus, setFocus] = useState<FocusRequest | null>(null);
  const runId = view.run_id;

  // The newest view, for requests that start before the page renders again.
  const latest = useRef(initial);
  const showView = (next: RunView) => {
    latest.current = next;
    setView(next);
  };

  // One action at a time: each waits for the one before it.
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  function inTurn<T>(task: () => Promise<T>): Promise<T> {
    const next = queue.current.then(task);
    queue.current = next.catch(() => undefined);
    return next;
  }

  // After a retry the run processes in the background: reload until it stops. A failed
  // request counts as one more attempt, so checking goes on after a short outage.
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (view.status !== 'processing') return;
    const timer = setTimeout(() => {
      void getRun(runId).then((result) => {
        if (result.ok) showView(result.data);
        else setAttempt((n) => n + 1);
      });
    }, POLL_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [view, runId, attempt]);

  const show = (result: Reply): RunView | null => {
    if (result.ok) {
      setError(null);
      showView(result.data);
      return result.data;
    }
    setError(result.code);
    return null;
  };

  const review = (request: Partial<ReviewRequest>) =>
    inTurn(async () =>
      show(
        await reviewRun(runId, {
          form_version: latest.current.form?.version ?? 0,
          action_id: newId(),
          decisions: [],
          approve_form: false,
          reject_case: false,
          reject_reason: null,
          ...request,
        }),
      ),
    );

  /** Sends one field decision. Resolves true when the server accepted it. */
  const decide = async (name: string, decision: NewDecision): Promise<boolean> => {
    const next = await review({ decisions: [{ ...decision, decision_id: newId() }] });
    if (next === null) return false;
    setFocus((before) => ({
      target: nextUndecided(next, name) ?? NEXT_STEP,
      n: (before?.n ?? 0) + 1,
    }));
    return true;
  };

  const handlers: FormHandlers = {
    onApproveForm: () => void review({ approve_form: true }),
    onReject: (reason) => void review({ reject_case: true, reject_reason: reason }),
    onReopen: (reason) => {
      void inTurn(async () => show(await reopenRun(runId, reason)));
    },
    onSubmit: () => {
      void inTurn(async () => {
        const result = await submitRun(runId, latest.current.form?.version ?? 0);
        if (!result.ok) {
          setError(result.code);
          return;
        }
        show(await getRun(runId));
      });
    },
    onRetry: () => {
      void inTurn(async () => {
        const result = await retryRun(runId);
        if (result.ok) showView({ ...latest.current, status: 'processing' });
        else setError(result.code);
      });
    },
  };

  return { view, error, focus, decide, handlers };
}
