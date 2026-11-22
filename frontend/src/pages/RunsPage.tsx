// Every run, newest first, with today's rates above (US5, FR-032).
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
import { copy } from '../copy';
import { runPath, tracePath, useLinkHandler } from '../router';
import { runStatusText, shortTime } from '../text';

const percent = (rate: number) => `${String(Math.round(rate * 100))}%`;

function InAppLink({ path, children }: { path: string; children: string }) {
  return (
    <Link href={path} onClick={useLinkHandler(path)} hasUnderline>
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
          <Text hasTabularNumbers>{`$${summary.cost_usd.toFixed(2)}`}</Text>
        </MetadataListItem>
        <MetadataListItem label={copy['runs.summary.budget']}>
          <Text hasTabularNumbers>{summary.budget_tokens_remaining.toLocaleString('en')}</Text>
        </MetadataListItem>
      </MetadataList>
    </VStack>
  );
}

const money = (usd: number) => `$${usd.toFixed(2)}`;

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
    renderCell: (run: RunListItem) => (
      <Text hasTabularNumbers>{(run.duration_ms / 1000).toFixed(1) + ' s'}</Text>
    ),
  },
  {
    key: 'trace',
    header: copy['runs.trace.link'],
    renderCell: (run: RunListItem) => (
      <InAppLink path={tracePath(run.run_id)}>{copy['runs.trace.link']}</InAppLink>
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
  const [summary, setSummary] = useState<Summary | null>(null);
  useEffect(() => {
    void listRuns().then((result) => {
      setRuns(result.ok ? result.data.runs : []);
    });
    void getSummary().then((result) => {
      if (result.ok) setSummary(result.data);
    });
  }, []);

  return (
    <VStack gap={6}>
      <Heading level={1}>{copy['runs.title']}</Heading>
      {summary !== null && <DailySummary summary={summary} />}
      {runs === null && <Spinner size="lg" aria-label={copy['app.loading']} />}
      {runs !== null && runs.length === 0 && <EmptyRuns />}
      {runs !== null && runs.length > 0 && isNarrow && <RunRows runs={runs} />}
      {runs !== null && runs.length > 0 && !isNarrow && (
        <Table data={runs} columns={COLUMNS} idKey="run_id" />
      )}
    </VStack>
  );
}
