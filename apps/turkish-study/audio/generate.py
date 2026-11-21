#!/usr/bin/env python3
"""Generate isolated draft MP3s from the exact authoritative lesson arrays."""
import argparse, pathlib, json, hashlib, unicodedata, tempfile, subprocess
from collections import Counter
def main():
    p=argparse.ArgumentParser()
    p.add_argument("lessons",type=pathlib.Path)
    p.add_argument("--out",type=pathlib.Path,required=True)
    p.add_argument("--start",type=int,default=1)
    p.add_argument("--end",type=int,default=7)
    a=p.parse_args()
    assert 1<=a.start<=a.end<=120
    raw=a.lessons.read_bytes(); assets=[]; seen=set()
    assert not (a.out/"audio/manifest.json").exists(), "Use a fresh output directory"
    for l in json.loads(raw)["lessons"]:
        if not a.start<=l["day"]<=a.end: continue
        assert l["id"]==f'D{l["day"]:03d}'
        for kind,prefix,key,col in [("word","V","words",0),("example","E","examples",0),("dialogue","T","dialogue",1)]:
            for n,row in enumerate(l[key],1):
                text=row[col]; assert text and text==unicodedata.normalize("NFC",text)
                target=f'{l["id"]}-{prefix}{n}'; assert target not in seen; seen.add(target)
                aid=f'{target}-espeak-v1-{hashlib.sha256(text.encode()).hexdigest()[:12]}'
                rel=f'assets/audio/{l["id"]}/{aid}.mp3'; out=a.out/rel; out.parent.mkdir(parents=True,exist_ok=True)
                with tempfile.TemporaryDirectory() as tmp:
                    wav=pathlib.Path(tmp)/"speech.wav"
                    subprocess.run(["espeak","-v","tr","-s","145","-w",str(wav),"--stdin"],input=text.encode(),check=True)
                    subprocess.run(["ffmpeg","-v","error","-n","-i",str(wav),"-ar","22050","-ac","1","-codec:a","libmp3lame","-b:a","32k","-map_metadata","-1",str(out)],check=True)
                meta=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_entries","stream=codec_name,sample_rate,channels:format=duration","-of","json",str(out)]))
                s=meta["streams"][0]; assert s["codec_name"]=="mp3" and s["sample_rate"]=="22050" and s["channels"]==1 and float(meta["format"]["duration"])>0
                subprocess.run(["ffmpeg","-v","error","-i",str(out),"-f","null","-"],check=True)
                assets.append(dict(id=aid,lessonId=l["id"],kind=kind,targetId=target,text=text,locale="tr-TR",provider="eSpeak",voice="tr; 145 wpm; v1",license="eSpeak output: upstream author states no restriction; source text license applies; review pending",sourceUrl="https://sourceforge.net/p/espeak/discussion/538920/thread/58c2e481/",path=rel,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),reviewStatus="draft"))
    assert assets
    dest=a.out/"audio/manifest.json"; dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps({"schemaVersion":"1.0.0","assets":assets},ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"count":len(assets),"byKind":dict(Counter(x["kind"] for x in assets)),"inputSha256":hashlib.sha256(raw).hexdigest(),"reviewStatus":"draft"}))
if __name__=="__main__": main()
