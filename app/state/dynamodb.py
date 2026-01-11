# app/state/dynamodb.py
import boto3
import json

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("financial-agent-sessions")

def save_state(session_id: str, state: dict):
    table.put_item(
        Item={
            "session_id": session_id,
            "state": json.dumps(state)
        }
    )

def load_state(session_id: str):
    resp = table.get_item(Key={"session_id": session_id})
    return json.loads(resp["Item"]["state"]) if "Item" in resp else {}
