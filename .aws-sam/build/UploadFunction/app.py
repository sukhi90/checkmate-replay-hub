import os
import json
import uuid
import base64
import secrets
from datetime import datetime, timezone, timedelta

import boto3

s3 = boto3.client("s3")
ddb = boto3.resource("dynamodb")
ses = boto3.client("sesv2")

TABLE = ddb.Table(os.environ["TABLE_NAME"])
BUCKET = os.environ["BUCKET_NAME"]
FROM_EMAIL = os.environ["SES_FROM_EMAIL"]
PUBLIC_URL = os.environ["PUBLIC_URL"]


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
        },
        "body": json.dumps(body)
    }


def send_email(to, subject, body):
    ses.send_email(
        FromEmailAddress=FROM_EMAIL,
        Destination={"ToAddresses": [to]},
        Content={
            "Simple": {
                "Subject": {
                    "Data": subject,
                    "Charset": "UTF-8"
                },
                "Body": {
                    "Text": {
                        "Data": body,
                        "Charset": "UTF-8"
                    }
                }
            }
        }
    )


def upload(event):
    try:
        body = json.loads(event.get("body") or "{}")

        email = body.get("email", "").strip()
        filename = body.get("filename", "partie.txt")
        content = body.get("content", "")

        if not email:
            return response(400, {
                "status": "ERROR",
                "message": "Email address is required."
            })

        if not content:
            return response(400, {
                "status": "ERROR",
                "message": "Chess file is empty."
            })

        if len(content) > 1000000:
            return response(400, {
                "status": "ERROR",
                "message": "File is too large."
            })

        submission_id = str(uuid.uuid4())

        token = secrets.token_urlsafe(32)

        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=24)

        s3_key = f"uploads/{submission_id}/{filename}"

        s3.put_object(
            Bucket=BUCKET,
            Key=s3_key,
            Body=content.encode("utf-8"),
            ContentType="text/plain",
            ServerSideEncryption="AES256"
        )

        TABLE.put_item(
            Item={
                "submissionId": submission_id,
                "email": email,
                "filename": filename,
                "s3Key": s3_key,
                "status": "AWAITING_CONFIRMATION",
                "confirmationToken": token,
                "tokenExpiresAt": expires.isoformat(),
                "createdAt": now.isoformat()
            }
        )

        confirm_url = (
            f"{PUBLIC_URL}/confirm"
            f"?submissionId={submission_id}"
            f"&token={token}"
        )

        send_email(
            email,
            "Checkmate Replay Hub - Confirm your submission",
            f"""Your chess file was uploaded successfully.

Please confirm your submission by clicking this link:

{confirm_url}

This confirmation link can only be used once and expires in 24 hours.
"""
        )

        return response(200, {
            "status": "AWAITING_CONFIRMATION",
            "submissionId": submission_id
        })

    except Exception as exc:
        print("UPLOAD ERROR:", repr(exc))
        return response(500, {
            "status": "ERROR",
            "message": "Upload failed."
        })


def confirm(event):
    try:
        params = event.get("queryStringParameters") or {}

        submission_id = params.get("submissionId")
        token = params.get("token")

        if not submission_id or not token:
            return response(400, {
                "status": "ERROR",
                "message": "Missing confirmation information."
            })

        result = TABLE.get_item(
            Key={"submissionId": submission_id}
        )

        item = result.get("Item")

        if not item:
            return response(404, {
                "status": "ERROR",
                "message": "Submission not found."
            })

        if item.get("status") != "AWAITING_CONFIRMATION":
            return response(400, {
                "status": "ERROR",
                "message": "This confirmation link has already been used or the submission is no longer awaiting confirmation."
            })

        if not secrets.compare_digest(
            str(item.get("confirmationToken", "")),
            str(token)
        ):
            return response(400, {
                "status": "ERROR",
                "message": "Invalid confirmation link."
            })

        expiry = datetime.fromisoformat(
            item["tokenExpiresAt"].replace("Z", "+00:00")
        )

        if datetime.now(timezone.utc) > expiry:
            return response(400, {
                "status": "ERROR",
                "message": "Confirmation link has expired."
            })

        now = datetime.now(timezone.utc).isoformat()

        # Atomic condition: only the first valid request can confirm it.
        TABLE.update_item(
            Key={"submissionId": submission_id},
            UpdateExpression="""
                SET #s = :processing,
                    confirmedAt = :now
                REMOVE confirmationToken, tokenExpiresAt
            """,
            ExpressionAttributeNames={
                "#s": "status"
            },
            ExpressionAttributeValues={
                ":processing": "PROCESSING",
                ":now": now
            },
            ConditionExpression="#s = :awaiting",
        )

        return {
            "statusCode": 302,
            "headers": {
                "Location": f"{PUBLIC_URL}/?confirmed=1"
            },
            "body": ""
        }

    except Exception as exc:
        print("CONFIRM ERROR:", repr(exc))

        return response(400, {
            "status": "ERROR",
            "message": "Invalid or already-used confirmation link."
        })


def lambda_handler(event, context):
    method = (
        event.get("requestContext", {})
        .get("http", {})
        .get("method", "")
    )

    path = event.get("rawPath", "")

    if method == "OPTIONS":
        return response(200, {"ok": True})

    if path.endswith("/upload") and method == "POST":
        return upload(event)

    if path.endswith("/confirm") and method == "GET":
        return confirm(event)

    return response(404, {
        "status": "ERROR",
        "message": "Route not found."
    })
