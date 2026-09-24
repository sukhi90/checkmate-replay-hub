import os
import json
import boto3

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")

table = dynamodb.Table(os.environ["TABLE_NAME"])
queue_url = os.environ["PROCESSING_QUEUE_URL"]


def lambda_handler(event, context):

    token = event["pathParameters"]["token"]

    response = table.scan()

    item = None

    for row in response.get("Items", []):
        if row.get("confirmationToken") == token:
            item = row
            break

    if not item:
        return {
            "statusCode": 404,
            "body": "Invalid confirmation token"
        }

    submission_id = item["submissionId"]

    table.update_item(
        Key={"submissionId": submission_id},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={
            "#s": "status"
        },
        ExpressionAttributeValues={
            ":s": "PROCESSING"
        }
    )

    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({
            "submissionId": submission_id
        })
    )

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html"
        },
        "body": """
        <html>
        <body>
            <h2>Submission confirmed</h2>
            <p>Processing has started.</p>
        </body>
        </html>
        """
    }
