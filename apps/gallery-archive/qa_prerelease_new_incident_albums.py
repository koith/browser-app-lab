#!/usr/bin/env python3
"""Accept new user-reported photo failures before production deploy.

Reuses the fully staged FastAPI test with actual already-owned TeraBox bytes.
No new image discovery, no writes to TeraBox, no private files published.
"""
import argparse
from qa_prerelease_real_owner_gateway import TARGET, run

INCIDENT_ALBUMS = {
    "mimmi": ("djawa-janus-scary-lantern-night", 15),
    "yui": ("djawa-privaty-public-samples", 30),
}

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--model",choices=("mimmi","yui"),required=True)
    args=parser.parse_args()
    TARGET[args.model]=INCIDENT_ALBUMS[args.model]
    run(args.model)
    print("NEW_USER_SCREENSHOT_REAL_EXISTING_OWNER_ALL_PHOTOS_PASS",args.model,
          INCIDENT_ALBUMS[args.model][1],flush=True)
