// The reviewer's actions on one form field: approve it, correct (or enter) its value, or
// override a check that could not run. The page sends each decision to the server at once.
import { Button } from '@astryxdesign/core/Button';
import { HStack } from '@astryxdesign/core/HStack';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { useEffect, useRef, useState } from 'react';

import type { Decision, FormFieldView } from '../api/client';
import { copy, format } from '../copy';
import { fieldLabel, isUndecided, valueText } from '../text';
import { InlineEditor } from './InlineEditor';

/** Fields a reviewer can type a value into (the server has the same list). Lists such as
 * activities and owners are approved, not retyped. */
const CORRECTABLE = new Set([
  'legal_name_en',
  'legal_name_ar',
  'legal_form',
  'licence_number',
  'issue_date',
  'expiry_date',
  'registered_address',
  'chamber_number',
]);

export type NewDecision = Omit<Decision, 'decision_id'>;

type Editing = { kind: 'value' } | { kind: 'override'; ruleId: string } | null;

export function FieldActions({
  name,
  field,
  focusRequest,
  onDecide,
}: {
  name: string;
  field: FormFieldView;
  /** Changes each time keyboard focus must move here (after a decision on another field). */
  focusRequest: number | null;
  /** Sends the decision; resolves true when the server accepted it. */
  onDecide: (decision: NewDecision) => Promise<boolean>;
}) {
  const [editing, setEditing] = useState<Editing>(null);
  const firstButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (focusRequest !== null) firstButton.current?.focus();
  }, [focusRequest]);

  // The editor stays open, with what the reviewer typed, until the server accepts the value.
  const send = (decision: NewDecision) => {
    void onDecide(decision).then((isAccepted) => {
      if (isAccepted) setEditing(null);
    });
  };

  const label = { field: fieldLabel(name) };
  const overridable = field.rule_results.filter(
    // A check that could not run, or one whose rule says it can be wrong (an inferred
    // licence number pattern): the backend marks both as overridable.
    (rule) => rule.outcome !== 'passed' && rule.overridable,
  );

  if (editing?.kind === 'value') {
    return (
      <InlineEditor
        label={copy['review.correct.label']}
        initial={valueText(field.value) ?? ''}
        onCancel={() => {
          setEditing(null);
        }}
        onSave={(value) => {
          send({ field: name, action: 'correct', value });
        }}
      />
    );
  }
  if (editing?.kind === 'override') {
    const ruleId = editing.ruleId;
    return (
      <VStack gap={2}>
        <Text color="secondary">{copy['review.override.help']}</Text>
        <InlineEditor
          label={copy['review.override.reason.label']}
          onCancel={() => {
            setEditing(null);
          }}
          onSave={(reason) => {
            send({ rule_id: ruleId, action: 'override', reason });
          }}
        />
      </VStack>
    );
  }

  const isMissing = field.status !== 'present';
  // A missing value is entered, not approved; a missing list (owners) can only be approved.
  const canApprove = isUndecided(field) && (!isMissing || !CORRECTABLE.has(name));
  return (
    <HStack gap={2} wrap="wrap">
      {canApprove && (
        <Button
          ref={firstButton}
          label={format('review.approve.field', label)}
          variant="primary"
          onClick={() => {
            send({ field: name, action: 'approve' });
          }}
        >
          {copy['review.approve']}
        </Button>
      )}
      {CORRECTABLE.has(name) && (
        <Button
          ref={canApprove ? undefined : firstButton}
          label={format(isMissing ? 'review.enterValue.field' : 'review.correct.field', label)}
          onClick={() => {
            setEditing({ kind: 'value' });
          }}
        >
          {copy[isMissing ? 'review.enterValue' : 'review.correct']}
        </Button>
      )}
      {overridable.map((rule) => (
        <Button
          key={rule.rule_id}
          label={format('review.override.field', label)}
          onClick={() => {
            setEditing({ kind: 'override', ruleId: rule.rule_id });
          }}
        >
          {copy['review.override']}
        </Button>
      ))}
    </HStack>
  );
}
