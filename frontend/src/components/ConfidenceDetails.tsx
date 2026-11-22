// How sure the system is of a read value (US3, FR-019): the score, the score the field
// needs, and in words each piece of weak evidence behind a low score.
import { List, ListItem } from '@astryxdesign/core/List';
import { MetadataList, MetadataListItem } from '@astryxdesign/core/MetadataList';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';

import type { FormFieldView } from '../api/client';
import { copy, type CopyKey } from '../copy';

type Confidence = NonNullable<FormFieldView['confidence']>;

/** A signal below this value is named as weak evidence. */
const WEAK_SIGNAL = 0.8;

const SIGNAL_TEXT: Readonly<Record<string, CopyKey>> = {
  agreement: 'signal.agreement',
  grounding: 'signal.grounding',
  rules: 'signal.rules',
  ocr: 'signal.ocr',
  corroboration: 'signal.corroboration',
  self_rating: 'signal.self_rating',
};

export function ConfidenceDetails({ confidence }: { confidence: Confidence }) {
  const weak: CopyKey[] = [];
  for (const [name, value] of Object.entries(confidence.signals)) {
    const key = SIGNAL_TEXT[name];
    if (key !== undefined && value < WEAK_SIGNAL) weak.push(key);
  }
  return (
    <VStack gap={2}>
      <MetadataList>
        <MetadataListItem label={copy['review.confidence.label']}>
          <Text hasTabularNumbers>{confidence.score.toFixed(2)}</Text>
        </MetadataListItem>
        {confidence.threshold != null && (
          <MetadataListItem label={copy['review.threshold.label']}>
            <Text hasTabularNumbers>{confidence.threshold.toFixed(2)}</Text>
          </MetadataListItem>
        )}
      </MetadataList>
      {weak.length > 0 && (
        <List
          header={<Text weight="semibold">{copy['confidence.weak.title']}</Text>}
          listStyle="disc"
          density="compact"
        >
          {weak.map((key) => (
            <ListItem key={key} label={<Text>{copy[key]}</Text>} />
          ))}
        </List>
      )}
    </VStack>
  );
}
