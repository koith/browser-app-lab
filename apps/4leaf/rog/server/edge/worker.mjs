import { DurableObject } from "cloudflare:workers";
import central from "../central.cjs";
const ORIGIN="https://koith.github.io";
const empty=()=>({rooms:[],history:[],sequence:0});
class Archive{
 kind="durable-object";
 constructor(storage){this.storage=storage;this.last=new Map()}
 async load(){
  const values=await this.storage.list();
  if(!values.size){this.last=new Map();return empty()}
  if(!values.has("seq"))throw Error("Missing authority sequence");
  const result={rooms:[],history:[],sequence:JSON.parse(values.get("seq"))};
  for(const [key,value] of values){
   if(key.startsWith("room:"))result.rooms.push(JSON.parse(value));
   else if(key.startsWith("history:"))result.history.push([key.slice(8),JSON.parse(value)]);
   else if(key!=="seq")throw Error("Unexpected authority archive key");
  }
  this.last=values;return result;
 }
 async save(data){
  const next=new Map([["seq",JSON.stringify(data.sequence)]]);
  for(const room of data.rooms)next.set("room:"+room.id,JSON.stringify(room));
  for(const [id,lines] of data.history)next.set("history:"+id,JSON.stringify(lines));
  const put=[...next].filter(([key,value])=>this.last.get(key)!==value);
  const del=[...this.last.keys()].filter(key=>!next.has(key));
  await this.storage.transaction(async tx=>{
   for(const [key,value] of put)await tx.put(key,value);
   for(const key of del)await tx.delete(key);
  });
  this.last=next;
 }
}
export class ChatAuthority extends DurableObject{
 constructor(ctx,env){
  super(ctx,env);
  this.core=central.makeServer({fetchOnly:true,origins:ORIGIN,persistence:new Archive(ctx.storage)});
 }
 async fetch(request){
  const u=new URL(request.url),origin=request.headers.get("origin")||"";
  const peer=request.headers.get("cf-connecting-ip")||"edge-unknown";
  if(u.pathname==="/api/socket"){
   if(origin!==ORIGIN||request.headers.get("upgrade")?.toLowerCase()!=="websocket")return new Response("Forbidden",{status:403});
   const pair=new WebSocketPair(),[client,server]=Object.values(pair);
   this.ctx.acceptWebSocket(server);
   server.serializeAttachment({origin,peer});
   return new Response(null,{status:101,webSocket:client});
  }
  return this.core.fetch(request,peer);
 }
 async webSocketMessage(ws,raw){
  let m;try{
   if(typeof raw!=="string"||raw.length>12000)throw Error("Invalid request");
   m=JSON.parse(raw);
   if(typeof m.id!=="string"||m.id.length>30||!["GET","POST"].includes(m.method)||
    typeof m.route!=="string"||!/^\/api\/[a-zA-Z0-9/_?%&=.+-]+$/.test(m.route))throw Error("Invalid request");
   const attachment=ws.deserializeAttachment();
   if(attachment?.origin!==ORIGIN)throw Error("Forbidden");
   const req=new Request("https://authority.invalid"+m.route,{method:m.method,
    headers:{origin:ORIGIN,"content-type":"application/json",...(m.token?{authorization:"Bearer "+m.token}:{})},
    ...(m.method==="POST"?{body:JSON.stringify(m.data??{})}:{})});
   const response=await this.core.fetch(req,attachment.peer);
   ws.send(JSON.stringify({id:m.id,status:response.status,body:await response.text()}));
  }catch{
   if(m?.id)try{ws.send(JSON.stringify({id:m.id,status:400,body:JSON.stringify({error:"Invalid edge request"})}))}catch{}
  }
 }
 webSocketClose(ws){try{ws.close()}catch{}}
 webSocketError(ws){try{ws.close()}catch{}}
}
export default {fetch(request,env){
 const u=new URL(request.url);
 if(!u.pathname.startsWith("/api/"))return new Response("4LEAF ChatTown authority",{status:404});
 return env.CHAT.get(env.CHAT.idFromName("production-v1")).fetch(request);
}};
