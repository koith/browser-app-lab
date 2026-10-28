#!/usr/bin/env python3
"""Offline check for multi-site Mimmi 52-title research index parser."""
from discover_source_inventory import extract_entries,canonical

def main():
    sample="""<html><div>
      <p>NO.052 DJAWA Photo Mimmi Asuna the Maid 〖125P〗</p>
      <p>Mimmi NO.051 DJAWA Photo Mimmi Rei, Beyond the Heart [97P]</p>
      <p>NO.050 DJAWA Photo Mimmi Nikke Elegg 〖154P〗</p>
      <p>NO.051 DJAWA Photo Mimmi Rei, Beyond the Heart [97P]</p>
      <p>NO.003 DJAWA Photo Mimmi Some Theme</p>
      <p>NO.300 Bad</p>
      </div></html>"""
    items=extract_entries(sample)
    assert len(items)==4,items
    a={x["number"]:x for x in items}
    assert a[52]["advertised_photos"]==125,a
    assert a[51]["advertised_photos"]==97,a
    assert a[3]["advertised_photos"] is None,a
    assert "rei" in canonical(a[51]["title"])
    print("MIMMI_MULTI_SOURCE_RESEARCH_PARSER_PASS")
if __name__=="__main__":main()
