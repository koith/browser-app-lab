'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const assert=require('node:assert/strict');

for(const model of ['mimmi','yui']){
 const html=fs.readFileSync(path.join(__dirname,'..',model+'-gallery','index.html'),'utf8');
 const start=html.indexOf('let photoGridObserver=null,photoGridGeneration=0;');
 const end=html.indexOf('function render(){',start);
 assert.ok(start>0&&end>start,'progressive renderer exists');
 assert.match(html,/function render\(\)\{\s*photoGridGeneration\+\+;photoGridObserver\?\.disconnect\(\)/);
 assert.match(html,/const visible=all\.filter\(p=>match\(p\.name\)\);renderPhotoGridProgressively\(visible\);/);
 const opened=[],observers=[];
 const grid={children:[],replaceChildren(){this.children=[];},
   insertAdjacentHTML(_where,markup){
    for(const match of markup.matchAll(/data-i="(\d+)"/g))
      this.children.push({dataset:{i:match[1]},onclick:null});
   },
   appendChild(node){this.children.push(node);}};
 const document={createElement:()=>({
    className:'',style:{},setAttribute(){},
    remove(){const i=grid.children.indexOf(this);if(i>=0)grid.children.splice(i,1);}
  })};
 class Observer {
  constructor(callback,options){this.callback=callback;this.options=options;this.connected=false;observers.push(this);}
  observe(node){this.connected=true;this.node=node;}
  disconnect(){this.connected=false;}
  trigger(){this.callback([{isIntersecting:true,target:this.node}]);}
 }
 const context={
   document,mode:'photos',IntersectionObserver:Observer,
   $:()=>grid,photoHTML:(_p,i)=>'<button class="photo" data-i="'+i+'"></button>',
   openViewer:(photos,i)=>opened.push({count:photos.length,i}),
   observeOwner:()=>{},
 };
 vm.createContext(context);
 vm.runInContext(html.slice(start,end),context);
 const photos=Array.from({length:130},(_,i)=>({number:i+1}));
 context.renderPhotoGridProgressively(photos);
 assert.equal(grid.children.length,65,'initial render has 64 tiles and one sentinel');
 grid.children[63].onclick();
 assert.deepEqual(opened.pop(),{count:130,i:63});
 assert.equal(observers[0].options.rootMargin,'700px');
 observers[0].trigger();
 assert.equal(grid.children.length,129,'second chunk 128 tiles plus sentinel');
 observers[1].trigger();
 assert.equal(grid.children.length,130,'all 130 tiles after scrolling to end');
 grid.children[129].onclick();
 assert.deepEqual(opened.pop(),{count:130,i:129});
 const oldObserver=observers[1];
 vm.runInContext('photoGridGeneration++;photoGridObserver?.disconnect();photoGridObserver=null',context);
 context.renderPhotoGridProgressively([{number:1}]);
 assert.equal(grid.children.length,1,'search change can fully replace prior tiles');
 oldObserver.trigger();
 assert.equal(grid.children.length,1,'stale observer must not resurrect old tiles');
 console.log('GALLERY_ON_DEMAND_PHOTO_GRID_SCROLL_AND_STALE_OBSERVER_PASS',model);
}
