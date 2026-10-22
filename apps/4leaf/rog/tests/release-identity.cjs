'use strict';
/* One truthful release ID for the revived WEB APP (not the 2004 client).
 * Web metadata, immutable PWA cache revision and offline manifest must agree.
 * The real deployed index is checked separately in the release workflow.
 */
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const meta=JSON.parse(fs.readFileSync(path.join(root,'app-version.json'),'utf8'));
const index=fs.readFileSync(path.join(root,'index.html'),'utf8');
const sw=fs.readFileSync(path.join(root,'sw.js'),'utf8');
assert.equal(meta.version,'0.86.0-beta.10');
assert.match(meta.channel,/beta/,'original client exact copy was not completed');
assert.ok(meta.sourceFidelity.includes('not-complete'),'do not falsely claim original is finished');
assert.ok(!meta.originalClient.includes(meta.version),'web revival is separate from 2002–2004 release');
assert.ok(index.includes('<meta name="leaf-revival-version" content="'+meta.version+'">'));
assert.ok(index.includes('content="partial-original-source-assets"'));
assert.ok(sw.includes("const REVISION='"+meta.pwaCache+"'"));
assert.ok(sw.includes("'./app-version.json'"),'the version must be available on iOS in airplane mode');
console.log('4LEAF RELEASE VERSION AND OFFLINE IDENTITY PASS',JSON.stringify({
 appVersion:meta.version,pwaCache:meta.pwaCache,fidelity:meta.sourceFidelity
}));
