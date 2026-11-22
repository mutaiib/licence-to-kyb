// Scaffolded from `astryx template login-card`: the centred column and the card are kept.
// The provider buttons, sign-up link and terms are removed: reviewers have one account type.
import { Banner } from '@astryxdesign/core/Banner';
import { Button } from '@astryxdesign/core/Button';
import { Card } from '@astryxdesign/core/Card';
import { Center } from '@astryxdesign/core/Center';
import { Heading } from '@astryxdesign/core/Heading';
import { TextInput } from '@astryxdesign/core/TextInput';
import { VStack } from '@astryxdesign/core/VStack';
import { useState, type SyntheticEvent } from 'react';

import { signIn } from '../api/client';
import { copy } from '../copy';
import { errorText } from '../text';

export function SignInPage({
  notice,
  onSignedIn,
}: {
  /** An error code to show before the reviewer signs in, for example `session_expired`. */
  notice: string | null;
  onSignedIn: () => void;
}) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const shownCode = errorCode ?? notice;

  const submit = async (event: SyntheticEvent) => {
    event.preventDefault();
    setIsLoading(true);
    const result = await signIn(username, password);
    setIsLoading(false);
    if (result.ok) {
      onSignedIn();
    } else {
      setErrorCode(result.code);
    }
  };

  return (
    <Center axis="both" padding={6}>
      <VStack gap={4} hAlign="stretch" width="100%" maxWidth={400}>
        <Card padding={8} width="100%">
          <VStack
            as="form"
            gap={4}
            hAlign="stretch"
            onSubmit={(event: SyntheticEvent) => {
              void submit(event);
            }}
          >
            <Heading level={1}>{copy['signin.title']}</Heading>
            {shownCode !== null && (
              <VStack role="alert">
                <Banner status="error" title={errorText(shownCode)} />
              </VStack>
            )}
            <TextInput
              label={copy['signin.username.label']}
              value={username}
              onChange={setUsername}
              autoComplete="username"
              size="lg"
            />
            <TextInput
              label={copy['signin.password.label']}
              type="password"
              value={password}
              onChange={setPassword}
              autoComplete="current-password"
              size="lg"
            />
            <Button
              label={copy['signin.button']}
              type="submit"
              variant="primary"
              size="lg"
              isLoading={isLoading}
            />
          </VStack>
        </Card>
      </VStack>
    </Center>
  );
}
