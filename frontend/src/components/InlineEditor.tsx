// A text input with Save and Cancel. Used to correct a value, and to write the reason for
// an override, a rejection or a reopening. Save stays disabled until the text is not empty.
import { Button } from '@astryxdesign/core/Button';
import { HStack } from '@astryxdesign/core/HStack';
import { TextInput } from '@astryxdesign/core/TextInput';
import { VStack } from '@astryxdesign/core/VStack';
import { useState } from 'react';

import { copy } from '../copy';

/** The longest value or reason the server accepts (api/schemas.py). */
const MAX_LENGTH = 500;

export function InlineEditor({
  label,
  initial = '',
  onSave,
  onCancel,
}: {
  label: string;
  initial?: string;
  onSave: (text: string) => void;
  onCancel: () => void;
}) {
  const [text, setText] = useState(initial);
  const isEmpty = text.trim() === '';
  const save = () => {
    if (!isEmpty) onSave(text.trim());
  };
  return (
    <VStack gap={2}>
      <TextInput
        label={label}
        value={text}
        onChange={(next) => {
          setText(next.slice(0, MAX_LENGTH));
        }}
        onEnter={save}
        hasAutoFocus
      />
      <HStack gap={2}>
        <Button label={copy['review.save']} variant="primary" isDisabled={isEmpty} onClick={save} />
        <Button label={copy['review.cancel']} variant="ghost" onClick={onCancel} />
      </HStack>
    </VStack>
  );
}
