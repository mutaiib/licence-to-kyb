// Scaffolded from `astryx template detail-page`: a Layout with the record in the content region and a
// LayoutPanel rail. Here the content region shows the licence page, and the rail shows the KYB form.
// The rail reads top to bottom in the order a reviewer works: the next step, the fields to examine,
// the fields that passed, the documents to request, and last the exception (reject the case).
import { Banner } from '@astryxdesign/core/Banner';
import { Collapsible, CollapsibleGroup } from '@astryxdesign/core/Collapsible';
import { Heading } from '@astryxdesign/core/Heading';
import { HStack } from '@astryxdesign/core/HStack';
import { useMediaQuery } from '@astryxdesign/core/hooks';
import { Layout, LayoutContent, LayoutPanel } from '@astryxdesign/core/Layout';
import { Link } from '@astryxdesign/core/Link';
import { List, ListItem } from '@astryxdesign/core/List';
import { MetadataList, MetadataListItem } from '@astryxdesign/core/MetadataList';
import { Spinner } from '@astryxdesign/core/Spinner';
import { StackItem } from '@astryxdesign/core/Stack';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { useEffect, useState, type ReactNode } from 'react';

import { getRun, type FormFieldView, type ReasonCode, type RunView } from '../api/client';
import { ConfidenceDetails } from '../components/ConfidenceDetails';
import { EvidenceViewer } from '../components/EvidenceViewer';
import { ProposalDetails } from '../components/ProposalDetails';
import { FieldActions, type NewDecision } from '../components/FieldActions';
import { NextStep, RejectCase } from '../components/FormActions';
import { StatusLabel } from '../components/StatusLabel';
import { NEXT_STEP, useReviewActions, type FocusRequest } from './useReviewActions';
import { tracePath, useLinkHandler } from '../router';
import { copy, format } from '../copy';
import {
  documentLabel,
  errorText,
  fieldLabel,
  isFlagged,
  isUndecided,
  reasonText,
  shortTime,
  fieldValueText,
} from '../text';

type Load =
  { kind: 'loading' } | { kind: 'failed'; code: string } | { kind: 'loaded'; view: RunView };

/**
 * Loads the run once per run ID. The result is stored with the ID it belongs to, so a page that
 * moves to another run shows `loading` instead of the previous run's result.
 */
function useRun(runId: string): Load {
  const [load, setLoad] = useState<{ runId: string; load: Load } | null>(null);
  useEffect(() => {
    let isCancelled = false;
    void getRun(runId).then((result) => {
      if (isCancelled) return;
      setLoad({
        runId,
        load: result.ok
          ? { kind: 'loaded', view: result.data }
          : { kind: 'failed', code: result.code },
      });
    });
    return () => {
      isCancelled = true;
    };
  }, [runId]);
  return load?.runId === runId ? load.load : { kind: 'loading' };
}

interface FailingRule {
  rule_id: string;
  reason_code: ReasonCode;
  detail?: Readonly<Record<string, string>>;
}

interface FieldActing {
  canAct: boolean;
  focus: FocusRequest | null;
  onDecide: (name: string, decision: NewDecision) => Promise<boolean>;
}

function FieldDetails({
  name,
  field,
  acting,
}: {
  name: string;
  field: FormFieldView;
  acting: FieldActing;
}) {
  const failing: FailingRule[] = [];
  for (const rule of field.rule_results) {
    if (rule.reason_code !== null) {
      failing.push({ rule_id: rule.rule_id, reason_code: rule.reason_code, detail: rule.detail });
    }
  }
  return (
    <VStack gap={3} paddingBlockEnd={2}>
      {failing.length > 0 && (
        <List density="compact" listStyle="disc">
          {failing.map((rule) => (
            <ListItem
              key={rule.rule_id}
              label={<Text>{reasonText(rule.reason_code, rule.detail)}</Text>}
            />
          ))}
        </List>
      )}
      <MetadataList>
        <MetadataListItem label={copy['review.evidence.label']}>
          <Text>{field.evidence_quote ?? copy['state.not_present']}</Text>
        </MetadataListItem>
        {field.origin === 'entered_by_reviewer' && (
          <MetadataListItem label={copy['state.entered_by_reviewer']}>
            <Text>{fieldValueText(field)}</Text>
          </MetadataListItem>
        )}
      </MetadataList>
      {field.model_rationale != null && (
        <ProposalDetails
          rationale={field.model_rationale}
          accepted={field.proposal_accepted === true}
        />
      )}
      {acting.canAct && (
        <FieldActions
          name={name}
          field={field}
          focusRequest={acting.focus?.target === name ? acting.focus.n : null}
          onDecide={(decision) => acting.onDecide(name, decision)}
        />
      )}
      {field.confidence != null && (
        <Collapsible
          defaultIsOpen={false}
          trigger={<Text color="secondary">{copy['review.details']}</Text>}
        >
          <ConfidenceDetails confidence={field.confidence} isFlagged={isUndecided(field)} />
        </Collapsible>
      )}
    </VStack>
  );
}

