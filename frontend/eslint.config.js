import js from "@eslint/js";
import globals from "globals";
import react from "eslint-plugin-react";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      react,
    },
    rules: {
      "react/no-danger": "error",
      "no-eval": "error",
      "no-restricted-properties": [
        "error",
        {
          property: "innerHTML",
          message: "Uso de innerHTML prohibido por seguridad.",
        },
        {
          property: "outerHTML",
          message: "Uso de outerHTML prohibido por seguridad.",
        },
        {
          property: "insertAdjacentHTML",
          message: "Uso de insertAdjacentHTML prohibido por seguridad.",
        },
      ],
    },
  },
);
