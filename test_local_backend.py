import os
import json

# Set mandatory mock environments so the script can boot up safely
os.environ["UPLOAD_BUCKET"] = "dummy-sandbox-bucket"
os.environ["TABLE_NAME"] = "dummy-sandbox-table"
os.environ["SES_SENDER_EMAIL"] = "test@example.com"
os.environ["API_URL"] = "http://localhost"

# Import your freshly fixed submission script code
from backend.submission.app import create_submission

# Simulate the exact payload data your curl command was trying to send
mock_event = {
    "body": json.dumps({
        "email": "test@example.com",
        "fileName": "partie.txt"
    })
}

print("Executing 'create_submission' locally with mock event wrapper...")
result = create_submission(mock_event)

print("\n--- RESPONSE FROM BACKEND ---")
print(json.dumps(result, indent=4))
