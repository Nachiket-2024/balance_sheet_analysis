import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { globalIgnores } from 'eslint/config'

export default tseslint.config([
  globalIgnores(['dist', 'coverage', '**/coverage/**']),
  {
    // Test files live at ../tests/frontend, outside this project's own
    // root (per the repository's top-level tests/backend + tests/frontend
    // layout) — ESLint's flat config otherwise silently ignores anything
    // outside its own directory, so without this pattern `npm run lint`
    // gives zero signal on test code.
    files: ['**/*.{ts,tsx}', '../tests/frontend/**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // Standard convention for "intentionally unused" (e.g. a function
      // parameter kept for a stable API shape but not used in this
      // implementation) instead of silencing the rule file-wide.
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' },
      ],
    },
  },
])
