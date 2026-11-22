// Actions on the whole form, in two parts:
// - NextStep, at the top: one card that says what to do now, with at most one main button.
//     a flagged field has no decision  → examine the fields (the buttons are on the fields)
//     every field has a decision        → Approve form
//     the form is approved              → Submit
//     processing stopped                → Retry processing
//     rejected                          → Reopen case
//     done                              → nothing more to do
// - RejectCase, at the end: the exception, with a reason and a confirmation.
import { AlertDialog } from '@astryxdesign/core/AlertDialog';
import { Banner } from '@astryxdesign/core/Banner';
import { Button } from '@astryxdesign/core/Button';
import { HStack } from '@astryxdesign/core/HStack';
import { VStack } from '@astryxdesign/core/VStack';
import { useEffect, useRef, useState } from 'react';

import type { RunView } from '../api/client';
import { copy, format } from '../copy';
import { InlineEditor } from './InlineEditor';

const RETRYABLE = new Set(['processing_failed', 'budget_exhausted']);

export interface FormHandlers {
  onApproveForm: () => void;
  onSubmit: () => void;
  onReject: (reason: string) => void;
  onReopen: (reason: string) => void;
  onRetry: () => void;
}

type Status = 'info' | 'warning' | 'error' | 'success';

interface Step {
  status: Status;
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}

/** What the reviewer does now. Null while the system is still processing. */
function nextStep(view: RunView, undecided: number, handlers: FormHandlers): Step | null {
  if (view.status === 'done') {
    return {
      status: 'success',
      title: copy['next.done.title'],
      description: copy['review.submitted'],
    };
  }
  if (view.status === 'rejected') {
    const bySystem = view.route === 'reject';
    return {
      status: 'error',
      title: copy[bySystem ? 'route.reject' : 'next.rejected.title'],
      description: copy[bySystem ? 'route.reject.detail' : 'review.rejected'],
    };
  }
  if (view.status !== 'awaiting_review' && view.status !== 'awaiting_submit') return null;

  if (view.reasons.some((reason) => RETRYABLE.has(reason.code))) {
    return {
      status: 'error',
      title: copy['next.retry.title'],
      description: copy['review.retry.help'],
      action: { label: copy['review.retry'], onClick: handlers.onRetry },
    };
  }
  if (view.form === null) {
    return {
      status: 'error',
      title: copy['route.reject'],
      description: copy['route.reject.detail'],
    };
  }
  if (undecided > 0) {
    return {
      status: 'warning',
      title:
        undecided === 1
          ? copy['next.examine.one']
          : format('next.examine', { count: String(undecided) }),
      description: copy['next.examine.detail'],
    };
  }
  // Submit needs an approval of this exact form version (FR-026). A ready run waits for
  // submit too, but nobody has approved it yet.
  if (view.form_approved && view.status === 'awaiting_submit') {
    return {
      status: 'success',
      title: copy['next.submit.title'],
      description: copy['review.ready'],
      action: { label: copy['review.submit'], onClick: handlers.onSubmit },
    };
  }
  return {
    status: 'info',
    title: copy['next.approve.title'],
    // A ready run had nothing flagged; say so, then ask for the approval.
    description: copy[view.route === 'ready' ? 'route.ready.detail' : 'review.allDecided'],
    action: { label: copy['review.approveForm'], onClick: handlers.onApproveForm },
  };
}

export function NextStep({
  view,
  undecided,
  handlers,
  focusRequest = null,
}: {
  view: RunView;
  /** How many flagged fields have no decision yet. */
  undecided: number;
  handlers: FormHandlers;
  /** Changes each time keyboard focus must move to the main button (the last flagged field
   * has a decision, so the next step is Approve form). */
  focusRequest?: number | null;
}) {
  const [isReopening, setIsReopening] = useState(false);
  const mainButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (focusRequest !== null) mainButton.current?.focus();
  }, [focusRequest]);
  const step = nextStep(view, undecided, handlers);
  if (step === null) return null;
  const canReopen = view.status === 'rejected';
  return (
    <VStack gap={3} role="region" aria-label={copy['next.label']}>
      <Banner status={step.status} title={step.title} description={step.description} />
      {step.action !== undefined && (
        <HStack>
          <Button
            ref={mainButton}
            label={step.action.label}
            variant="primary"
            onClick={step.action.onClick}
          />
        </HStack>
      )}
      {canReopen && !isReopening && (
        <HStack>
          <Button
            label={copy['review.reopen']}
            onClick={() => {
              setIsReopening(true);
            }}
          />
        </HStack>
      )}
      {isReopening && (
        <InlineEditor
          label={copy['review.reopen.reason.label']}
          onCancel={() => {
            setIsReopening(false);
          }}
          onSave={(reason) => {
            setIsReopening(false);
            handlers.onReopen(reason);
          }}
        />
      )}
    </VStack>
  );
}

/** Reject the case: a quiet button at the end of the panel, then a reason, then a confirmation. */
export function RejectCase({
  view,
  onReject,
}: {
  view: RunView;
  onReject: (reason: string) => void;
}) {
  const [isWriting, setIsWriting] = useState(false);
  const [reason, setReason] = useState<string | null>(null);
  if (view.status !== 'awaiting_review' && view.status !== 'awaiting_submit') return null;
  return (
    <VStack gap={3}>
      {isWriting ? (
        <InlineEditor
          label={copy['review.reject.reason.label']}
          onCancel={() => {
            setIsWriting(false);
          }}
          onSave={(text) => {
            setIsWriting(false);
            setReason(text);
          }}
        />
      ) : (
        <HStack>
          <Button
            label={copy['review.reject']}
            variant="ghost"
            onClick={() => {
              setIsWriting(true);
            }}
          />
        </HStack>
      )}
      <AlertDialog
        isOpen={reason !== null}
        onOpenChange={(isOpen) => {
          if (!isOpen) setReason(null);
        }}
        title={copy['review.reject']}
        description={copy['review.reject.confirm']}
        actionLabel={copy['review.reject']}
        cancelLabel={copy['review.cancel']}
        onAction={() => {
          if (reason !== null) onReject(reason);
          setReason(null);
        }}
      />
    </VStack>
  );
}
