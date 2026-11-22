import react from '@vitejs/plugin-react';
import type { Plugin } from 'vite';
import { defineConfig } from 'vitest/config';

import { copy } from './src/copy.ts';

/** Fills the page title in index.html from copy.ts, so the title text has one source. */
function htmlTitleFromCopy(): Plugin {
  return {
    name: 'html-title-from-copy',
    transformIndexHtml: (html) => html.replace('%APP_TITLE%', copy.app.title),
  };
}

export default defineConfig({
  plugins: [react(), htmlTitleFromCopy()],
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.{ts,tsx}'],
    setupFiles: ['./tests/setup.ts'],
  },
});
