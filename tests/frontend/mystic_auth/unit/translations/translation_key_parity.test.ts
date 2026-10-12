// A missing translation key silently falls back to the raw i18next key in the UI
// instead of failing visibly, so this checks every namespace in translations.ts
// and asserts all languages expose the same set of (nested) keys as en.
import { describe, it, expect } from 'vitest';

import { NAMESPACES, SUPPORTED_LANGUAGES } from '@/translations/translations';

function flattenKeys(value: unknown, prefix = ''): string[] {
  if (typeof value !== 'object' || value === null) return [prefix];
  return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) =>
    flattenKeys(child, prefix ? `${prefix}.${key}` : key)
  );
}

describe('translation key parity', () => {
  it.each(NAMESPACES)('every language has the same keys as en for the "%s" namespace', async (namespace) => {
    const enModule = await import(`@/translations/languages/en/${namespace}.json`);
    const enKeys = new Set(flattenKeys(enModule.default));

    for (const lang of SUPPORTED_LANGUAGES) {
      if (lang === 'en') continue;
      const langModule = await import(`@/translations/languages/${lang}/${namespace}.json`);
      const langKeys = new Set(flattenKeys(langModule.default));

      const missing = [...enKeys].filter((k) => !langKeys.has(k));
      const extra = [...langKeys].filter((k) => !enKeys.has(k));

      expect(missing, `${lang}/${namespace}.json is missing keys present in en`).toEqual([]);
      expect(extra, `${lang}/${namespace}.json has stray keys not present in en`).toEqual([]);
    }
  });
});
