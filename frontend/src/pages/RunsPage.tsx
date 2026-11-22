// Every run, newest first, with today's rates above (US5, FR-032).
import { Banner } from '@astryxdesign/core/Banner';
import { Heading } from '@astryxdesign/core/Heading';
import { useMediaQuery } from '@astryxdesign/core/hooks';
import { Link } from '@astryxdesign/core/Link';
import { List, ListItem } from '@astryxdesign/core/List';
import { MetadataList, MetadataListItem } from '@astryxdesign/core/MetadataList';
import { Spinner } from '@astryxdesign/core/Spinner';
import { Table } from '@astryxdesign/core/Table';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { useEffect, useState } from 'react';

import { getSummary, listRuns, type RunListItem, type Summary } from '../api/client';
import { copy, format } from '../copy';
import { runPath, tracePath, useLinkHandler } from '../router';
import { errorText, runStatusText, shortTime } from '../text';

const percent = (rate: number) => format('unit.percent', { value: String(Math.round(rate * 100)) });
const money = (usd: number) => format('unit.usd', { value: usd.toFixed(2) });
const seconds = (ms: number) => format('unit.seconds', { value: (ms / 1000).toFixed(1) });

function InAppLink({
  path,
  label,
  children,
}: {
  path: string;
  /** The accessible name, when the visible text alone does not say where the link goes. */
  label?: string;
  children: string;
}) {
  return (
    <Link href={path} onClick={useLinkHandler(path)} label={label} hasUnderline>
      {children}
    </Link>
  );
}

function DailySummary({ summary }: { summary: Summary }) {
  return (
    <VStack gap={2} role="region" aria-label={copy['runs.summary.title']}>
      <Heading level={2}>{copy['runs.summary.title']}</Heading>
      <MetadataList>
        <MetadataListItem label={copy['runs.summary.refusals']}>
          <Text hasTabularNumbers>{percent(summary.refusal_rate)}</Text>
        </MetadataListItem>
        <MetadataListItem label={copy['runs.summary.fallbacks']}>
          <Text hasTabularNumbers>{percent(summary.fallback_rate)}</Text>
        </MetadataListItem>
        <MetadataListItem label={copy['runs.summary.review']}>
          <Text hasTabularNumbers>{percent(summary.review_rate)}</Text>
        </MetadataListItem>
        <MetadataListItem label={copy['runs.summary.cost']}>
          <Text hasTabularNumbers>{money(summary.cost_usd)}</Text>
        </MetadataListItem>
        <MetadataListItem label={copy['runs.summary.budget']}>
          <Text hasTabularNumbers>{summary.budget_tokens_remaining.toLocaleString('en')}</Text>
        </MetadataListItem>
      </MetadataList>
    </VStack>
  );
}

const COLUMNS = [
  {
    key: 'created_at',
    header: copy['runs.column.date'],
    renderCell: (run: RunListItem) => <Text>{shortTime(run.created_at)}</Text>,
  },
  {
    key: 'applicant_name',
    header: copy['runs.column.business'],
    renderCell: (run: RunListItem) => (
      <InAppLink path={runPath(run.run_id)}>{run.applicant_name}</InAppLink>
    ),
  },
  {
    key: 'status',
    header: copy['runs.column.status'],
    renderCell: (run: RunListItem) => <Text>{runStatusText(run.status)}</Text>,
  },
  {
    key: 'cost_usd',
    header: copy['runs.column.cost'],
    align: 'end' as const,
    renderCell: (run: RunListItem) => <Text hasTabularNumbers>{money(run.cost_usd)}</Text>,
  },
  {
    key: 'duration_ms',
    header: copy['runs.column.duration'],
    align: 'end' as const,
    renderCell: (run: RunListItem) => <Text hasTabularNumbers>{seconds(run.duration_ms)}</Text>,
  },
  {
    key: 'trace',
    header: copy['runs.trace.link'],
    renderCell: (run: RunListItem) => (
      <InAppLink
        path={tracePath(run.run_id)}
        label={format('runs.trace.linkFor', { name: run.applicant_name })}
      >
        {copy['runs.trace.link']}
      </InAppLink>
    ),
  },
];

/** On a phone: one row per run, the business name as the link, the details below it. */
function RunRows({ runs }: { runs: readonly RunListItem[] }) {
  return (
    <List>
      {runs.map((run) => (
        <RunRow key={run.run_id} run={run} />
      ))}
    </List>
  );
}

function RunRow({ run }: { run: RunListItem }) {
  const path = runPath(run.run_id);
  const details = [runStatusText(run.status), shortTime(run.created_at), money(run.cost_usd)];
  return (
    <ListItem
      href={path}
      onClick={useLinkHandler(path)}
      label={<Text weight="semibold">{run.applicant_name}</Text>}
      description={<Text color="secondary">{details.join(' · ')}</Text>}
    />
  );
}

function EmptyRuns() {
  return (
    <VStack gap={2}>
      <Text>{copy['runs.empty']}</Text>
      <InAppLink path="/">{copy['runs.empty.action']}</InAppLink>
    </VStack>
  );
}

export function RunsPage() {
  const isNarrow = useMediaQuery('(max-width: 768px)');
  const [runs, setRuns] = useState<RunListItem[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  useEffect(() => {
    void listRuns().then((result) => {
      // A failed load is not an empty list: say that the list could not load.
      if (result.ok) setRuns(result.data.runs);
      else setLoadError(result.code);
    });
    void getSummary().then((result) => {
      if (result.ok) setSummary(result.data);
    });
  }, []);

  return (
    <VStack gap={6}>
      <Heading level={1}>{copy['runs.title']}</Heading>
      {summary !== null && <DailySummary summary={summary} />}
      {loadError !== null && (
        <VStack role="alert">
          <Banner status="error" title={errorText(loadError)} />
        </VStack>
      )}
      {runs === null && loadError === null && (
        <Spinner size="lg" aria-label={copy['app.loading']} />
      )}
      {runs !== null && runs.length === 0 && <EmptyRuns />}
      {runs !== null && runs.length > 0 && isNarrow && <RunRows runs={runs} />}
      {runs !== null && runs.length > 0 && !isNarrow && (
        <Table data={runs} columns={COLUMNS} idKey="run_id" />
      )}
    </VStack>
  );
}
