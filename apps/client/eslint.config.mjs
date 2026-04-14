// @ts-check
import tseslint from "typescript-eslint"
import unicorn from "eslint-plugin-unicorn"
import sonarjs from "eslint-plugin-sonarjs"
import n from "eslint-plugin-n"
import i18next from "eslint-plugin-i18next"
import prettier from "eslint-config-prettier"

export default tseslint.config(
  ...tseslint.configs.strictTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  unicorn.configs.recommended,
  sonarjs.configs.recommended,
  n.configs["flat/recommended"],
  prettier,
  {
    plugins: { i18next },
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
  {
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unsafe-assignment": "error",
      "@typescript-eslint/no-unsafe-call": "error",
      "@typescript-eslint/no-unsafe-member-access": "error",
      "@typescript-eslint/no-unsafe-return": "error",
      "@typescript-eslint/no-unsafe-argument": "error",
      "@typescript-eslint/strict-boolean-expressions": "error",
      "@typescript-eslint/no-non-null-assertion": "error",
      "@typescript-eslint/consistent-type-imports": [
        "error",
        { prefer: "type-imports" },
      ],
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/require-await": "error",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/await-thenable": "error",
      "unicorn/prevent-abbreviations": [
        "error",
        {
          replacements: {
            props: false,
            ref: false,
            args: false,
            params: false,
            err: false,
            cb: false,
          },
        },
      ],
      "unicorn/no-process-exit": "off",
      "unicorn/no-array-reduce": "off",
      "unicorn/filename-case": [
        "error",
        {
          cases: { camelCase: true, pascalCase: true },
        },
      ],
      "sonarjs/cognitive-complexity": ["error", 15],
      "sonarjs/no-duplicate-string": ["error", { threshold: 3 }],
      "n/no-missing-import": "off",
      "n/no-unpublished-import": "off",
      "n/no-unsupported-features/node-builtins": [
        "error",
        { version: ">=22.0.0" },
      ],
      "n/no-unsupported-features/es-syntax": [
        "error",
        { version: ">=22.0.0" },
      ],
      "unicorn/import-style": [
        "error",
        {
          styles: {
            "node:path": { default: true },
            "node:url": { default: false, namespace: false, named: true },
          },
        },
      ],
      "sonarjs/prefer-read-only-props": "error",
      "unicorn/no-null": "off",
      "no-magic-numbers": [
        "warn",
        {
          ignore: [0, 1, -1, 2],
          ignoreArrayIndexes: true,
          ignoreDefaultValues: true,
          ignoreClassFieldInitialValues: true,
          enforceConst: true,
        },
      ],
      "id-match": [
        "error",
        "^[a-zA-Z_$][a-zA-Z0-9_$]*$",
        { properties: true, onlyDeclarations: false },
      ],
      "i18next/no-literal-string": [
        "error",
        {
          mode: "jsx-only",
          ignore: ["^[^a-zA-Z]*$"],
          ignoreAttribute: [
            "color",
            "backgroundColor",
            "mask",
            "borderStyle",
            "type",
            "key",
            "id",
          ],
        },
      ],
    },
  },
  {
    files: ["src/cli.ts", "src/index.tsx"],
    rules: {
      "i18next/no-literal-string": "off",
      "n/no-process-exit": "off",
    },
  },
  {
    files: ["tests/global-setup.ts", "vitest.config.ts"],
    rules: {
      "unicorn/filename-case": "off",
    },
  },
  {
    files: ["tests/**/*.ts", "**/*.test.ts", "**/*.spec.ts"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unsafe-assignment": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
      "@typescript-eslint/no-unsafe-argument": "off",
      "sonarjs/no-duplicate-string": "off",
      "sonarjs/todo-tag": "off",
      "sonarjs/no-os-command-from-path": "off",
      "sonarjs/os-command": "off",
      "sonarjs/no-nested-template-literals": "off",
      "unicorn/no-useless-undefined": "off",
      "unicorn/filename-case": "off",
      "unicorn/prevent-abbreviations": "off",
      "no-magic-numbers": "off",
      "i18next/no-literal-string": "off",
    },
  },
  {
    ignores: ["dist/", "node_modules/"],
  },
)
