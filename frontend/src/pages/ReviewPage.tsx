// Scaffolded from `astryx template detail-page`: a Layout with the record in the content region and a
// LayoutPanel rail. Here the content region shows the licence page, and the rail shows the KYB form.
// Read-only for User Story 1: the approve and correct actions come with User Story 2.
import { Banner } from '@astryxdesign/core/Banner';
import { Collapsible, CollapsibleGroup } from '@astryxdesign/core/Collapsible';
import { Heading } from '@astryxdesign/core/Heading';
import { HStack } from '@astryxdesign/core/HStack';
import { useMediaQuery } from '@astryxdesign/core/hooks';
import { Layout, LayoutContent, LayoutPanel } from '@astryxdesign/core/Layout';
import { List, ListItem } from '@astryxdesign/core/List';
import { MetadataList, MetadataListItem } from '@astryxdesign/core/MetadataList';
import { Spinner } from '@astryxdesign/core/Spinner';
import { StackItem } from '@astryxdesign/core/Stack';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { useEffect, useState } from 'react';

import { getRun, type FormFieldView, type RunView } from '../api/client';
import { EvidenceViewer } from '../components/EvidenceViewer';
import { StatusLabel } from '../components/StatusLabel';
import { copy, format } from '../copy';
import {
  documentLabel,
  errorText,
  fieldLabel,
  isFlagged,
  reasonText,
  routeDetail,
  routeLabel,
  fieldValueText,
} from '../text';

type Load =
  { kind: 'loading' } | { kind: 'failed'; code: string } | { kind: 'loaded'; view: RunView };

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

const ROUTE_STATUS = { ready: 'success', needs_review: 'warning', reject: 'error' } as const;

function FieldDetails({ field }: { field: FormFieldView }) {
  const failing = field.rule_results.filter((rule) => rule.reason_code !== null);
  return (
    <VStack gap={3} paddingBlockEnd={2}>
      {failing.length > 0 && (
        <List density="compact" listStyle="disc">
          {failing.map((rule) =>
            rule.reason_code === null ? null : (
              <ListItem
                key={rule.rule_id}
                label={<Text>{reasonText(rule.reason_code, rule.detail)}</Text>}
              />
            ),
          )}
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
        {field.confidence != null && (
          <MetadataListItem label={copy['review.confidence.label']}>
            <Text hasTabularNumbers>{field.confidence.score.toFixed(2)}</Text>
          </MetadataListItem>
        )}
        {field.confidence != null && (
          <MetadataListItem label={copy['review.threshold.label']}>
            <Text hasTabularNumbers>{field.confidence.threshold.toFixed(2)}</Text>
          </MetadataListItem>
        )}
      </MetadataList>
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

function KybForm({
  fields,
  selected,
  onSelect,
}: {
  fields: Readonly<Record<string, FormFieldView>>;
  selected: string | null;
  onSelect: (name: string) => void;
}) {
  const [open, setOpen] = useState<string[]>(() =>
    Object.entries(fields)
      .filter(([, field]) => isFlagged(field))
      .map(([name]) => name),
  );
  const change = (value: string | string[]) => {
    const next = Array.isArray(value) ? value : [value];
    const toggled =
      next.find((name) => !open.includes(name)) ?? open.find((name) => !next.includes(name));
    setOpen(next);
    if (toggled !== undefined) onSelect(toggled);
  };
  return (
    <VStack gap={2}>
      <Heading level={2}>{copy['review.form.title']}</Heading>
      <CollapsibleGroup type="multiple" value={open} onChange={change} hasDividers>
        {Object.entries(fields).map(([name, field]) => (
          <Collapsible
            key={name}
            value={name}
            trigger={<FieldTrigger name={name} field={field} isSelected={name === selected} />}
          >
            <FieldDetails field={field} />
          </Collapsible>
        ))}
      </CollapsibleGroup>
    </VStack>
  );
}

function firstSelection(fields: Readonly<Record<string, FormFieldView>>): string | null {
  const entries = Object.entries(fields);
  const flagged = entries.find(([, field]) => isFlagged(field) && field.evidence_box != null);
  const located = entries.find(([, field]) => field.evidence_box != null);
  return (flagged ?? located ?? entries[0])?.[0] ?? null;
}

function RunSummary({ view }: { view: RunView }) {
  const documents = [...new Set(view.required_documents)];
  return (
    <VStack gap={4}>
      {view.route !== null && (
        <Banner
          status={ROUTE_STATUS[view.route]}
          title={routeLabel(view.route)}
          description={routeDetail(view.route)}
        />
      )}
      {view.reasons.length > 0 && (
        <List header={<Heading level={2}>{copy['review.reasons.title']}</Heading>} listStyle="disc">
          {view.reasons.map((reason, index) => (
            <ListItem
              key={`${reason.code}-${String(index)}`}
              label={<Text>{reasonText(reason.code, reason.detail)}</Text>}
            />
          ))}
        </List>
      )}
      {documents.length > 0 && (
        <List
          header={<Heading level={2}>{copy['review.requiredDocuments.title']}</Heading>}
          listStyle="disc"
        >
          {documents.map((code) => (
            <ListItem key={code} label={documentLabel(code)} />
          ))}
        </List>
      )}
    </VStack>
  );
}

function Review({ view }: { view: RunView }) {
  const fields = view.form?.fields ?? {};
  const [selected, setSelected] = useState<string | null>(() => firstSelection(fields));
  const isNarrow = useMediaQuery('(max-width: 1024px)');
  const box = selected === null ? null : (fields[selected]?.evidence_box ?? null);
  const page = box?.page ?? 1;

  const document =
    view.pages > 0 ? <EvidenceViewer runId={view.run_id} page={page} box={box} /> : null;
  const form = (
    <VStack gap={6}>
      <RunSummary view={view} />
      {view.form !== null && <KybForm fields={fields} selected={selected} onSelect={setSelected} />}
    </VStack>
  );
  const heading = <Heading level={1}>{copy['review.title']}</Heading>;

  if (isNarrow) {
    return (
      <VStack gap={4}>
        {heading}
        {form}
        {document}
      </VStack>
    );
  }
  return (
    <Layout
      height="auto"
      content={
        <LayoutContent padding={4} label={format('review.page.label', { page: String(page) })}>
          <VStack gap={4}>
            {heading}
            {document}
          </VStack>
        </LayoutContent>
      }
      end={
        <LayoutPanel width={520} hasDivider padding={4} label={copy['review.form.title']}>
          {form}
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
  return <Review key={load.view.run_id} view={load.view} />;
}
