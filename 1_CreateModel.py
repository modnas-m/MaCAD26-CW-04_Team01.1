"""
01 - Create a Speckle Model inside an existing Project and Folder

NOTE: Project workspace in this case is: 128262a20c
"""
from specklepy.api.client import SpeckleClient
from specklepy.api.credentials import get_default_account
from specklepy.core.api.inputs.model_inputs import CreateModelInput

def main():
    account = get_default_account()

    # IMPORTANT: connect to the same server as the account
    client = SpeckleClient(host=account.serverInfo.url)
    client.authenticate_with_account(account)

    project_id = "128262a20c"

    model_name = "homework/session03/team_01.1checkk"

    model = client.model.create(
        CreateModelInput(
            project_id=project_id,
            name=model_name,
            description="Model created in homework/session03"
        )
    )

    print("✅ Model created")
    print("Server:", account.serverInfo.url)
    print("Project:", project_id)
    print("Model:", model.name)
    print("Model ID:", model.id)
    print(f"URL: {account.serverInfo.url}/projects/{project_id}/models/{model.id}")

if __name__ == "__main__":
    main()

