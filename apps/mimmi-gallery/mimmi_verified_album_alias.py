"""Match published photo sets to saved album IDs using shared SHA-256."""
def align(targets,source,public,owner):
    known={}
    for manifest in (public,owner):
        for album in manifest["albums"]:
            rec=known.setdefault(album["id"],{"hashes":set(),"last":0})
            for n,p in enumerate(album["images"],1):
                rec["hashes"].add(p["sha256"])
                rec["last"]=max(rec["last"],p.get("number") or n)
    by_id={a["id"]:a for a in source["albums"]}
    converted=[]; proof=[]
    for album in targets:
        samples={p["sha256"] for p in by_id[album["id"]]["samples"]}
        ranked=sorted(((len(rec["hashes"] & samples),aid)
                       for aid,rec in known.items()),reverse=True)
        first,aid=ranked[0] if ranked else (0,"")
        second=ranked[1][0] if len(ranked)>1 else 0
        if first<3 or second>max(1,first//4):continue
        rec=known[aid]
        out=[]
        for p in album["images"]:
            if p["sha256"] in rec["hashes"]:continue
            rec["last"]+=1
            if rec["last"]>20000:raise ValueError("album limit exceeded")
            out.append({**p,"number":rec["last"]})
            rec["hashes"].add(p["sha256"])
        if out:
            converted.append({**album,"id":aid,"images":out,"expected":None})
            proof.append({"source":album["id"],"album":aid,
                          "shared_sha":first,"candidates":len(out)})
    return converted,proof
