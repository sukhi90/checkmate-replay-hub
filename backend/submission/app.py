import os
import json
import re
import uuid
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

import boto3
from botocore.exceptions import ClientError


# ---------------------------------------------------------
# AWS clients
# ---------------------------------------------------------

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
ses = boto3.client("ses")


# ---------------------------------------------------------
# Environment variables
# ---------------------------------------------------------

UPLOAD_BUCKET = os.environ["UPLOAD_BUCKET"]
TABLE_NAME = os.environ["TABLE_NAME"]
SES_SENDER_EMAIL = os.environ["SES_SENDER_EMAIL"]
API_URL = os.environ["API_URL"]

table = dynamodb.Table(TABLE_NAME)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def response(status_code, body, headers=None):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "content-type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            **(headers or {}),
        },
        "body": json.dumps(body),
    }


def html_response(status_code, title, message):
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>

    <style>
        body {{
            font-family: Arial, sans-serif;
            background: #f4f6f8;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }}

        .card {{
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.10);
            max-width: 600px;
            text-align: center;
        }}

        h1 {{
            margin-bottom: 15px;
        }}

        p {{
            color: #555;
            line-height: 1.6;
        }}
    </style>
</head>

<body>
    <div class="card">
        <h1>{title}</h1>
        <p>{message}</p>
    </div>
</body>
</html>
"""

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
        },
        "body": html,
    }


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def validate_email(email):
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    return bool(re.match(pattern, email))


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------
# M3 - Send confirmation email
# ---------------------------------------------------------

def send_confirmation_email(email, submission_id, token):

    confirmation_url = (
        f"{API_URL}/confirm/{quote(token, safe='')}"
    )

    subject = "Checkmate Replay Hub - Confirm your submission"

    text_body = f"""
Hello,

Your chess replay file has been uploaded successfully.

Submission ID:
{submission_id}

Please confirm your submission by clicking this link:

{confirmation_url}

This confirmation link can only be used once.

After confirmation, your submission will move to PROCESSING.

If you did not submit this file, you can ignore this email.

Checkmate Replay Hub
"""

    html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">

<h2>Checkmate Replay Hub</h2>

<p>Your chess replay file has been uploaded successfully.</p>

<p>
<strong>Submission ID:</strong><br>
{submission_id}
</p>

<p>
Please confirm your submission by clicking the button below:
</p>

<p>
<a href="{confirmation_url}"
   style="
   display:inline-block;
   padding:12px 20px;
   background:#2563eb;
   color:white;
   text-decoration:none;
   border-radius:6px;">
   Confirm Submission
</a>
</p>

<p>
This confirmation link can only be used once.
</p>

<p>
After confirmation, your submission will move to
<strong>PROCESSING</strong>.
</p>

<p>
If you did not submit this file, you can ignore this email.
</p>

<hr>

<p>Checkmate Replay Hub</p>

</body>
</html>
"""

print("⚠️ Sandbox Mode: SES Bypassed")
    # ses.send_email(
    #     Source=SES_SENDER_EMAIL,
    #     Destination={
    #         "ToAddresses": [email]
    #     },
    #     Message={
    #         "Subject": {
    #             "Data": subject,
    #             "Charset": "UTF-8"
    #         },
    #         "Body": {
    #             "Text": {
    #                 "Data": text_body,
    #                 "Charset": "UTF-8"
    #             },
    #             "Html": {
    #                 "Data": html_body,
    #                 "Charset": "UTF-8"
    #             }
    #         }
    #     }
    # )
print("⚠️ Sandbox Mode: SES is disabled. Skipping email sending.")


# ---------------------------------------------------------
# POST /submissions
# ---------------------------------------------------------

def create_submission(event):

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return response(
            400,
            {"error": "Invalid JSON request"}
        )

    email = body.get("email", "").strip()
    file_name = body.get("fileName", "").strip()

    if not validate_email(email):
        return response(
            400,
            {"error": "Invalid email address"}
        )

    if not file_name.lower().endswith(".txt"):
        return response(
            400,
            {"error": "Only .txt files are allowed"}
        )

    submission_id = str(uuid.uuid4())

    safe_file_name = os.path.basename(file_name)

    s3_key = (
        f"submissions/{submission_id}/{safe_file_name}"
    )

    item = {
        "submissionId": submission_id,
        "email": email,
        "fileName": safe_file_name,
        "s3Key": s3_key,
        "status": "UPLOADING",
        "createdAt": now_iso()
    }

    table.put_item(Item=item)

    upload_url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": UPLOAD_BUCKET,
            "Key": s3_key,
            "ContentType": "text/plain"
        },
        ExpiresIn=900
    )

    return response(
        200,
        {
            "submissionId": submission_id,
            "uploadUrl": upload_url,
            "status": "UPLOADING"
        }
    )


