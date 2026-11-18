'use strict';
/* 4LEAF V2: authoritative CREATE/JOIN transaction independent of DOM and original sprites.
   A server-acknowledged room is never duplicated after a failed JOIN. */
(function(root,build){
 const api=build();
 if(typeof module==='object'&&module.exports)module.exports=api;
 if(root)root.__LEAF_ROOM_DOMAIN__=api;
})(typeof window==='object'?window:null,function(){
 function makeCreationSession(options){
  if(!options||typeof options.create!=='function'||typeof options.join!=='function'||
    typeof options.enter!=='function')throw TypeError('Room session requires create, join and enter');
  let phase='idle',room=null,draft=null,pending=null,disposed=false,joined=false,lastError=null;
  const assertActive=()=>{
   if(disposed||options.isActive?.()===false){
    const error=new Error('Room creation dialog closed');error.code='DIALOG_CLOSED';throw error;
   }
  };
  async function perform(input){
   assertActive();
   try{
    if(!room){
     draft=Object.freeze({...input});
     phase='creating';
     const response=await options.create(draft);
     if(!response?.room?.id)throw Error('Missing authoritative room ID in CREATE response');
     // Save ACK before invoking UI or initiating JOIN, even if a callback fails.
     room=options.normalize?options.normalize(response.room):response.room;
     if(!room?.id)throw Error('Normalized room lacks ID');
     options.onCreated?.(room);
    }
    assertActive();phase='joining';
    if(options.isReady?.()===false)await options.connect?.();
    await options.join(room.id,draft.password||'');
    try{
     assertActive();
     if(await options.enter(room)===false)throw Error('Server JOIN confirmed but scene entry failed');
    }catch(error){
     // Compensate the successful server admission when the screen cannot enter.
     try{await options.leave?.()}catch(rollbackError){error.rollbackError=rollbackError}
     throw error;
    }
    joined=true;phase='joined';lastError=null;
    return {room,joined:true};
   }catch(error){
    phase=room?'retryable':'failed';lastError=error;
    throw error;
   }
  }
  function submit(input){
   if(joined)return Promise.resolve({room,joined:true});
   if(pending)return pending;
   const work=perform(input);
   pending=work.finally(()=>{pending=null});
   return pending;
  }
  return {
   submit,dispose(){disposed=true},
   get room(){return room},
   get draft(){return draft},
   get state(){return {phase,roomId:room?.id||null,joined,pending:!!pending,
    error:lastError?.message||null,disposed}}
  };
 }
 return Object.freeze({makeCreationSession});
});