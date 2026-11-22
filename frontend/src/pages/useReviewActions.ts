// The review page's state: the current run view, the last error, and the field that gets
// keyboard focus next. Every action sends one request and shows the view the server returns.
import { useEffect, useState } from 'react';

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

/** The first undecided field after `after` in form order, or else the first one. */
function nextUndecided(view: RunView, after: string): string | null {
  const names = Object.entries(view.form?.fields ?? {})
    .filter(([, field]) => isUndecided(field))
    .map(([name]) => name);
  const order = Object.keys(view.form?.fields ?? {});
  const later = names.find((name) => order.indexOf(name) > order.indexOf(after));
  return later ?? names[0] ?? null;
}

export function useReviewActions(initial: RunView) {
  const [view, setView] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [focusName, setFocusName] = useState<string | null>(null);
  const runId = view.run_id;

  // After a retry the run processes in the background: reload until it stops. A failed
  // request counts as one more attempt, so checking goes on after a short outage.
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (view.status !== 'processing') return;
    const timer = setTimeout(() => {
      void getRun(runId).then((result) => {
        if (result.ok) setView(result.data);
        else setAttempt((n) => n + 1);
      });
    }, POLL_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [view, runId, attempt]);

  const show = (result: { ok: true; data: RunView } | { ok: false; code: string }) => {
    if (result.ok) {
      setError(null);
      setView(result.data);
      return result.data;
    }
    setError(result.code);
    return null;
  };

  const review = async (request: Partial<ReviewRequest>) =>
    show(
      await reviewRun(runId, {
        form_version: view.form?.version ?? 0,
        action_id: newId(),
        decisions: [],
        approve_form: false,
        reject_case: false,
        reject_reason: null,
        ...request,
      }),
    );

  const decide = async (name: string, decision: NewDecision) => {
    const next = await review({ decisions: [{ ...decision, decision_id: newId() }] });
    if (next !== null) setFocusName(nextUndecided(next, name));
  };

  const handlers: FormHandlers = {
    onApproveForm: () => void review({ approve_form: true }),
    onReject: (reason) => void review({ reject_case: true, reject_reason: reason }),
    onReopen: (reason) => {
      void reopenRun(runId, reason).then(show);
    },
    onSubmit: () => {
      void submitRun(runId, view.form?.version ?? 0).then(async (result) => {
        if (!result.ok) {
          setError(result.code);
          return;
        }
        show(await getRun(runId));
      });
    },
    onRetry: () => {
      void retryRun(runId).then((result) => {
        if (result.ok) setView({ ...view, status: 'processing' });
        else setError(result.code);
      });
    },
  };

  return { view, error, focusName, decide, handlers };
}