# ---------------------------------------------------------
# POST /submissions/{submissionId}/complete
# ---------------------------------------------------------

def complete_submission(event):

    submission_id = (
        event.get("pathParameters", {}) or {}
    ).get("submissionId")

    if not submission_id:
        return response(
            400,
            {"error": "Missing submissionId"}
        )

    result = table.get_item(
        Key={
            "submissionId": submission_id
        }
    )

    item = result.get("Item")

    if not item:
        return response(
            404,
            {"error": "Submission not found"}
        )

    try:

        s3.head_object(
            Bucket=UPLOAD_BUCKET,
            Key=item["s3Key"]
        )

    except ClientError:
        return response(
            400,
            {
                "error": "Uploaded file was not found"
            }
        )

    # -----------------------------------------------------
    # Generate cryptographically secure one-time token
    # -----------------------------------------------------

    token = secrets.token_urlsafe(32)

    token_hash = hash_token(token)

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(hours=24)
    ).isoformat()

    # -----------------------------------------------------
    # Save confirmation token
    # -----------------------------------------------------

    table.update_item(
        Key={
            "submissionId": submission_id
        },
        UpdateExpression="""
            SET #status = :status,
                confirmationTokenHash = :token_hash,
                confirmationExpiresAt = :expires_at
        """,
        ExpressionAttributeNames={
            "#status": "status"
        },
        ExpressionAttributeValues={
            ":status": "AWAITING_CONFIRMATION",
            ":token_hash": token_hash,
            ":expires_at": expires_at
        }
    )

    # -----------------------------------------------------
    # Send email
    # -----------------------------------------------------

    try:

        send_confirmation_email(
            item["email"],
            submission_id,
            token
        )

    except Exception as e:

        print(
            f"SES email error for {submission_id}: {str(e)}"
        )

        # Keep submission in a safe state.
        table.update_item(
            Key={
                "submissionId": submission_id
            },
            UpdateExpression="""
                SET #status = :status
            """,
            ExpressionAttributeNames={
                "#status": "ERROR"
            },
            ExpressionAttributeValues={
                ":status": "ERROR"
            }
        )

        return response(
            500,
            {
                "error": "Could not send confirmation email"
            }
        )

    return response(
        200,
        {
            "submissionId": submission_id,
            "status": "AWAITING_CONFIRMATION"
        }
    )


# ---------------------------------------------------------
# GET /confirm/{token}
# ---------------------------------------------------------

