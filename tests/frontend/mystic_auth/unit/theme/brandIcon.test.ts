import { describe, it, expect } from 'vitest';

import { getBrandIconDataUri } from '@/theme/brandIcon';

describe('getBrandIconDataUri', () => {
  it('returns a data URI with an inline SVG', () => {
    const uri = getBrandIconDataUri('#2563eb');

    expect(uri).toMatch(/^data:image\/svg\+xml,/);
  });

  it('embeds the given fill color into the SVG', () => {
    const uri = getBrandIconDataUri('#2563eb');
    const decoded = decodeURIComponent(uri.replace('data:image/svg+xml,', ''));

    expect(decoded).toContain('fill="#2563eb"');
  });

  it('produces a data URI matching the given color, not another color', () => {
    const blueUri = getBrandIconDataUri('#2563eb');
    const greenUri = getBrandIconDataUri('#16a34a');

    expect(blueUri).toContain(encodeURIComponent('fill="#2563eb"'));
    expect(greenUri).toContain(encodeURIComponent('fill="#16a34a"'));
  });
});
