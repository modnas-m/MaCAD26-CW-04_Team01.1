"""
Create a model inside session03 folder using SpecklePy SDK
"""
from main import get_client
from specklepy.core.api.inputs.model_inputs import CreateModelInput

PROJECT_ID = "128262a20c"
MODEL_NAME = "homework/session03/team_01.1check"
MODEL_DESCRIPTION = "The Bean is learning specklepy"


def main():
    client = get_client()

    model = client.model.create(CreateModelInput(
        project_id=PROJECT_ID,
        name=MODEL_NAME,
        description=MODEL_DESCRIPTION
    ))

    print(f"✓ Created model: {model.id}")
    print(f"  Name: {model.name}")
    print(f"  URL: https://app.speckle.systems/projects/{PROJECT_ID}/models/{model.id}")


if __name__ == "__main__":
    main()