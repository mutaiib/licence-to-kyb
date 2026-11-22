// How one run reached its result (US5, FR-032): every step with its calls.
import { Banner } from '@astryxdesign/core/Banner';
import { Heading } from '@astryxdesign/core/Heading';
import { Link } from '@astryxdesign/core/Link';
import { Spinner } from '@astryxdesign/core/Spinner';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { useEffect, useState } from 'react';

import { getTrace, type SpanView } from '../api/client';
import { SpanList } from '../components/SpanTree';
import { copy } from '../copy';
import { runPath, useLinkHandler } from '../router';
import { errorText } from '../text';

type Load =
  { kind: 'loading' } | { kind: 'failed'; code: string } | { kind: 'loaded'; spans: SpanView[] };

export function TracePage({ runId }: { runId: string }) {
  const [load, setLoad] = useState<Load>({ kind: 'loading' });
  const back = useLinkHandler(runPath(runId));
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
      <Heading level={1}>{copy['trace.title']}</Heading>
      <Link href={runPath(runId)} onClick={back}>
        {copy['trace.back']}
      </Link>
      <Text color="secondary">{copy['trace.masked']}</Text>
      {load.kind === 'loading' && <Spinner size="lg" aria-label={copy['app.loading']} />}
      {load.kind === 'failed' && (
        <VStack role="alert">
          <Banner status="error" title={errorText(load.code)} />
        </VStack>
      )}
      {load.kind === 'loaded' && <SpanList spans={load.spans} />}
    </VStack>
  );
}
