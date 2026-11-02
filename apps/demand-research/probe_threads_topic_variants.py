"""One bounded follow-up: can direct Threads search discover project topics?

Uses the safe standalone public HTML parser from probe_competitor_sources.
No personal records or URL output; five public requests total.
"""
from probe_competitor_sources import threads
import json

for label,word in (("topic1","뒷계"),("topic2","섹트")):
    for style in ("recent","default"):
        row=threads(label,word,style)
        print(json.dumps(row,ensure_ascii=False),flush=True)
