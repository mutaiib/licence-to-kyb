import { HStack } from '@astryxdesign/core/HStack';
import { Icon } from '@astryxdesign/core/Icon';
import { Text } from '@astryxdesign/core/Text';

import type { FieldState } from '../api/client';
import { stateText } from '../text';

interface Tone {
  icon: 'success' | 'warning' | 'info' | 'check';
  color: 'success' | 'warning' | 'info';
}

/** Each status has its own icon shape and its text, so colour is never the only signal (FR-042). */
const TONES: Readonly<Record<FieldState, Tone>> = {
  passed: { icon: 'success', color: 'success' },
  approved: { icon: 'check', color: 'success' },
  corrected: { icon: 'check', color: 'success' },
  overridden: { icon: 'info', color: 'info' },
  flagged: { icon: 'warning', color: 'warning' },
  needs_examination: { icon: 'warning', color: 'warning' },
};

/** A field status: an icon plus the status text. */
export function StatusLabel({ state }: { state: FieldState }) {
  const tone = TONES[state];
  return (
    <HStack gap={1} vAlign="center">
      <Icon icon={tone.icon} color={tone.color} size="sm" />
      <Text type="supporting" weight="medium">
        {stateText(state)}
      </Text>
    </HStack>
  );
}
