'use strict';
const path = require('node:path');
const { createRequire, registerHooks } = require('node:module');
const { pathToFileURL } = require('node:url');

if (typeof registerHooks !== 'function') {
  throw new Error('兼容启动需要 Node.js 24；也可以在原生 esbuild 正常的环境使用 pnpm dev。');
}
const projectRequire = createRequire(path.join(__dirname, 'package.json'));
const viteRequire = createRequire(projectRequire.resolve('vite/package.json'));
const nativeVersion = viteRequire('esbuild/package.json').version;
const wasmVersion = projectRequire('esbuild-wasm/package.json').version;
if (nativeVersion !== wasmVersion) {
  throw new Error('esbuild 与 esbuild-wasm 版本必须一致，请使用锁定依赖安装。');
}
const wasmUrl = pathToFileURL(projectRequire.resolve('esbuild-wasm')).href;
registerHooks({
  resolve(specifier, context, nextResolve) {
    const normalized = specifier.replace(/\\/g, '/');
    if (specifier === 'esbuild' || normalized.endsWith('/esbuild/lib/main.js')) {
      return { url: wasmUrl, format: 'commonjs', shortCircuit: true };
    }
    return nextResolve(specifier, context);
  }
});
