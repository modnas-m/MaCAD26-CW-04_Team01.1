"""
07 - Listen for Speckle project updates and backup JSON snapshots

- Subscribe to projectVersionsUpdated (WS)
- On each update:
  - fetch version.referencedObject (HTTP GraphQL)
  - fetch object.data (HTTP GraphQL)
  - write a timestamped JSON file to disk
"""

import asyncio
import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from gql import gql, Client
from gql.transport.websockets import WebsocketsTransport

from specklepy.api.client import SpeckleClient

# -----------------------
# Config
# -----------------------
load_dotenv()

SPECKLE_SERVER_HTTP = "https://app.speckle.systems"
SPECKLE_SERVER_WS = "wss://app.speckle.systems/graphql"

YOUR_TOKEN = os.environ.get("SPECKLE_TOKEN")
PROJECT_ID = "08c875bbe4"  # HB01 Program Model (project)

# Where backups go (relative to this script)
BACKUP_DIRNAME = "speckle_backups"

# -----------------------
# GraphQL documents
# -----------------------

SUB_PROJECT_VERSIONS_UPDATED = gql("""
subscription ProjectVersionsUpdated($projectId: String!) {
  projectVersionsUpdated(id: $projectId) {
    id
    modelId
    type
    version {
      id
      message
      createdAt
    }
  }
}
""")

# We fetch referencedObject from the Version/Commit.
# (Speckle schema calls it "Commit" in some references, but "Version" in UI; field is referencedObject.)
Q_VERSION_REFERENCED_OBJECT = """
query GetVersionRootObject($projectId: String!, $versionId: String!) {
  project(id: $projectId) {
    version(id: $versionId) {
      id
      referencedObject
      message
      createdAt
      authorUser {
        id
        name
        email
      }
    }
  }
}
"""

Q_OBJECT_DATA = """
query GetObjectData($projectId: String!, $objectId: String!) {
  project(id: $projectId) {
    object(id: $objectId) {
      id
      speckleType
      data
    }
  }
}
"""

# -----------------------
# Helpers
# -----------------------

def _safe_timestamp(dt: datetime) -> str:
    """Filesystem-safe timestamp."""
    return dt.strftime("%Y-%m-%d_%H-%M-%S")

def _ensure_backup_dir(script_dir: str) -> str:
    path = os.path.join(script_dir, BACKUP_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path

def _write_backup_json(script_dir: str, payload: dict, received_at: datetime) -> str:
    backup_dir = _ensure_backup_dir(script_dir)
    filename = f"{_safe_timestamp(received_at)}.json"
    filepath = os.path.join(backup_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)

    return filepath

def _speckle_http_client() -> SpeckleClient:
    if not YOUR_TOKEN:
        raise RuntimeError("Missing SPECKLE_TOKEN in your environment (.env).")

    client = SpeckleClient(host=SPECKLE_SERVER_HTTP)
    client.authenticate_with_token(YOUR_TOKEN)
    return client

def _get_version_root_object_and_author(http_client: SpeckleClient, project_id: str, version_id: str) -> dict:
    res = http_client.execute_query(
        Q_VERSION_REFERENCED_OBJECT,
        {"projectId": project_id, "versionId": version_id},
    )
    # SpeckleClient.execute_query returns the "data dict" directly
    ver = res["project"]["version"]
    if not ver or not ver.get("referencedObject"):
        raise RuntimeError(f"Could not resolve referencedObject for version {version_id}")
    return ver

def _get_object_data(http_client: SpeckleClient, project_id: str, object_id: str) -> dict:
    res = http_client.execute_query(
        Q_OBJECT_DATA,
        {"projectId": project_id, "objectId": object_id},
    )
    obj = res["project"]["object"]
    if not obj or "data" not in obj:
        raise RuntimeError(f"Could not fetch object.data for object {object_id}")
    return obj

# -----------------------
# Main async loop
# -----------------------

async def subscribe_and_backup():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    http_client = _speckle_http_client()
    me = getattr(getattr(http_client, "account", None), "userInfo", None)

    print("✓ HTTP client authenticated"
          + (f" as {me.name}" if me and getattr(me, "name", None) else ""))

    transport = WebsocketsTransport(
        url=SPECKLE_SERVER_WS,
        init_payload={"Authorization": f"Bearer {YOUR_TOKEN}"},
    )

    ws_client = Client(transport=transport, fetch_schema_from_transport=False)

    try:
        async with ws_client as session:
            print(f"🔌 Connected (WS) to {SPECKLE_SERVER_WS}")
            print(f"📡 Listening for updates on project: {PROJECT_ID}")
            print("Press Ctrl+C to stop\n")

            async for result in session.subscribe(
                SUB_PROJECT_VERSIONS_UPDATED,
                variable_values={"projectId": PROJECT_ID},
            ):
                received_at = datetime.now(timezone.utc)

                evt = (result or {}).get("projectVersionsUpdated") or {}
                ver_meta = evt.get("version") or {}

                version_id = ver_meta.get("id")
                message = ver_meta.get("message")
                created_at = ver_meta.get("createdAt")
                model_id = evt.get("modelId")
                event_type = evt.get("type")

                if not version_id:
                    print("⚠ Update received but no version.id found; skipping.")
                    continue

                print("=" * 60)
                print("📦 Update received")
                print(f"  - modelId: {model_id}")
                print(f"  - versionId: {version_id}")
                print(f"  - type: {event_type}")
                print(f"  - message: {message}")
                print(f"  - createdAt: {created_at}")

                try:
                    # 1) Resolve the root object for this version
                    version_info = _get_version_root_object_and_author(http_client, PROJECT_ID, version_id)
                    root_object_id = version_info["referencedObject"]
                    author = version_info.get("authorUser") or {}

                    # 2) Fetch object.data
                    obj = _get_object_data(http_client, PROJECT_ID, root_object_id)

                    # 3) Build backup payload
                    backup_payload = {
                        "projectId": PROJECT_ID,
                        "modelId": model_id,
                        "versionId": version_id,
                        "rootObjectId": root_object_id,
                        "commitMessage": message,
                        "createdAt": created_at,
                        "receivedAt": received_at.isoformat(),
                        "author": {
                            "id": author.get("id"),
                            "name": author.get("name"),
                            "email": author.get("email"),
                        },
                        "object": {
                            "id": obj.get("id"),
                            "speckleType": obj.get("speckleType"),
                            "data": obj.get("data"),
                        },
                    }

                    # 4) Write timestamped file
                    outpath = _write_backup_json(script_dir, backup_payload, received_at)
                    print(f"✅ Backup written: {outpath}")

                except Exception as e:
                    print(f"❌ Backup failed for version {version_id}: {e}")

    except KeyboardInterrupt:
        print("\n👋 Subscription stopped by user")
    finally:
        await transport.close()
        print("🔌 Connection closed")

if __name__ == "__main__":
    asyncio.run(subscribe_and_backup())
