import json
import os
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError
from chess_validator import validate_game, ChessValidationError

s3 = boto3.client("s3")
ses = boto3.client("ses")
dynamodb = boto3.resource("dynamodb")

table = dynamodb.Table(os.environ["TABLE_NAME"])
UPLOAD_BUCKET = os.environ["BUCKET_NAME"]
SES_SENDER_EMAIL = os.environ["SES_FROM_EMAIL"]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def send_result_email(email, submission_id, status, winner=None, moves=None, error_reason=None):
    subject = "Checkmate Replay Hub - Submission result"
    
    if status == "DONE":
        winner_text = {"white": "White", "black": "Black", "draw": "Draw"}.get(winner, winner)
        text_body = f"""Your Checkmate Replay Hub submission was processed successfully.
Submission ID: {submission_id}
Status: DONE
Winner: {winner_text}
Number of moves: {moves}
"""
        html_body = f"""<html><body>
<h2>Checkmate Replay Hub</h2>
<p>Your chess submission was processed successfully.</p>
<p><strong>Status:</strong> DONE<br>
<strong>Submission ID:</strong> {submission_id}<br>
<strong>Winner:</strong> {winner_text}<br>
<strong>Number of moves:</strong> {moves}</p>
</body></html>"""
    else:
        text_body = f"""Your Checkmate Replay Hub submission could not be processed.
Submission ID: {submission_id}
Status: FAILED
Reason: {error_reason}
"""
        html_body = f"""<html><body>
<h2>Checkmate Replay Hub</h2>
<p>Your chess submission could not be processed.</p>
<p><strong>Status:</strong> FAILED<br>
<strong>Submission ID:</strong> {submission_id}</p>
<p><strong>Reason:</strong><br>{error_reason}</p>
<p>Please correct the chess file and submit it again.</p>
</body></html>"""

    ses.send_email(
        Source=SES_SENDER_EMAIL,
        Destination={"ToAddresses": [email]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Text": {"Data": text_body, "Charset": "UTF-8"},
                "Html": {"Data": html_body, "Charset": "UTF-8"},
            },
        },
    )

def update_done(submission_id, winner, moves):
    table.update_item(
        Key={"submissionId": submission_id},
        UpdateExpression="""SET #status=:status,
                            winner=:winner, moveCount=:moves, processedAt=:processed_at""",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "DONE",
            ":winner": winner,
            ":moves": moves,
            ":processed_at": now_iso(),
        },
    )

def update_failed(submission_id, reason):
    table.update_item(
        Key={"submissionId": submission_id},
        UpdateExpression="""SET #status=:status,
                            errorReason=:reason, processedAt=:processed_at""",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "FAILED",
            ":reason": reason,
            ":processed_at": now_iso(),
        },
    )

def process_submission(submission_id):
    response = table.get_item(Key={"submissionId": submission_id})
    item = response.get("Item")
    if not item:
        raise RuntimeError(f"Submission {submission_id} does not exist.")
        
    email = item["email"]
    s3_key = item["s3Key"]
    
    if item.get("status") in ("DONE", "FAILED"):
        return {"status": item["status"], "message": "Already processed."}
        
    try:
        obj = s3.get_object(Bucket=UPLOAD_BUCKET, Key=s3_key)
        content = obj["Body"].read().decode("utf-8")
    except UnicodeDecodeError:
        reason = "The uploaded file is not valid UTF-8 text."
        update_failed(submission_id, reason)
        send_result_email(email, submission_id, "FAILED", error_reason=reason)
        return {"status": "FAILED", "reason": reason}
    except ClientError as exc:
        print(f"S3 error for {submission_id}: {exc}")
        reason = "The uploaded chess file could not be read from secure storage."
        update_failed(submission_id, reason)
        send_result_email(email, submission_id, "FAILED", error_reason=reason)
        return {"status": "FAILED", "reason": reason}
        
    try:
        result = validate_game(content.splitlines())
        update_done(submission_id, result["winner"], result["moves"])
        send_result_email(
            email, submission_id, "DONE",
            winner=result["winner"], moves=result["moves"]
        )
        return {
            "status": "DONE",
            "winner": result["winner"],
            "moves": result["moves"],
        }
    except ChessValidationError as exc:
        reason = str(exc)
        update_failed(submission_id, reason)
        send_result_email(email, submission_id, "FAILED", error_reason=reason)
        return {"status": "FAILED", "reason": reason}

def lambda_handler(event, context):
    print("Received SQS event:", json.dumps(event))
    results = []
    for record in event.get("Records", []):
        body = json.loads(record["body"])
        results.append(process_submission(body["submissionId"]))
    return {"processed": len(results), "results": results}
