// The resolver's proposal for one field (US4): its explanation, labelled as model output,
// and whether the new value was used. A value is used only when its checks pass (FR-016).
import { Banner } from '@astryxdesign/core/Banner';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';

import { copy } from '../copy';

export function ProposalDetails({ rationale, accepted }: { rationale: string; accepted: boolean }) {
  return (
    <VStack gap={1}>
      <Text weight="semibold">{copy['review.rationale.label']}</Text>
      <Text color="secondary">{copy['review.rationale.note']}</Text>
      <Text>{rationale}</Text>
      <Banner
        status={accepted ? 'info' : 'warning'}
        title={copy[accepted ? 'proposal.accepted' : 'proposal.refused']}
      />
    </VStack>
  );
}
