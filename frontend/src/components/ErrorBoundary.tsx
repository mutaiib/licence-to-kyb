// The last safety net: if a part of the page throws while it renders, show a message with the
// action to take instead of a blank page. React offers this only as a class component.
import { Banner } from '@astryxdesign/core/Banner';
import { VStack } from '@astryxdesign/core/VStack';
import { Component, type ReactNode } from 'react';

import { copy } from '../copy';

export class ErrorBoundary extends Component<{ children: ReactNode }, { hasFailed: boolean }> {
  override state = { hasFailed: false };

  static getDerivedStateFromError(): { hasFailed: boolean } {
    return { hasFailed: true };
  }

  override render(): ReactNode {
    if (this.state.hasFailed) {
      return (
        <VStack role="alert">
          <Banner status="error" title={copy['app.crashed']} />
        </VStack>
      );
    }
    return this.props.children;
  }
}
