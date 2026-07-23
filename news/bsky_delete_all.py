#!/usr/bin/env python3
"""Delete ALL of the account's Bluesky posts (app.bsky.feed.post records).

Irreversible. Runs from the bsky-delete workflow, which holds the app
password in a GitHub secret. Requires CONFIRM_DELETE=DELETE to actually run.

Env:
  BLUESKY_HANDLE        e.g. yang-fei0770.bsky.social
  BLUESKY_APP_PASSWORD  app password
  CONFIRM_DELETE        must equal "DELETE" or the script refuses
"""
import os
import sys
import time

import requests

PDS = "https://bsky.social"


def login(handle, password):
    r = requests.post(f"{PDS}/xrpc/com.atproto.server.createSession",
                      json={"identifier": handle, "password": password}, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    handle = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    confirm = os.environ.get("CONFIRM_DELETE", "").strip()

    if confirm != "DELETE":
        print('refusing: set CONFIRM_DELETE="DELETE" to proceed', file=sys.stderr)
        sys.exit(1)
    if not handle or not password:
        print("missing BLUESKY_HANDLE or BLUESKY_APP_PASSWORD", file=sys.stderr)
        sys.exit(1)

    session = login(handle, password)
    did = session["did"]
    token = session["accessJwt"]
    auth = {"Authorization": f"Bearer {token}"}

    deleted = 0
    cursor = None
    while True:
        params = {"repo": did, "collection": "app.bsky.feed.post", "limit": 100}
        if cursor:
            params["cursor"] = cursor
        lr = requests.get(f"{PDS}/xrpc/com.atproto.repo.listRecords",
                          params=params, timeout=30)
        lr.raise_for_status()
        data = lr.json()
        records = data.get("records", [])
        if not records:
            break
        for rec in records:
            rkey = rec["uri"].rsplit("/", 1)[-1]
            try:
                dr = requests.post(f"{PDS}/xrpc/com.atproto.repo.deleteRecord",
                                   headers=auth,
                                   json={"repo": did,
                                         "collection": "app.bsky.feed.post",
                                         "rkey": rkey}, timeout=30)
                dr.raise_for_status()
                deleted += 1
                if deleted % 25 == 0:
                    print(f"deleted {deleted}...")
                time.sleep(0.3)  # gentle on the rate limit
            except Exception as e:
                print(f"failed to delete {rkey}: {e}", file=sys.stderr)
        cursor = data.get("cursor")
        # listRecords keeps returning the same page as we delete from the top,
        # so we don't rely on cursor alone — loop until a page comes back empty.

    print(f"done — deleted {deleted} post(s)")


if __name__ == "__main__":
    main()
