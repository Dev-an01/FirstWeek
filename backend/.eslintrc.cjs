module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
  },
  extends: [
    "airbnb-base",
    "plugin:prettier/recommended", // adding it at last to override other configs
  ],
  overrides: [
    {
      env: {
        node: true,
      },
      files: [".eslintrc.{js,cjs}"],
      parserOptions: {
        sourceType: "script",
      },
    },
  ],
  parserOptions: {
    parser: "@babel/eslint-parser",
    requireConfigFile: false,
    ecmaVersion: "latest",
    sourceType: "module",
  },
  rules: {
    "no-console": 0,
    camelcase: 0,
    "no-alert": 0,
    "consistent-return": 0,
    "no-underscore-dangle": 0,
    "object-shorthand": 0,
    "import/no-relative-packages": 0,
    "no-case-declarations": 0,
    "no-useless-escape": 0,
    "no-plusplus": 0,
    "no-param-reassign": 0,
    "no-use-before-define": 0,
    "no-restricted-syntax": 0,
    "no-await-in-loop": 0,
    "no-nested-ternary": 0,
    "prefer-destructuring": 0,
    'no-restricted-globals': 0,
    'no-return-await': 0,
    radix: 0,
  },
  settings: {},
};
