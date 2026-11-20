"""Regression: identity-verified public profile capture survives AppView outages."""
import json

import pytest

from target_account_archive import SourceUnavailable
from target_account_enrichment import archive_profile, profile_metadata

DID = "did:plc:abcdefghijklmnopqrstuvwx"
PROFILE = {"platform": "bluesky", "identity": DID, "actor": DID,
           "pds": "https://pds.example.test",
           "profile_url": "https://bsky.app/profile/" + DID}
PDS_URL = (PROFILE["pds"] + "/xrpc/com.atproto.repo.getRecord?")
PDS_RESPONSE = {
    "uri": "at://" + DID + "/app.bsky.actor.profile/self",
    "value": {"$type": "app.bsky.actor.profile",
              "displayName": "Public PDS title", "description": "Original public bio"},
}


class PublicAPI:
    def __init__(self, primary=None, secondary=None, pds=None):
        self.primary = primary
        self.secondary = secondary
        self.pds = PDS_RESPONSE if pds is None else pds
        self.calls = []

    def json(self, url):
        self.calls.append(url)
        if url.startswith("https://public.api.bsky.app/"):
            result = self.primary
        elif url.startswith("https://api.bsky.app/"):
            result = self.secondary
        elif url.startswith(PDS_URL):
            result = self.pds
        else:
            raise AssertionError("Unexpected public endpoint")
        if isinstance(result, Exception):
            raise result
        return result


class Store:
    def __init__(self):
        self.saved = {}

    def write_immutable(self, path, data):
        assert path not in self.saved
        self.saved[path] = data


def test_primary_appview_failure_recovers_with_official_secondary():
    api = PublicAPI(primary=SourceUnavailable("temporary 503"),
                    secondary={"did": DID, "handle": "example.bsky.social",
                               "displayName": "Official", "followersCount": 7})
    meta = profile_metadata(PROFILE, api)
    assert meta["metadata_source"] == "official_bluesky_appview"
    assert meta["handle"] == "example.bsky.social"
    assert meta["followers_count"] == 7
    assert len(api.calls) == 2


def test_public_pds_record_preserves_verified_bio_without_fabricated_fields():
    api = PublicAPI(primary=SourceUnavailable("temporarily unavailable"),
                    secondary=SourceUnavailable("temporarily unavailable"))
    store = Store()
    stat = archive_profile(PROFILE, api, store)
    assert stat["profile_verified"] is True
    assert stat["profile_assets_unavailable"] == 0
    snapshots = [json.loads(raw) for path, raw in store.saved.items()
                 if path.startswith("profile/snapshots/")]
    assert len(snapshots) == 1
    doc = snapshots[0]
    assert doc["metadata_source"] == "public_pds_profile_record"
    assert doc["description"] == "Original public bio"
    assert doc["handle"] == ""
    assert doc["followers_count"] is None
    assert doc["assets"]["avatar"]["status"] == "not_set"
    assert doc["assets"]["banner"]["status"] == "not_set"
    # The exact same PDS record is reused for art checks; no redundant call.
    assert len([x for x in api.calls if x.startswith(PDS_URL)]) == 1


def test_mismatched_public_pds_uri_is_never_called_a_verified_profile():
    incorrect = {**PDS_RESPONSE, "uri": "at://did:plc:other/app.bsky.actor.profile/self"}
    api = PublicAPI(primary=SourceUnavailable("503"),
                    secondary=SourceUnavailable("503"), pds=incorrect)
    with pytest.raises(SourceUnavailable, match="identity mismatch"):
        archive_profile(PROFILE, api, Store())
