// Scaffolded from `astryx template contact-form`: a single 640 column with the fields over one
// submit button. The progress list (List/ListItem) appears below the form after the upload.
import { Banner } from '@astryxdesign/core/Banner';
import { Button } from '@astryxdesign/core/Button';
import { FileInput } from '@astryxdesign/core/FileInput';
import { Heading } from '@astryxdesign/core/Heading';
import { Link } from '@astryxdesign/core/Link';
import { Section } from '@astryxdesign/core/Section';
import { Text } from '@astryxdesign/core/Text';
import { TextInput } from '@astryxdesign/core/TextInput';
import { VStack } from '@astryxdesign/core/VStack';
import { useEffect, useState, type SyntheticEvent } from 'react';

import { createRun, getRun, type ReasonCode, type RunView } from '../api/client';
import { StepList } from '../components/StepList';
import { copy } from '../copy';
import { runPath, useLinkHandler } from '../router';
import { errorText, reasonText } from '../text';

/** The limits in docs/ui-copy.md (`upload.instruction`) and contracts/http-api.md. */
export const MAX_FILE_BYTES = 10 * 1024 * 1024;
const ACCEPT = '.pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png';
const ACCEPTED_TYPES = new Set(['application/pdf', 'image/jpeg', 'image/png']);
const ACCEPTED_EXTENSIONS = /\.(pdf|jpe?g|png)$/i;
export const POLL_MS = 1000;
const ACTIVE = new Set<RunView['status']>(['received', 'processing']);

/** A reason the browser can see before the upload: the file type or the size. */
function checkFile(file: File): ReasonCode | null {
  if (!ACCEPTED_TYPES.has(file.type) && !ACCEPTED_EXTENSIONS.test(file.name)) {
    return 'invalid_type';
  }
  return file.size > MAX_FILE_BYTES ? 'too_large' : null;
}

type Outcome =
  | { kind: 'none' }
  | { kind: 'refused'; reasonCode: ReasonCode }
  | { kind: 'failed'; code: string }
  | { kind: 'duplicate'; runId: string }
  | { kind: 'processing'; runId: string };

function RunLink({ runId }: { runId: string }) {
  const path = runPath(runId);
  return (
    <Link href={path} onClick={useLinkHandler(path)} isStandalone>
      {copy['upload.openRun']}
    </Link>
  );
}

/** Polls the run every second while it is processing. */
function useRunProgress(runId: string | null): RunView | null {
  const [view, setView] = useState<RunView | null>(null);
  useEffect(() => {
    if (runId === null) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let isCancelled = false;
    const poll = async () => {
      const result = await getRun(runId);
      if (isCancelled) return;
      if (result.ok) {
        setView(result.data);
        if (!ACTIVE.has(result.data.status)) return;
      } else if (result.code !== 'network') {
        return;
      }
      timer = setTimeout(() => void poll(), POLL_MS);
    };
    void poll();
    return () => {
      isCancelled = true;
      clearTimeout(timer);
    };
  }, [runId]);
  return runId === null || view?.run_id !== runId ? null : view;
}

export function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [fileReason, setFileReason] = useState<ReasonCode | null>(null);
  const [applicantName, setApplicantName] = useState('');
  const [outcome, setOutcome] = useState<Outcome>({ kind: 'none' });
  const [isUploading, setIsUploading] = useState(false);
  const progress = useRunProgress(outcome.kind === 'processing' ? outcome.runId : null);
  const isFinished = progress !== null && !ACTIVE.has(progress.status);
  const canSubmit = file !== null && fileReason === null && applicantName.trim() !== '';

  const chooseFile = (files: File | File[] | null) => {
    const chosen = Array.isArray(files) ? (files[0] ?? null) : files;
    setFile(chosen);
    setFileReason(chosen === null ? null : checkFile(chosen));
    setOutcome({ kind: 'none' });
  };

  const submit = async (event: SyntheticEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    setIsUploading(true);
    const result = await createRun(file, applicantName.trim());
    setIsUploading(false);
    if (result.kind === 'refused') {
      setOutcome({ kind: 'refused', reasonCode: result.reasonCode });
    } else if (result.kind === 'failed') {
      setOutcome({ kind: 'failed', code: result.code });
    } else if (result.run.duplicate) {
      setOutcome({ kind: 'duplicate', runId: result.run.run_id });
    } else {
      setOutcome({ kind: 'processing', runId: result.run.run_id });
    }
  };

  return (
    <VStack hAlign="center" width="100%">
      <Section width="100%" maxWidth={640} padding={6} variant="section">
        <VStack gap={6}>
          <VStack
            as="form"
            gap={4}
            onSubmit={(event: SyntheticEvent) => {
              void submit(event);
            }}
          >
            <Heading level={1}>{copy['upload.title']}</Heading>
            <Text color="secondary">{copy['upload.intro']}</Text>
            <FileInput
              label={copy['upload.file.label']}
              placeholder={copy['upload.file.placeholder']}
              description={copy['upload.instruction']}
              labelTooltip={copy['glossary.fileTypes']}
              accept={ACCEPT}
              value={file}
              onChange={chooseFile}
              status={
                fileReason === null ? undefined : { type: 'error', message: reasonText(fileReason) }
              }
              statusVariant="detached"
            />
            <TextInput
              label={copy['upload.applicantName.label']}
              description={copy['upload.applicantName.help']}
              value={applicantName}
              onChange={setApplicantName}
              autoComplete="organization"
            />
            <Button
              label={copy['upload.button']}
              type="submit"
              variant="primary"
              isLoading={isUploading}
              isDisabled={!canSubmit}
            />
          </VStack>

          {outcome.kind === 'refused' && (
            <VStack role="alert">
              <Banner status="error" title={reasonText(outcome.reasonCode)} />
            </VStack>
          )}
          {outcome.kind === 'failed' && (
            <VStack role="alert">
              <Banner status="error" title={errorText(outcome.code)} />
            </VStack>
          )}
          {outcome.kind === 'duplicate' && (
            <Banner
              status="info"
              title={copy['upload.duplicate']}
              endContent={<RunLink runId={outcome.runId} />}
            />
          )}
          {outcome.kind === 'processing' && progress !== null && (
            <VStack gap={3} aria-live="polite">
              <StepList steps={progress.steps} />
              {isFinished && <RunLink runId={outcome.runId} />}
            </VStack>
          )}
        </VStack>
      </Section>
    </VStack>
  );
}
