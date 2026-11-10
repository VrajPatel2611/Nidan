import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

const config = [
  ...coreWebVitals,
  ...typescript,
  // Generated from ../openapi.yaml by `npm run gen:api`. Never edited by hand.
  { ignores: ["src/api/schema.ts", ".next/**", "node_modules/**"] },
];

export default config;
