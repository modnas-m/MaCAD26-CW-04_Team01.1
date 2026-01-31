"""
Homework Session 03 - SpecklePy
- Load geometry from source model and create 3 modules
- Organize into "New_Modules" and "Old_Modules" collections
- Add "Tower" and "Designer" properties
"""
from specklepy.api.client import SpeckleClient
from specklepy.api.credentials import get_default_account
from specklepy.transports.server import ServerTransport
from specklepy.api import operations
from specklepy.core.api.inputs.version_inputs import CreateVersionInput
from specklepy.objects.base import Base
from gql import gql
import copy

PROJECT_ID = "128262a20c"
SOURCE_MODEL_ID = "a1014e4b32"
TARGET_GEOMETRY_ID = "c859d4998f1f91f9afe2e5c0af23d94c"
Z_OFFSET = 16000
DESIGNERS = ["Maria Sanchez", "Lakzhmy Zaro", "Emilie El Chidiac"]


def shift_z_recursive(obj, dz, seen=None):
    if seen is None:
        seen = set()
    if obj is None or id(obj) in seen:
        return
    seen.add(id(obj))

    if hasattr(obj, "displayValue") and obj.displayValue:
        meshes = obj.displayValue if isinstance(obj.displayValue, list) else [obj.displayValue]
        for m in meshes:
            if hasattr(m, "vertices") and m.vertices:
                verts = list(m.vertices)
                for i in range(2, len(verts), 3):
                    verts[i] += dz
                m.vertices = verts

    if hasattr(obj, "bbox") and obj.bbox:
        try:
            if obj.bbox.min: obj.bbox.min.z += dz
            if obj.bbox.max: obj.bbox.max.z += dz
        except: pass

    if hasattr(obj, "z"):
        try: obj.z += dz
        except: pass

    if isinstance(obj, list):
        for item in obj:
            shift_z_recursive(item, dz, seen)
    elif hasattr(obj, "get_dynamic_member_names"):
        for name in obj.get_dynamic_member_names():
            try: shift_z_recursive(getattr(obj, name), dz, seen)
            except: pass


def get_latest_ref_obj_id(client, project_id, model_id):
    query = gql(f'''query {{ project(id: "{project_id}") {{ model(id: "{model_id}") {{ versions(limit: 1) {{ items {{ referencedObject }} }} }} }} }}''')
    res = client.httpclient.execute(query)
    return res["project"]["model"]["versions"]["items"][0]["referencedObject"]


def find_model_by_name(client, project_id, model_name):
    query = gql(f'''query {{ project(id: "{project_id}") {{ models(limit: 100) {{ items {{ id name }} }} }} }}''')
    res = client.httpclient.execute(query)
    for model in res["project"]["models"]["items"]:
        if model_name.lower() in model["name"].lower():
            return model["id"], model["name"]
    return None, None


def create_collection(name, elements):
    c = Base()
    c.speckle_type = "Speckle.Core.Models.Collections.Collection"
    c.name = name
    c.collectionType = "Collection"
    c.elements = elements
    return c


def create_brep_with_props(geometry, num, designer, z_shift=0):
    geom = copy.deepcopy(geometry[0])  # Get the single BrepX
    if z_shift:
        shift_z_recursive(geom, z_shift)
    # Add Designer property to BrepX and its properties dict
    geom.Designer = designer
    geom.Module = f"{num:02d}"
    if hasattr(geom, "properties") and isinstance(geom.properties, dict):
        geom.properties["Designer"] = designer
        geom.properties["Module"] = f"{num:02d}"
    return geom


def main():
    account = get_default_account()
    client = SpeckleClient(host=account.serverInfo.url)
    client.authenticate_with_account(account)

    target_model_id, target_model_name = find_model_by_name(client, PROJECT_ID, "team_01.1checkk")
    if not target_model_id:
        print("ERROR: Model 'team_01.1checkk' not found")
        return

    transport = ServerTransport(stream_id=PROJECT_ID, client=client)
    source_base = operations.receive(obj_id=get_latest_ref_obj_id(client, PROJECT_ID, SOURCE_MODEL_ID), remote_transport=transport)

    source_geometry = [e for e in source_base.elements[0].elements if hasattr(e, "id") and e.id == TARGET_GEOMETRY_ID]
    if not source_geometry:
        print(f"ERROR: Geometry {TARGET_GEOMETRY_ID} not found")
        return

    # Create BrepX elements with properties for each module
    brep_01 = create_brep_with_props(source_geometry, 1, DESIGNERS[0])
    brep_02 = create_brep_with_props(source_geometry, 2, DESIGNERS[1], Z_OFFSET)
    brep_03 = create_brep_with_props(source_geometry, 3, DESIGNERS[2], Z_OFFSET * 2)

    # Old_Modules contains BrepX from Module_01 and Module_03
    # New_Modules contains BrepX from Module_02
    old_modules = create_collection("Old_Modules", [brep_01, brep_03])
    new_modules = create_collection("New_Modules", [brep_02])

    root = Base()
    root.speckle_type = "Speckle.Core.Models.Collections.Collection"
    root.name = "Tower"
    root.collectionType = "Tower"
    root.Tower = "Team-01.1"
    root.elements = [old_modules, new_modules]
    root.units = "mm"

    new_obj_id = operations.send(base=root, transports=[transport])
    new_version = client.version.create(CreateVersionInput(
        project_id=PROJECT_ID, model_id=target_model_id, object_id=new_obj_id,
        message="Homework Session 03: 3 modules with Tower and Designer properties"
    ))

    print(f"Success! URL: {account.serverInfo.url}/projects/{PROJECT_ID}/models/{target_model_id}@{new_version.id}")


if __name__ == "__main__":
    main()
