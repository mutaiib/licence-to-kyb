// Every run, newest first, with today's rates above (US5, FR-032).
import { Heading } from '@astryxdesign/core/Heading';
import { Link } from '@astryxdesign/core/Link';
import { MetadataList, MetadataListItem } from '@astryxdesign/core/MetadataList';
import { Spinner } from '@astryxdesign/core/Spinner';
import { Table } from '@astryxdesign/core/Table';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { useEffect, useState } from 'react';

import { getSummary, listRuns, type RunListItem, type Summary } from '../api/client';
import { copy } from '../copy';
import { runPath, tracePath, useLinkHandler } from '../router';
import { routeLabel, runStatusText } from '../text';

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

const COLUMNS = [
  {
    key: 'created_at',
    header: copy['runs.column.date'],
    renderCell: (run: RunListItem) => <Text>{run.created_at.slice(0, 16).replace('T', ' ')}</Text>,
  },
  {
    key: 'applicant_name',
    header: copy['runs.column.business'],
    renderCell: (run: RunListItem) => (
      <InAppLink path={runPath(run.run_id)}>{run.applicant_name}</InAppLink>
    ),
  },
  {
    key: 'route',
    header: copy['runs.column.route'],
    renderCell: (run: RunListItem) => (
      <Text>{run.route === null ? '' : routeLabel(run.route)}</Text>
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
    renderCell: (run: RunListItem) => (
      <Text hasTabularNumbers>{`$${run.cost_usd.toFixed(2)}`}</Text>
    ),
  },
  {
    key: 'duration_ms',
    header: copy['runs.column.duration'],
    align: 'end' as const,
    renderCell: (run: RunListItem) => (
      <Text hasTabularNumbers>{`${(run.duration_ms / 1000).toFixed(1)} s`}</Text>
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

export function RunsPage() {
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
      {runs !== null && runs.length === 0 && <Text>{copy['runs.empty']}</Text>}
      {runs !== null && runs.length > 0 && <Table data={runs} columns={COLUMNS} idKey="run_id" />}
    </VStack>
  );
}
