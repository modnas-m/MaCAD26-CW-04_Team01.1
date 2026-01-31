"""
Create a model inside session03 folder
"""
from main import get_client
from gql import gql

WORKSPACE_ID = "a1cd06bae2"
PROJECT_ID = "128262a20c"  # CW26-Sessions project ID

def main():
    client = get_client()

    # Create a model inside the specific path
    mutation = gql("""
    mutation CreateModel($input: CreateModelInput!) {
      modelMutations {
        create(input: $input) {
          id
          name
        }
      }
    }
    """)
    
    params = {
        "input": {
            "projectId": PROJECT_ID,
            "name": "homework/session03/Team_01.1",
            "description": "The Bean is learning specklepy"
        }
    }
    
    result = client.httpclient.execute(mutation, params)
    
    # Debug: print the full result
    print("Full result:", result)
    
    if "errors" in result:
        print("Errors:", result["errors"])
        return
    
    model = result["data"]["modelMutations"]["create"]
    
    print(f"✓ Created model: {model['id']}")
    print(f"  Model name: {model['name']}")
    print(f"  URL: https://app.speckle.systems/projects/{PROJECT_ID}/models/{model['name']}")

if __name__ == "__main__":
    main()