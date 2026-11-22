// How one run reached its result (US5, FR-032): every step with its calls.
import { Banner } from '@astryxdesign/core/Banner';
import { Heading } from '@astryxdesign/core/Heading';
import { Link } from '@astryxdesign/core/Link';
import { Spinner } from '@astryxdesign/core/Spinner';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { useEffect, useState } from 'react';

import { getRun, getTrace, type SpanView } from '../api/client';
import { SpanList } from '../components/SpanTree';
import { copy, format } from '../copy';
import { runPath, useLinkHandler } from '../router';
import { errorText } from '../text';

type Load =
  { kind: 'loading' } | { kind: 'failed'; code: string } | { kind: 'loaded'; spans: SpanView[] };

/** Time of all steps, cost and number of model calls: what a trace is read for. */
function totals(spans: readonly SpanView[]): string {
  const steps = spans.filter((span) => span.kind === 'step');
  const calls = spans.filter((span) => span.kind === 'model_call');
  const seconds = steps.reduce((sum, span) => sum + span.latency_ms, 0) / 1000;
  const cost = calls.reduce((sum, span) => sum + span.cost_usd, 0);
  return format('trace.totals', {
    seconds: seconds.toFixed(1),
    cost: cost.toFixed(4),
    calls: String(calls.length),
  });
}

export function TracePage({ runId }: { runId: string }) {
  const [load, setLoad] = useState<Load>({ kind: 'loading' });
  const back = useLinkHandler(runPath(runId));
  const [business, setBusiness] = useState<string | null>(null);
  useEffect(() => {
    void getRun(runId).then((result) => {
      if (result.ok) setBusiness(result.data.applicant_name);
    });
  }, [runId]);
  useEffect(() => {
    void getTrace(runId).then((result) => {
      setLoad(
        result.ok
          ? { kind: 'loaded', spans: result.data.spans }
          : { kind: 'failed', code: result.code },
      );
    });
  }, [runId]);

  return (
    <VStack gap={4}>
      <VStack gap={1}>
        <Heading level={1}>{business ?? copy['trace.title']}</Heading>
        {business !== null && <Text color="secondary">{copy['trace.title']}</Text>}
      </VStack>
      <Link href={runPath(runId)} onClick={back} hasUnderline>
        {copy['trace.back']}
      </Link>
      <Text color="secondary">{copy['trace.masked']}</Text>
      {load.kind === 'loading' && <Spinner size="lg" aria-label={copy['app.loading']} />}
      {load.kind === 'failed' && (
        <VStack role="alert">
          <Banner status="error" title={errorText(load.code)} />
        </VStack>
      )}
      {load.kind === 'loaded' && <Text weight="semibold">{totals(load.spans)}</Text>}
      {load.kind === 'loaded' && <SpanList spans={load.spans} />}
    </VStack>
  );
}
