// The trace of one run as a tree: each step, with its model calls and tool calls under it.
// The page shows only non-personal values: names, models, tokens, time, cost and outcome.
import { List, ListItem } from '@astryxdesign/core/List';
import { Text } from '@astryxdesign/core/Text';

import type { SpanView } from '../api/client';
import { format } from '../copy';
import { stepLabel } from '../text';

function children(spans: readonly SpanView[], parentId: string | null): SpanView[] {
  return spans.filter((span) => span.parent_id === parentId);
}

function details(span: SpanView): string[] {
  const parts = [`${String(span.latency_ms)} ms`];
  if (span.kind === 'model_call') {
    parts.push(
      span.model ?? '',
      format('trace.tokens.value', {
        input: String(span.input_tokens),
        output: String(span.output_tokens),
      }),
      `$${span.cost_usd.toFixed(4)}`,
    );
  }
  return parts.filter((part) => part !== '');
}

function SpanItem({ span, spans }: { span: SpanView; spans: readonly SpanView[] }) {
  const name = span.kind === 'step' ? stepLabel(span.name) : span.name;
  const nested = children(spans, span.span_id);
  return (
    <ListItem
      aria-label={name}
      label={<Text weight={span.kind === 'step' ? 'semibold' : 'normal'}>{name}</Text>}
      description={
        <>
          <Text color="secondary" hasTabularNumbers>
            {details(span).join(' · ')}
          </Text>
          {span.summary !== 'ok' && <Text color="secondary">{span.summary}</Text>}
          {nested.length > 0 && <SpanList spans={spans} parentId={span.span_id} />}
        </>
      }
    />
  );
}

export function SpanList({
  spans,
  parentId = null,
}: {
  spans: readonly SpanView[];
  parentId?: string | null;
}) {
  return (
    <List density="compact">
      {children(spans, parentId).map((span) => (
        <SpanItem key={span.span_id} span={span} spans={spans} />
      ))}
    </List>
  );
}