function FieldTrigger({
  name,
  field,
  isSelected,
}: {
  name: string;
  field: FormFieldView;
  isSelected: boolean;
}) {
  const value = fieldValueText(field, name);
  return (
    <HStack gap={3} vAlign="center" width="100%">
      <StackItem size="fill">
        <VStack gap={0.5}>
          <Text weight="semibold" color={isSelected ? 'accent' : 'primary'}>
            {fieldLabel(name)}
          </Text>
          <Text color={field.status === 'present' ? 'primary' : 'secondary'}>{value}</Text>
        </VStack>
      </StackItem>
      <StatusLabel state={field.state} />
    </HStack>
  );
}

interface Selection {
  selected: string | null;
  onSelect: (name: string) => void;
}

/** A group of field rows. Each row opens to show its evidence, checks and actions. */
function FieldGroup({
  names,
  fields,
  selection,
  acting,
  isOpenAtStart,
}: {
  names: readonly string[];
  fields: Readonly<Record<string, FormFieldView>>;
  selection: Selection;
  acting: FieldActing;
  isOpenAtStart: boolean;
}) {
  const [open, setOpen] = useState<string[]>(() => (isOpenAtStart ? [...names] : []));
  // The group reports the full list of open fields. The field the reviewer just opened or
  // closed is the one that is in only one of the two lists; it becomes the selected field.
  const change = (value: string | string[]) => {
    const next = Array.isArray(value) ? value : [value];
    const opened = next.find((name) => !open.includes(name));
    const closed = open.find((name) => !next.includes(name));
    setOpen(next);
    const toggled = opened ?? closed;
    if (toggled !== undefined) selection.onSelect(toggled);
  };
  return (
    <CollapsibleGroup type="multiple" value={open} onChange={change} hasDividers>
      {names.map((name) => {
        const field = fields[name];
        if (field === undefined) return null;
        return (
          <Collapsible
            key={name}
            value={name}
            trigger={
              <FieldTrigger name={name} field={field} isSelected={name === selection.selected} />
            }
          >
            <FieldDetails name={name} field={field} acting={acting} />
          </Collapsible>
        );
      })}
    </CollapsibleGroup>
  );
}

/**
 * The KYB form in two parts: the fields to examine, open, and the fields that passed, closed.
 * `between` is shown between them (on a phone: the licence page, next to the flagged fields).
 */
function KybForm({
  fields,
  selection,
  acting,
  between,
}: {
  fields: Readonly<Record<string, FormFieldView>>;
  selection: Selection;
  acting: FieldActing;
  between?: ReactNode;
}) {
  const names = Object.keys(fields);
  const toExamine = names.filter((name) => fields[name] !== undefined && isFlagged(fields[name]));
  const passedNames = names.filter((name) => !toExamine.includes(name));
  const examineTitle = format('review.toExamine', { count: String(toExamine.length) });
  return (
    <VStack gap={4}>
      <Heading level={2}>{copy['review.form.title']}</Heading>
      {toExamine.length > 0 && (
        <VStack gap={2} role="region" aria-label={examineTitle}>
          <Heading level={3}>{examineTitle}</Heading>
          <FieldGroup
            names={toExamine}
            fields={fields}
            selection={selection}
            acting={acting}
            isOpenAtStart
          />
        </VStack>
      )}
      {between}
      {passedNames.length > 0 && (
        <Collapsible
          defaultIsOpen={false}
          trigger={
            <Text weight="semibold">
              {format('review.passedFields', { count: String(passedNames.length) })}
            </Text>
          }
        >
          <FieldGroup
            names={passedNames}
            fields={fields}
            selection={selection}
            acting={acting}
            isOpenAtStart={false}
          />
        </Collapsible>
      )}
    </VStack>
  );
}

/** The field to select first: a flagged field with evidence, else any field with evidence. */
function firstSelection(fields: Readonly<Record<string, FormFieldView>>): string | null {
  const entries = Object.entries(fields);
  const flagged = entries.find(([, field]) => isFlagged(field) && field.evidence_box != null);
  const located = entries.find(([, field]) => field.evidence_box != null);
  const first = flagged ?? located ?? entries[0];
  return first === undefined ? null : first[0];
}

