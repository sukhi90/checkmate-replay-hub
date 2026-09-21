import json
import os
import re
import uuid
from datetime import datetime, timezone

import boto3


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

s3 = boto3.client("s3")

UPLOAD_BUCKET = os.environ["UPLOAD_BUCKET"]


ALLOWED_EXTENSIONS = {
    ".txt",
}


def response(status_code, body):

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def get_json_body(event):

    body = event.get("body")

    if not body:
        return {}

    try:
        return json.loads(body)

    except json.JSONDecodeError:
        return {}


def valid_email(email):

    if not email:
        return False

    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

    return re.match(pattern, email) is not None


def valid_filename(filename):

    if not filename:
        return False

    filename = os.path.basename(filename)

    if len(filename) > 100:
        return False

    extension = os.path.splitext(filename)[1].lower()

    return extension in ALLOWED_EXTENSIONS


def create_submission(event):

    data = get_json_body(event)

    email = data.get("email", "").strip()
    filename = data.get("fileName", "").strip()

    if not valid_email(email):

        return response(
            400,
            {
                "error": "Please provide a valid email address."
            },
        )

    if not valid_filename(filename):

        return response(
            400,
            {
                "error": "Only .txt chess replay files are allowed."
            },
        )

    submission_id = str(uuid.uuid4())

    safe_filename = os.path.basename(filename)

    s3_key = (
        f"submissions/{submission_id}/{safe_filename}"
    )

    now = datetime.now(timezone.utc).isoformat()

    table.put_item(
        Item={
            "submissionId": submission_id,
            "email": email,
            "fileName": safe_filename,
            "s3Key": s3_key,
            "status": "UPLOADING",
            "createdAt": now,
        }
    )

    upload_url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": UPLOAD_BUCKET,
            "Key": s3_key,
            "ContentType": "text/plain",
        },
        ExpiresIn=900,
    )

    return response(
        200,
        {
            "submissionId": submission_id,
            "uploadUrl": upload_url,
            "status": "UPLOADING",
        },
    )


def complete_submission(event):

    path_parameters = event.get(
        "pathParameters"
    ) or {}

    submission_id = path_parameters.get(
        "submissionId"
    )

    if not submission_id:

        return response(
            400,
            {
                "error": "Missing submissionId."
            },
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
            {
                "error": "Submission not found."
            },
        )

    try:

        s3.head_object(
            Bucket=UPLOAD_BUCKET,
            Key=item["s3Key"],
        )

    except Exception:

        return response(
            400,
            {
                "error": "Uploaded file was not found in S3."
            },
        )

    table.update_item(
        Key={
            "submissionId": submission_id
        },
        UpdateExpression="SET #status = :status",
        ExpressionAttributeNames={
            "#status": "status"
        },
        ExpressionAttributeValues={
            ":status": "UPLOADED"
        },
    )

    return response(
        200,
        {
            "submissionId": submission_id,
            "status": "UPLOADED",
        },
    )


def lambda_handler(event, context):

    request_context = event.get(
        "requestContext",
        {}
    )

    http = request_context.get(
        "http",
        {}
    )

    method = http.get(
        "method",
        ""
    )

    path = event.get(
        "rawPath",
        ""
    )

    if method == "POST" and path == "/submissions":

        return create_submission(event)

    if (
        method == "POST"
        and "/submissions/" in path
        and path.endswith("/complete")
    ):

        return complete_submission(event)

    return response(
        404,
        {
            "error": "Route not found."
        },
    )
