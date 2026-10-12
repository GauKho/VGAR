// scip-python 0.6.6 builds RegExp(path.sep, 'g') without escaping '\\'.
// Narrow compatibility shim; only repair that otherwise-invalid pattern.
if (process.platform === 'win32') {
  const NativeRegExp = global.RegExp;
  function repair(args) {
    if (args[0] === '\\') args[0] = '\\\\';
    return args;
  }
  global.RegExp = new Proxy(NativeRegExp, {
    construct(target, args) { return Reflect.construct(target, repair(args)); },
    apply(target, receiver, args) { return Reflect.apply(target, receiver, repair(args)); },
  });
}
