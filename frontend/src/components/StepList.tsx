import { Heading } from '@astryxdesign/core/Heading';
import { Icon } from '@astryxdesign/core/Icon';
import { List, ListItem } from '@astryxdesign/core/List';
import { Spinner } from '@astryxdesign/core/Spinner';
import { Text } from '@astryxdesign/core/Text';

import type { StepView } from '../api/client';
import { copy } from '../copy';
import { stepLabel, stepStateText } from '../text';

function StepIcon({ state }: { state: StepView['state'] }) {
  switch (state) {
    case 'done':
      return <Icon icon="success" color="success" size="sm" />;
    case 'running':
      return <Spinner size="sm" aria-label={stepStateText(state)} />;
    case 'skipped':
      return <Icon icon="chevronsRight" color="secondary" size="sm" />;
    case 'pending':
      return <Icon icon="clock" color="secondary" size="sm" />;
  }
}

/** The processing steps of a run, each with its status as text. */
export function StepList({ steps }: { steps: readonly StepView[] }) {
  return (
    <List
      density="compact"
      hasDividers
      header={<Heading level={2}>{copy['progress.title']}</Heading>}
    >
      {steps.map((step) => (
        <ListItem
          key={step.name}
          label={stepLabel(step.name)}
          startContent={<StepIcon state={step.state} />}
          endContent={<Text color="secondary">{stepStateText(step.state)}</Text>}
        />
      ))}
    </List>
  );
}