def confirm_submission(event):

    token = (
        event.get("pathParameters", {}) or {}
    ).get("token")

    if not token:
        return html_response(
            400,
            "Invalid confirmation link",
            "The confirmation link is missing or invalid."
        )

    token_hash = hash_token(token)

    # -----------------------------------------------------
    # Find submission using DynamoDB scan.
    #
    # For this student project this keeps the data model
    # simple. M4 can later improve this if desired.
    # -----------------------------------------------------

    result = table.scan(
        FilterExpression=(
            "confirmationTokenHash = :token_hash"
        ),
        ExpressionAttributeValues={
            ":token_hash": token_hash
        }
    )

    items = result.get("Items", [])

    if not items:

        return html_response(
            400,
            "Link already used or invalid",
            "This confirmation link is invalid or has already been used."
        )

    item = items[0]

    submission_id = item["submissionId"]

    # -----------------------------------------------------
    # Check expiry
    # -----------------------------------------------------

    expires_at = item.get("confirmationExpiresAt")

    if not expires_at:

        return html_response(
            400,
            "Invalid confirmation link",
            "This confirmation link is no longer valid."
        )

    try:

        expiry = datetime.fromisoformat(
            expires_at.replace("Z", "+00:00")
        )

        if datetime.now(timezone.utc) >= expiry:

            table.update_item(
                Key={
                    "submissionId": submission_id
                },
                UpdateExpression="""
                    SET #status = :status
                    REMOVE confirmationTokenHash,
                           confirmationExpiresAt
                """,
                ExpressionAttributeNames={
                    "#status": "status"
                },
                ExpressionAttributeValues={
                    ":status": "ERROR"
                }
            )

            return html_response(
                400,
                "Confirmation link expired",
                "This confirmation link has expired. Please submit the chess file again."
            )

    except ValueError:

        return html_response(
            400,
            "Invalid confirmation link",
            "The confirmation link contains an invalid expiration time."
        )

    # -----------------------------------------------------
    # One-time atomic confirmation
    # -----------------------------------------------------

    try:

        table.update_item(
            Key={
                "submissionId": submission_id
            },

            UpdateExpression="""
                SET #status = :processing,
                    confirmedAt = :confirmed_at
                REMOVE confirmationTokenHash,
                       confirmationExpiresAt
            """,

            ConditionExpression=(
                "#status = :awaiting "
                "AND confirmationTokenHash = :token_hash"
            ),

            ExpressionAttributeNames={
                "#status": "status"
            },

            ExpressionAttributeValues={
                ":processing": "PROCESSING",
                ":awaiting": "AWAITING_CONFIRMATION",
                ":token_hash": token_hash,
                ":confirmed_at": now_iso()
            }
        )

    except ClientError as e:

        if (
            e.response["Error"]["Code"]
            == "ConditionalCheckFailedException"
        ):

            return html_response(
                400,
                "Link already used",
                "This confirmation link has already been used or is no longer valid."
            )

        print(
            f"Confirmation error: {str(e)}"
        )

        return html_response(
            500,
            "Confirmation failed",
            "The confirmation could not be completed. Please try again."
        )

    return html_response(
        200,
        "Submission confirmed",
        f"""
        Your submission has been successfully confirmed.

        <br><br>

        Submission ID:
        <strong>{submission_id}</strong>

        <br><br>

        Current status:
        <strong>PROCESSING</strong>

        <br><br>

        The chess processing will be handled in the next milestone.
        """
    )


# ---------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------

def lambda_handler(event, context):

    print(
        json.dumps(
            event,
            default=str
        )
    )

    request_context = event.get(
        "requestContext",
        {}
    )

    http_info = request_context.get(
        "http",
        {}
    )

    method = http_info.get(
        "method",
        event.get("httpMethod", "")
    )

    path = event.get(
        "rawPath",
        event.get("path", "")
    )

    # -----------------------------------------------------
    # CORS preflight
    # -----------------------------------------------------

    if method == "OPTIONS":

        return response(
            200,
            {"message": "OK"}
        )

    # -----------------------------------------------------
    # POST /submissions
    # -----------------------------------------------------

    if (
        method == "POST"
        and path == "/submissions"
    ):

        return create_submission(event)

    # -----------------------------------------------------
    # POST /submissions/{submissionId}/complete
    # -----------------------------------------------------

    if (
        method == "POST"
        and path.startswith("/submissions/")
        and path.endswith("/complete")
    ):

        return complete_submission(event)

    # -----------------------------------------------------
    # GET /confirm/{token}
    # -----------------------------------------------------

    if (
        method == "GET"
        and path.startswith("/confirm/")
    ):

        return confirm_submission(event)

    return response(
        404,
        {
            "error": "Route not found"
        }
    )
