#!/usr/bin/env python3
"""Mimmi actor scope and duplicate album isolation unit check."""
from unittest.mock import patch
import discover_v2ph_actor as c
import collect_v2ph_public as v

class Fake:
    status_code=200
    url="https://www.v2ph.com/actor/Mimmi"
    content=b"""<h1>Mimmi</h1><article><a href="/album/abc123.html"><h3>Mimmi Alice</h3></a></article>
    <article><a href="/album/efg456.html">Mimmi Sunshine</a></article>
    <a href="https://evil.example/album/hack.html">evil</a>
    """
    def raise_for_status(self):pass

def main():
    with patch.object(v.S,"get",return_value=Fake()):
        albums,pages=c.scan_actor(1,20)
    assert len(albums)==2,albums
    assert albums[0]["id"]=="v2ph-actor-abc123",albums
    assert len(pages)==1
    print("MIMMI_ACTOR_SAFETY_AND_LINK_DISCOVERY_PASS")
if __name__=="__main__":main()