/** Reasons about the whole run. A field's own reasons show on the field, so they are not
 * repeated here. */
function RunReasons({ view }: { view: RunView }) {
  const runReasons = view.reasons.filter((reason) => reason.field === null);
  if (runReasons.length === 0) return null;
  return (
    <List header={<Heading level={2}>{copy['review.reasons.title']}</Heading>} listStyle="disc">
      {runReasons.map((reason, index) => (
        <ListItem
          key={`${reason.code}-${String(index)}`}
          label={<Text>{reasonText(reason.code, reason.detail)}</Text>}
        />
      ))}
    </List>
  );
}

/** The documents to ask the applicant for. Needed after the decision, so shown after the form. */
function DocumentsToRequest({ view }: { view: RunView }) {
  const documents = [...new Set(view.required_documents)];
  if (documents.length === 0) return null;
  return (
    <List
      header={<Heading level={2}>{copy['review.requiredDocuments.title']}</Heading>}
      listStyle="disc"
    >
      {documents.map((code) => (
        <ListItem key={code} label={documentLabel(code)} />
      ))}
    </List>
  );
}

function RunHeader({ view }: { view: RunView }) {
  const trace = tracePath(view.run_id);
  return (
    <VStack gap={1}>
      <Heading level={1}>{view.applicant_name}</Heading>
      <HStack gap={3} wrap="wrap" vAlign="center">
        <Text color="secondary">
          {format('review.uploaded', { time: shortTime(view.created_at) })}
        </Text>
        <Link href={trace} onClick={useLinkHandler(trace)} hasUnderline>
          {copy['review.trace.link']}
        </Link>
      </HStack>
    </VStack>
  );
}

function Review({ initial }: { initial: RunView }) {
  const { view, error, focus, decide, handlers } = useReviewActions(initial);
  const fields = view.form?.fields ?? {};
  const acting: FieldActing = {
    canAct: view.status === 'awaiting_review' || view.status === 'awaiting_submit',
    focus,
    onDecide: decide,
  };
  const undecided = Object.values(fields).filter(isUndecided).length;
  const [selected, setSelected] = useState<string | null>(() => firstSelection(fields));
  const isNarrow = useMediaQuery('(max-width: 1024px)');
  const box = selected === null ? null : (fields[selected]?.evidence_box ?? null);
  const page = box?.page ?? 1;

  const document =
    view.pages > 0 ? <EvidenceViewer runId={view.run_id} page={page} box={box} /> : null;
  const selection: Selection = { selected, onSelect: setSelected };
  // The order a reviewer works in: what to do now, the fields that need a decision, then the
  // rest. Rejecting the case is the exception, so it comes last.
  const panel = (between?: ReactNode) => (
    <VStack gap={6}>
      {error !== null && (
        <VStack role="alert">
          <Banner status="error" title={errorText(error)} />
        </VStack>
      )}
      <NextStep
        view={view}
        undecided={undecided}
        handlers={handlers}
        focusRequest={focus?.target === NEXT_STEP ? focus.n : null}
      />
      <RunReasons view={view} />
      {view.form !== null && (
        <KybForm fields={fields} selection={selection} acting={acting} between={between} />
      )}
      {view.form === null && between}
      <DocumentsToRequest view={view} />
      <RejectCase view={view} onReject={handlers.onReject} />
    </VStack>
  );

  if (isNarrow) {
    return (
      <VStack gap={4}>
        <RunHeader view={view} />
        {panel(document)}
      </VStack>
    );
  }
  return (
    <Layout
      height="auto"
      content={
        <LayoutContent padding={4} label={format('review.page.label', { page: String(page) })}>
          <VStack gap={4}>
            <RunHeader view={view} />
            {document}
          </VStack>
        </LayoutContent>
      }
      end={
        <LayoutPanel width={520} hasDivider padding={4} label={copy['review.form.title']}>
          {panel()}
        </LayoutPanel>
      }
    />
  );
}

export function ReviewPage({ runId }: { runId: string }) {
  const load = useRun(runId);
  if (load.kind === 'loading') {
    return <Spinner size="lg" aria-label={copy['app.loading']} />;
  }
  if (load.kind === 'failed') {
    return load.code === 'session_expired' ? null : (
      <VStack role="alert">
        <Banner status="error" title={errorText(load.code)} />
      </VStack>
    );
  }
  return <Review key={load.view.run_id} initial={load.view} />;
}
