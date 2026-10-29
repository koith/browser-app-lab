'use strict';
/* Offline gallery connector regression. No real owner token or network required. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const src = fs.readFileSync(path.join(__dirname, 'gallery-private-connect.js'), 'utf8');

function fakeElement(id) {
  return {
    id, hidden:false,value:'',disabled:false,textContent:'',dataset:{},
    className:'',innerHTML:'',attributes:{},
    classList:{remove(){},add(){}},
    focus(){},
    addEventListener(name, handler){this['on' + name]=handler},
    setAttribute(name, value){this.attributes[name]=value},
    insertAdjacentElement(where, element){this.inserted = element},
    async fire(type, payload={}) {if(this['on'+type]) return this['on'+type]({preventDefault(){},...payload});}
  };
}

async function run(model, options={}) {
  const elements=new Map();
  for(const name of ['browse','pg-toggle','pg-form','pg-token','pg-status','pg-submit','pg-cancel'])
    elements.set(name,fakeElement(name));
  // Form is injected with an HTML hidden attribute, unlike a bare fake element.
  elements.get('pg-form').hidden=true;
  const vault=fakeElement('vault');
  const browse=elements.get('browse');
  browse.querySelector=selector=>selector==='.vault-actions'?vault:null;
  const store=new Map();
  const key=model+'-owner-session';
  if(options.session)store.set(key,JSON.stringify(options.session));
  const requests=[];let reloads=0;
  const gallery={model,schema_version:1,albums:[{
    id:'photo-album',images:[
      {number:1,bytes:1000,sha256:'1'.repeat(64)},
      {number:2,bytes:1200,sha256:'2'.repeat(64)}
    ]
  }]};
  const ctx={
    document:{
      currentScript:{dataset:{model}},readyState:'complete',
      createElement:()=>fakeElement('owner-gallery-connector'),
      getElementById:id=>elements.get(id)||null
    },
    sessionStorage:{
      getItem:key=>store.get(key)||null,setItem:(key,v)=>store.set(key,v),
      removeItem:key=>store.delete(key)
    },
    location:{reload(){reloads++}},
    fetch:async (url,args)=>{
      requests.push({url,headers:args.headers,cache:args.cache,credentials:args.credentials});
      return options.response || {ok:true,status:200,json:async()=>gallery};
    },
    AbortController, setTimeout,clearTimeout,
  };
  vm.runInNewContext(src,ctx,{filename:'gallery-private-connect.js'});
  assert(vault.inserted,'Gallery inline connection panel not inserted');
  const toggle=elements.get('pg-toggle');
  const form=elements.get('pg-form');
  const password=elements.get('pg-token');
  const status=elements.get('pg-status');
  if (!options.session) {
    assert.match(status.textContent,/공개 저장본만/);
    await toggle.fire('click');assert.equal(form.hidden,false);
    password.value='fake-offline-owner-access-token';
    await form.fire('submit');
    const pending=options.response && options.response.status !== 200;
    // Auth errors never write credentials or reload.
    if (pending) {
      assert.equal(store.has(key),false);
      assert.equal(reloads,0);
      assert.match(status.textContent,/연결 실패/);
    } else {
      assert.equal(reloads,1,'Authenticated media catalog should reload the gallery');
      assert.equal(JSON.parse(store.get(key)).token,password.value||'fake-offline-owner-access-token');
    }
  } else {
    await new Promise(resolve=>setTimeout(resolve,0));
    assert.match(status.textContent,/연결됨/);
    await toggle.fire('click');
    assert.equal(store.has(key),false,'disconnect must remove private session');
    assert.equal(reloads,1);
  }
  assert.equal(requests[0].url,'https://mimmi-private-gallery-free.onrender.com'
    +(model==='yui'?'/api/yui/catalog':'/api/catalog'));
  assert.equal(requests[0].credentials,'omit');
  assert.equal(requests[0].cache,'no-store');
  assert.ok(requests[0].headers.Authorization.startsWith('Bearer '));
  assert.equal(/https:\/\/(?!mimmi-private-gallery-free)/.test(requests[0].url),false);
}

(async()=>{
  for(const model of ['yui','mimmi']) {
    await run(model);
    await run(model,{response:{ok:false,status:401}});
    await run(model,{response:{ok:false,status:503}});
    await run(model,{session:{api:'https://mimmi-private-gallery-free.onrender.com',token:'existing-private-session'}});
  }
  // Prevent shipping secrets or public TeraBox URLs inside the Pages connector.
  assert(!/ndus=|RCLONE_CONFIG_ARCHIVE_COOKIE|Y7tLTwvksRbA/.test(src));
  console.log('OWNER_GALLERY_INLINE_REAL_CATALOG_AUTH_RELOAD_TEST_PASS: 2 models x 4 cases');
})().catch(err=>{console.error(err);process.exitCode=1});
