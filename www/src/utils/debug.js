const wrap = function(functionToWrap, before, after, thisObject) {
  return function () {
      var args = Array.prototype.slice.call(arguments), result;
      if (before) before.apply(thisObject || this, args);
      result = functionToWrap.apply(thisObject || this, args);
      if (after) after.apply(thisObject || this, args);
      return result;
  };
};

export function enableWeb3Profiling(verbose = false) {
  if (!window.ethereum) {
    console.log('profiling disabled: window.ethereum was not found');
    return;
  }
  if (window.ethereum.request.name !== 'bound request') return;  // already wrapped?
  
  const VERBOSE_ONLY_METHODS = ['eth_chainId', 'eth_accounts', 'eth_blockNumber'];
  let startTime = undefined;

  const calls = {}
  const requests = {}
  window.profiler = {
    calls: calls,
    requests: requests,
    totalRequests: 0,
  }
  window.ethereum.request = wrap(window.ethereum.request,
    ({ method, params }) => {
      if (!startTime) {
        startTime = Date.now();
      }
      requests[method] = (requests[method] || 0) + 1;
      window.profiler.totalRequests += 1;

      const elapsed = (Date.now() - startTime) / 1000;
      const n = window.profiler.totalRequests;
      if (verbose || VERBOSE_ONLY_METHODS.indexOf(method) === -1) {
        console.log(`${elapsed.toFixed(2)}s [${n}] json-rpc: ${method} `, params);
      }
      if (method === 'eth_call') {
        const to = params[0]['to'];
        const signature = params[0]['data'].substr(0, 10);
        if (!calls.hasOwnProperty(to)) calls[to] = {}
        calls[to][signature] = (calls[to][signature] || 0) + 1;
      }
      if (n > 500) {
        throw new Error("Guard from infinite loop requests");
      }
    },
    () => {},
  );
}