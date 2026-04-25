const path = require('path');

module.exports = {
  webpack: {
    configure: (config) => {
      // Exclude node_modules from source-map-loader to avoid ENOENT errors
      // when packages have broken/missing source map references (e.g. axios)
      const sourceMapLoaderRule = config.module.rules.find(
        (rule) => rule.enforce === 'pre' && rule.use?.loader?.includes('source-map-loader')
      );
      if (sourceMapLoaderRule) {
        sourceMapLoaderRule.exclude = /node_modules/;
      }
      return config;
    },
  },
};
