import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { App } from '../src/App';
import { copy } from '../src/copy';

describe('app shell', () => {
  it('shows the product name in the top banner', () => {
    render(<App />);

    const banner = screen.getByRole('banner');

    expect(within(banner).getByText(copy['app.title'])).toBeVisible();
  });

  it('gives the page one main content area', () => {
    render(<App />);

    expect(screen.getAllByRole('main')).toHaveLength(1);
  });
});
