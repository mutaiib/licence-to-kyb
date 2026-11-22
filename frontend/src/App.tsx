import { AppShell } from '@astryxdesign/core/AppShell';
import { Button } from '@astryxdesign/core/Button';
import { InfoTip } from '@astryxdesign/core/InfoTip';
import { Spinner } from '@astryxdesign/core/Spinner';
import { Theme } from '@astryxdesign/core/theme';
import { TopNav, TopNavHeading, TopNavItem } from '@astryxdesign/core/TopNav';
import { useCallback, useEffect, useState } from 'react';

import { listRuns, onSessionExpired, signOut } from './api/client';
import { defaultThemeSlug, themes } from './astryx-themes';
import { copy } from './copy';
import { ReviewPage } from './pages/ReviewPage';
import { RunsPage } from './pages/RunsPage';
import { TracePage } from './pages/TracePage';
import { SignInPage } from './pages/SignInPage';
import { UploadPage } from './pages/UploadPage';
import { navigate, parsePath, useLinkHandler, usePathname } from './router';

type Session =
  { kind: 'checking' } | { kind: 'signedIn' } | { kind: 'signedOut'; notice: string | null };

/** Asks the API once whether the session cookie is valid, and follows later session expiry. */
function useSession() {
  const [session, setSession] = useState<Session>({ kind: 'checking' });
  useEffect(() => {
    let isCancelled = false;
    void listRuns().then((result) => {
      if (!isCancelled) {
        setSession(result.ok ? { kind: 'signedIn' } : { kind: 'signedOut', notice: null });
      }
    });
    const unsubscribe = onSessionExpired(() => {
      setSession((current) =>
        current.kind === 'signedIn' ? { kind: 'signedOut', notice: 'session_expired' } : current,
      );
    });
    return () => {
      isCancelled = true;
      unsubscribe();
    };
  }, []);
  return [session, setSession] as const;
}

function NavItems({ pathname }: { pathname: string }) {
  const page = parsePath(pathname).name;
  return (
    <>
      <TopNavItem
        label={copy['nav.upload']}
        href="/"
        onClick={useLinkHandler('/')}
        isSelected={page === 'upload'}
      />
      <TopNavItem
        label={copy['nav.runs']}
        href="/runs"
        onClick={useLinkHandler('/runs')}
        isSelected={page === 'runs' || page === 'trace'}
      />
    </>
  );
}

/** The app frame: a top bar with the product name, and the main content area. */
export function App() {
  const [session, setSession] = useSession();
  const pathname = usePathname();
  const page = parsePath(pathname);

  const handleSignOut = useCallback(async () => {
    await signOut();
    setSession({ kind: 'signedOut', notice: null });
    navigate('/');
  }, [setSession]);

  const isSignedIn = session.kind === 'signedIn';
  let content;
  if (session.kind === 'checking') {
    content = <Spinner size="lg" aria-label={copy['app.loading']} />;
  } else if (session.kind === 'signedOut') {
    content = (
      <SignInPage
        notice={session.notice}
        onSignedIn={() => {
          setSession({ kind: 'signedIn' });
        }}
      />
    );
  } else if (page.name === 'review') {
    content = <ReviewPage runId={page.runId} />;
  } else if (page.name === 'runs') {
    content = <RunsPage />;
  } else if (page.name === 'trace') {
    content = <TracePage runId={page.runId} />;
  } else {
    content = <UploadPage />;
  }

  return (
    <Theme theme={themes[defaultThemeSlug]}>
      <AppShell
        contentPadding={4}
        topNav={
          <TopNav
            heading={
              <TopNavHeading
                heading={copy['app.title']}
                headerEndContent={
                  <InfoTip content={copy['glossary.kyb']} label={copy['glossary.label']} />
                }
              />
            }
            startContent={isSignedIn ? <NavItems pathname={pathname} /> : undefined}
            endContent={
              isSignedIn ? (
                <Button
                  label={copy['signout.button']}
                  variant="ghost"
                  clickAction={handleSignOut}
                />
              ) : undefined
            }
          />
        }
      >
        {content}
      </AppShell>
    </Theme>
  );
}
