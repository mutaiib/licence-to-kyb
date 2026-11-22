/**
 * A small history router. The app has two pages, so a router dependency is not necessary.
 * nginx serves index.html for every path (nginx.conf), so deep links work.
 */
import { useCallback, useSyncExternalStore, type MouseEvent } from 'react';

export type Page = { name: 'upload' } | { name: 'review'; runId: string };

const NAVIGATE_EVENT = 'app:navigate';

export function parsePath(pathname: string): Page {
  const match = /^\/runs\/([^/]+)\/?$/.exec(pathname);
  if (match?.[1] !== undefined) {
    return { name: 'review', runId: decodeURIComponent(match[1]) };
  }
  return { name: 'upload' };
}

export function runPath(runId: string): string {
  return `/runs/${encodeURIComponent(runId)}`;
}

export function navigate(path: string): void {
  if (window.location.pathname !== path) {
    window.history.pushState({}, '', path);
  }
  window.dispatchEvent(new Event(NAVIGATE_EVENT));
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener('popstate', onChange);
  window.addEventListener(NAVIGATE_EVENT, onChange);
  return () => {
    window.removeEventListener('popstate', onChange);
    window.removeEventListener(NAVIGATE_EVENT, onChange);
  };
}

/** The current path. Re-renders on back, forward and `navigate`. */
export function usePathname(): string {
  return useSyncExternalStore(subscribe, () => window.location.pathname);
}

/**
 * A click handler for an in-app link: a plain click navigates without a page load. A click with a
 * modifier key keeps the browser behaviour (for example, open in a new tab).
 */
export function useLinkHandler(path: string): (event: MouseEvent) => void {
  return useCallback(
    (event: MouseEvent) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return;
      }
      event.preventDefault();
      navigate(path);
    },
    [path],
  );
}
