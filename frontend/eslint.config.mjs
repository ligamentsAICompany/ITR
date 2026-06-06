import nextVitals from "eslint-config-next/core-web-vitals";

const eslintConfig = [
  {
    ignores: [".next/**", ".test-build/**", "out/**"],
  },
  ...nextVitals,
];

export default eslintConfig;
