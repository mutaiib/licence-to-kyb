// Actions on the whole form, which depend on the run status:
// - awaiting review: approve the form (only when every flagged field has a decision), reject,
//   and retry processing after a processing failure
// - awaiting submit: submit, or reject
// - rejected: reopen
// - done: the submission matched the approved form
import { Banner } from '@astryxdesign/core/Banner';
import { AlertDialog } from '@astryxdesign/core/AlertDialog';
import { Button } from '@astryxdesign/core/Button';
import { HStack } from '@astryxdesign/core/HStack';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { useState } from 'react';

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

export function FormActions({
  view,
  undecided,
  handlers,
}: {
  view: RunView;
  /** How many flagged fields have no decision yet. */
  undecided: number;
  handlers: FormHandlers;
}) {
  const [writing, setWriting] = useState<'reject' | 'reopen' | null>(null);
  const [rejectReason, setRejectReason] = useState<string | null>(null);

  if (view.status === 'done') {
    return <Banner status="success" title={copy['review.submitted']} />;
  }
  if (writing !== null) {
    const isReject = writing === 'reject';
    return (
      <InlineEditor
        label={copy[isReject ? 'review.reject.reason.label' : 'review.reopen.reason.label']}
        onCancel={() => {
          setWriting(null);
        }}
        onSave={(reason) => {
          setWriting(null);
          if (isReject) setRejectReason(reason);
          else handlers.onReopen(reason);
        }}
      />
    );
  }
  if (view.status === 'rejected') {
    return (
      <VStack gap={3}>
        <Banner status="error" title={copy['review.rejected']} />
        <HStack>
          <Button
            label={copy['review.reopen']}
            onClick={() => {
              setWriting('reopen');
            }}
          />
        </HStack>
      </VStack>
    );
  }
  if (view.status !== 'awaiting_review' && view.status !== 'awaiting_submit') {
    return null; // still processing
  }

  const canRetry = view.reasons.some((reason) => RETRYABLE.has(reason.code));
  const isApproved = view.status === 'awaiting_submit';
  return (
    <VStack gap={3}>
      {canRetry && (
        <HStack gap={3} vAlign="center">
          <Text>{copy['review.retry.help']}</Text>
          <Button label={copy['review.retry']} onClick={handlers.onRetry} />
        </HStack>
      )}
      <Text>
        {isApproved
          ? copy['review.ready']
          : undecided === 1
            ? copy['review.remaining.one']
            : undecided > 1
              ? format('review.remaining', { count: String(undecided) })
              : copy['review.allDecided']}
      </Text>
      <HStack gap={2} wrap="wrap">
        {!isApproved && (
          <Button
            label={copy['review.approveForm']}
            variant="primary"
            isDisabled={undecided > 0}
            onClick={handlers.onApproveForm}
          />
        )}
        <Button
          label={copy['review.submit']}
          variant={isApproved ? 'primary' : 'secondary'}
          isDisabled={!isApproved}
          onClick={handlers.onSubmit}
        />
        <Button
          label={copy['review.reject']}
          variant="destructive"
          onClick={() => {
            setWriting('reject');
          }}
        />
      </HStack>
      <AlertDialog
        isOpen={rejectReason !== null}
        onOpenChange={(isOpen) => {
          if (!isOpen) setRejectReason(null);
        }}
        title={copy['review.reject']}
        description={copy['review.reject.confirm']}
        actionLabel={copy['review.reject']}
        cancelLabel={copy['review.cancel']}
        onAction={() => {
          if (rejectReason !== null) handlers.onReject(rejectReason);
          setRejectReason(null);
        }}
      />
    </VStack>
  );
}
