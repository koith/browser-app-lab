// Regression: a configured Pages origin must receive a successful CORS
// preflight even when the backing bucket/signing key is temporarily absent.
// No private data, live provider calls, or bypass of disallowed origins.
import assert from 'node:assert/strict';
import worker from './worker.mjs';
const endpoint='https://gallery-worker.example/api/v1/sign';
const make=(origin)=>new Request(endpoint,{method:'OPTIONS',headers:{Origin:origin,'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'}});
const env={PAGE_ORIGIN:'https://koith.github.io'};
const allowed=await worker.fetch(make(env.PAGE_ORIGIN),env);
assert.equal(allowed.status,204);
assert.equal(allowed.headers.get('Access-Control-Allow-Origin'),env.PAGE_ORIGIN);
assert.match(allowed.headers.get('Access-Control-Allow-Methods')||'',/POST/);
assert.match(allowed.headers.get('Access-Control-Allow-Headers')||'',/Content-Type/i);
const denied=await worker.fetch(make('https://untrusted.example'),env);
assert.equal(denied.status,403);
assert.equal(denied.headers.get('Access-Control-Allow-Origin'),null);
const actual=await worker.fetch(new Request(endpoint,{method:'POST',headers:{Origin:env.PAGE_ORIGIN,'Content-Type':'application/json'},body:'{}'}),env);
assert.equal(actual.status,503);
assert.equal(actual.headers.get('Access-Control-Allow-Origin'),env.PAGE_ORIGIN);
console.log('G09 preflight allowed/denied and backend-503 separation PASS');
