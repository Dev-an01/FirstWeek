module.exports = {
  presets: [
    ['@babel/preset-env', { targets: { node: 'current' } }],
    ['@babel/preset-react', { runtime: 'automatic' }],
  ],
  plugins: [
    '@babel/plugin-syntax-import-meta', // Allow parsing of import.meta
    // Custom plugin to transform import.meta.env to process.env for Jest
    function ({ types: t }) {
      return {
        name: 'transform-import-meta-env',
        visitor: {
          MemberExpression(path) {
            // Check if this is import.meta.env.SOMETHING
            if (
              t.isMemberExpression(path.node.object) &&
              t.isMetaProperty(path.node.object.object) &&
              path.node.object.object.meta.name === 'import' &&
              path.node.object.object.property.name === 'meta' &&
              path.node.object.property.name === 'env'
            ) {
              // Replace import.meta.env with process.env
              path.node.object = t.memberExpression(
                t.identifier('process'),
                t.identifier('env')
              );
            }
          },
        },
      };
    },
  ],
};