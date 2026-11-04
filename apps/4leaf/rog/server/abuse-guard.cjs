'use strict';
// Bounded in-memory abuse throttling for anonymous ChatTown guests.
// Network peer is the actual TCP socket address, NOT an untrusted X-Forwarded-For.
// These limits are secondary abuse protection, never account authentication.
function createAbuseGuard({now=Date.now,maxEntries=2048}={}){
 const buckets=new Map();
 function take(category,key,limit,windowMs){
  const timestamp=now(),identity=category+':'+String(key||'unknown');
  let entry=buckets.get(identity);
  if(!entry||timestamp>=entry.resetAt){
   entry={count:0,resetAt:timestamp+windowMs};
   buckets.delete(identity);
  }
  if(entry.count>=limit){
   const error=new Error('Too many '+category+' requests; try again later');
   error.status=429;throw error;
  }
  entry.count++;
  // Move recent keys to the end, prune expired records then oldest keys
  // before attacker-controlled new sessions could grow process memory.
  buckets.delete(identity);buckets.set(identity,entry);
  if(buckets.size>maxEntries){
   for(const [id,record] of buckets){
    if(timestamp>=record.resetAt)buckets.delete(id);
   }
   while(buckets.size>maxEntries)buckets.delete(buckets.keys().next().value);
  }
 }
 return {
  session:(networkPeer)=>{
   take('session-peer',networkPeer,60,60000);
   take('session-global','all',600,60000);
  },
  createRoom:(personId)=>{
   take('room-create-person',personId,5,60000);
   take('room-create-global','all',120,60000);
  },
  password:(personId)=>{
   take('password-person',personId,6,60000);
   take('password-global','all',120,60000);
  },
  chat:()=>take('chat-global','all',350,5000),
  inspect:()=>({trackedKeys:buckets.size})
 };
}
module.exports={createAbuseGuard};
