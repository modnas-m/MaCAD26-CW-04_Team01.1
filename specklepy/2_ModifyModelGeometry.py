from specklepy.api.client import SpeckleClient
from specklepy.api.credentials import get_default_account
from specklepy.transports.server import ServerTransport
from specklepy.api import operations
from specklepy.core.api.inputs.version_inputs import CreateVersionInput
import copy

PROJECT_ID = "128262a20c"
MODEL_ID = "0fc383dd86"
Z_OFFSET = 16


def get_prop_ci(obj, name):
    """Get dynamic member by name (case-insensitive). Returns (actual_name, value) or (None, None)."""
    if hasattr(obj, name):
        return name, getattr(obj, name)

    if hasattr(obj, "get_dynamic_member_names"):
        wanted = name.lower()
        for n in obj.get_dynamic_member_names():
            if str(n).lower() == wanted:
                return n, getattr(obj, n)

    return None, None


def set_prop_ci(obj, name, value):
    """Set dynamic member preserving existing casing if it exists."""
    actual, _ = get_prop_ci(obj, name)
    setattr(obj, actual or name, value)


def shift_z(obj, dz):
    """Best-effort: shift displayValue mesh vertices + bbox + point-like .z."""
    if hasattr(obj, "displayValue") and obj.displayValue:
        meshes = obj.displayValue if isinstance(obj.displayValue, list) else [obj.displayValue]
        for m in meshes:
            if hasattr(m, "vertices") and m.vertices:
                verts = list(m.vertices)  # [x,y,z,x,y,z,...]
                for i in range(2, len(verts), 3):
                    verts[i] += dz
                m.vertices = verts

    if hasattr(obj, "bbox") and obj.bbox:
        try:
            obj.bbox.min.z += dz
            obj.bbox.max.z += dz
        except Exception:
            pass

    if hasattr(obj, "z"):
        try:
            obj.z += dz
        except Exception:
            pass


def find_first_module_01(root):
    """DFS through lists + dynamic members. Returns (obj, parent_list, index) or (None,None,None)."""
    seen = set()

    def walk(o, parent=None, idx=None):
        if o is None:
            return None, None, None
        oid = id(o)
        if oid in seen:
            return None, None, None
        seen.add(oid)

        _, v = get_prop_ci(o, "Module")
        if v is not None and str(v) == "01":
            return o, parent, idx

        if isinstance(o, list):
            for i, item in enumerate(o):
                r = walk(item, o, i)
                if r[0] is not None:
                    return r
            return None, None, None

        if hasattr(o, "get_dynamic_member_names"):
            for n in o.get_dynamic_member_names():
                try:
                    child = getattr(o, n)
                except Exception:
                    continue
                r = walk(child, None, None)
                if r[0] is not None:
                    return r

        return None, None, None

    return walk(root)


def get_latest_referenced_object_id(client, project_id, model_id):
    query = """
    query LatestVersion($projectId: String!, $modelId: String!) {
      project(id: $projectId) {
        model(id: $modelId) {
          versions(limit: 1) {
            items {
              referencedObject
            }
          }
        }
      }
    }
    """

    res = client.execute_query(
        query,
        variables={"projectId": project_id, "modelId": model_id}
    )

    items = (
        res.get("project", {})
           .get("model", {})
           .get("versions", {})
           .get("items", [])
    )

    if not items:
        raise RuntimeError("No versions found for this model.")

    return items[0]["referencedObject"]


def main():
    account = get_default_account()
    client = SpeckleClient(host=account.serverInfo.url)
    client.authenticate_with_account(account)

    ref_obj_id = get_latest_referenced_object_id(client, PROJECT_ID, MODEL_ID)

    transport = ServerTransport(stream_id=PROJECT_ID, client=client)
    base = operations.receive(obj_id=ref_obj_id, remote_transport=transport)
    print("Received data from Speckle")

    target, parent_list, parent_index = find_first_module_01(base)
    if target is None:
        raise RuntimeError('No object found with property Module == "01".')

    copied = copy.deepcopy(target)
    set_prop_ci(copied, "Module", "02")
    shift_z(copied, Z_OFFSET)

    # insert right next to original if possible; else try base.elements
    if isinstance(parent_list, list) and isinstance(parent_index, int):
        parent_list.insert(parent_index + 1, copied)
    elif hasattr(base, "elements") and isinstance(base.elements, list):
        base.elements.append(copied)
    else:
        raise RuntimeError("Could not re-insert the copied object (no parent list and no base.elements).")

    new_obj_id = operations.send(base=base, transports=[transport])

    new_version = client.version.create(
        CreateVersionInput(
            project_id=PROJECT_ID,
            model_id=MODEL_ID,
            object_id=new_obj_id,
            message="Copy Module 01 -> Module 02, shift +16Z"
        )
    )

    print("✓ Created new version:", new_version.id)
    print(f"URL: {account.serverInfo.url}/projects/{PROJECT_ID}/models/{MODEL_ID}@{new_version.id}")


if __name__ == "__main__":
    main()
