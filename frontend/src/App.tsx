import { AppShell } from '@astryxdesign/core/AppShell';
import { Theme } from '@astryxdesign/core/theme';
import { TopNav, TopNavHeading } from '@astryxdesign/core/TopNav';

import { defaultThemeSlug, themes } from './astryx-themes';
import { copy } from './copy';

/** The app frame: a top bar with the product name, and the main content area. */
export function App() {
  return (
    <Theme theme={themes[defaultThemeSlug]}>
      <AppShell
        contentPadding={4}
        topNav={<TopNav heading={<TopNavHeading heading={copy.app.title} />} />}
      >
        {/* Feature pages render here. */}
        {null}
      </AppShell>
    </Theme>
  );
}
