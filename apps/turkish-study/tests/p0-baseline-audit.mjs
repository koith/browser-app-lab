// Read-only structural/static audit. Node 18+; run from any cwd: node tests/p0-baseline-audit.mjs
import fs from 'node:fs';
const root=new URL('../',import.meta.url);
const read=n=>fs.readFileSync(new URL(n,root),'utf8');
function audit(c,l,m,html){
 const checks=[];const check=(id,ok,expected,actual)=>checks.push({id,result:ok?"pass":"fail",expected,actual});
 const first=l.lessons.filter(x=>x.day<=7), ids=l.lessons.flatMap(x=>x.questions.map(q=>q.id));
 const days=c.days;
 check("curriculum-sequence",days.length===120&&days.every((x,i)=>x.day===i+1&&x.id===`D${String(i+1).padStart(3,"0")}`),120,days.length);
 check("first-week",first.length===7&&first.every((x,i)=>x.day===i+1),7,first.length);
 check("mapped-ids",l.lessons.every(x=>days.some(d=>d.id===x.id&&d.day===x.day)),true,l.lessons.map(x=>x.id));
 check("unique-question-ids",new Set(ids).size===ids.length,true,ids.length);
 check("question-id-sequence",l.lessons.every(x=>x.questions.every((q,i)=>q.id===`${x.id}-Q${i+1}`)),true,ids.length);
 check("answer-unique",l.lessons.every(x=>x.questions.every(q=>q.choices.filter(v=>v===q.answer).length===1&&new Set(q.choices).size===q.choices.length)),true,ids.length);
 check("nfc",JSON.stringify(l)===JSON.stringify(l).normalize("NFC"),true,JSON.stringify(l)===JSON.stringify(l).normalize("NFC"));
 check("required-content",first.every(x=>["objective","grammar","note","task"].every(k=>typeof x[k]==="string"&&x[k].length)&&["examples","dialogue","questions"].every(k=>x[k].length>0)),true,first.length);
 check("source-ids",first.every(x=>x.sources.every(s=>s in c.sources)),true,first.map(x=>x.sources.length));
 check("monthly-assessments",JSON.stringify(days.filter(x=>x.kind==="assessment"&&[30,60,90,120].includes(x.day)).map(x=>x.day))===JSON.stringify([30,60,90,120]),[30,60,90,120],days.filter(x=>[30,60,90,120].includes(x.day)).map(x=>[x.day,x.kind]));
 const norm=s=>s.normalize("NFC").toLocaleLowerCase("tr-TR").trim().replace(/[.!?]+$/,"").replace(/\s+/g," ");
 let known=new Set(),unseen=[];
 for(const x of first){for(const p of [...x.words,...x.examples,...x.dialogue.map(p=>[p[1],p[2]])])known.add(norm(p[0]));for(const q of x.questions)for(const v of q.choices)if(!known.has(norm(v)))unseen.push({question:q.id,choice:v});}
 check("choice-prior-attestation",unseen.length===0,[],unseen);
 check("manifest-reference-static",html.includes("RELEASE_MANIFEST.json"),true,html.includes("RELEASE_MANIFEST.json"));
 check("answer-explanations",first.every(x=>x.questions.every(q=>typeof q.explanation==="string"&&q.explanation.trim())),true,first.reduce((n,x)=>n+x.questions.filter(q=>q.explanation).length,0));
 check("approved-days",m.publishedDayIds.length===7,7,m.publishedDayIds.length);
 return {checks,counts:first.map(x=>({id:x.id,words:x.words.length,examples:x.examples.length,turns:x.dialogue.length,questions:x.questions.length})),totals:{words:first.reduce((n,x)=>n+x.words.length,0),examples:first.reduce((n,x)=>n+x.examples.length,0),turns:first.reduce((n,x)=>n+x.dialogue.length,0),questions:first.reduce((n,x)=>n+x.questions.length,0)}};
}
const result=audit(JSON.parse(read('curriculum.json')),JSON.parse(read('lessons.json')),JSON.parse(read('RELEASE_MANIFEST.json')),read('index.html'));
console.log(JSON.stringify(result,null,2));
process.exitCode=result.checks.some(c=>c.result==='fail')?1:0;
