module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
  },
  extends: [
    'airbnb',
    'airbnb/hooks',
    'plugin:react-hooks/recommended',
    'plugin:prettier/recommended', // adding it at last to override other configs
  ],
  overrides: [
    {
      env: {
        node: true,
      },
      files: ['.eslintrc.{js,cjs}'],
      parserOptions: {
        sourceType: 'script',
      },
    },
    {
      files: [
        '**/__tests__/**/*',
        '**/*.test.js',
        '**/*.test.jsx',
        '**/setupTests.js',
        'src/test/**/*',
      ],
      env: {
        jest: true,
      },
      rules: {
        'import/no-extraneous-dependencies': [
          'error',
          { devDependencies: true },
        ],
        'react/function-component-definition': 'off',
        'no-plusplus': 'off',
      },
    },
  ],
  parserOptions: {
    parser: '@babel/eslint-parser',
    requireConfigFile: false,
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  plugins: ['react'],
  rules: {
    'react/react-in-jsx-scope': 0,
    'react-hooks/exhaustive-deps': 0,
    'react/no-unescaped-entities': 'off',
    'react/require-default-props': 'off',
    'react/no-array-index-key': 0,
    'react/destructuring-assignment': 0,
    'no-console': 0,
    camelcase: 0,
    'no-alert': 0,
    'react/button-has-type': 0,
    'no-underscore-dangle': 0,
    'no-nested-ternary': 0,
    'import/prefer-default-export': 0,
    'jsx-a11y/label-has-associated-control': 0,
    'react/prop-types': 0,
    'jsx-a11y/click-events-have-key-events': 0,
    'jsx-a11y/no-static-element-interactions': 0,
    'no-plusplus': 0,
    'no-restricted-globals': 0,
    'class-methods-use-this': 0,
    'no-return-await': 0,
    'no-await-in-loop': 0,
    'jsx-ally/media-has-caption': 0,
    'no-restricted-syntax': 0,
    'no-bitwise': 0,
    'import/extensions': [
      'error',
      'ignorePackages',
      {
        js: 'never',
        jsx: 'never',
      },
    ],
  },
  settings: {
    react: {
      version: 'detect',
    },
  },
};
