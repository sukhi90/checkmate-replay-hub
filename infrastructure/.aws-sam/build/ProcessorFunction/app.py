import os
import json
from datetime import datetime, timezone

import boto3

s3 = boto3.client("s3")
ddb = boto3.resource("dynamodb")
ses = boto3.client("sesv2")

TABLE = ddb.Table(os.environ["TABLE_NAME"])
FROM_EMAIL = os.environ["SES_FROM_EMAIL"]


FILES = {
    "a": "RNBQKBNR",
    "b": "RNBQKBNR",
}


def square_to_xy(square):
    if len(square) != 2:
        return None

    file = square[0]
    rank = square[1]

    if file not in "abcdefgh":
        return None

    if rank not in "12345678":
        return None

    return ord(file) - ord("a"), int(rank) - 1


def initial_board():
    board = {}

    for i, p in enumerate("RNBQKBNR"):
        board[(i, 0)] = ("W", p)

    for i in range(8):
        board[(i, 1)] = ("W", "P")

    for i, p in enumerate("RNBQKBNR"):
        board[(i, 7)] = ("B", p)

    for i in range(8):
        board[(i, 6)] = ("B", "P")

    return board


def clear_path(board, sx, sy, dx, dy):
    stepx = 0 if dx == sx else (1 if dx > sx else -1)
    stepy = 0 if dy == sy else (1 if dy > sy else -1)

    x = sx + stepx
    y = sy + stepy

    while (x, y) != (dx, dy):
        if (x, y) in board:
            return False
        x += stepx
        y += stepy

    return True


def legal_piece_move(piece, sx, sy, dx, dy, board, capture):
    p = piece

    ax = abs(dx - sx)
    ay = abs(dy - sy)

    if p == "P":
        direction = 1 if piece[0] == "W" else -1

    return True


def validate_move(board, side, src, dst):
    s = square_to_xy(src)
    d = square_to_xy(dst)

    if s is None or d is None:
        return False, "Invalid square."

    sx, sy = s
    dx, dy = d

    if (sx, sy) not in board:
        return False, f"No piece exists on {src}."

    color, piece = board[(sx, sy)]

    if color != side:
        return False, f"It is not {color}'s turn for piece on {src}."

    target = board.get((dx, dy))

    if target and target[0] == side:
        return False, f"Destination {dst} contains your own piece."

    ax = abs(dx - sx)
    ay = abs(dy - sy)

    valid = False

    if piece == "P":
        direction = 1 if side == "W" else -1
        start_rank = 1 if side == "W" else 6

        if dx == sx and target is None and dy - sy == direction:
            valid = True

        elif (
            dx == sx
            and target is None
            and sy == start_rank
            and dy - sy == 2 * direction
            and (sx, sy + direction) not in board
        ):
            valid = True

        elif (
            ax == 1
            and dy - sy == direction
            and target is not None
            and target[0] != side
        ):
            valid = True

    elif piece == "N":
        valid = (ax, ay) in ((1, 2), (2, 1))

    elif piece == "B":
        valid = ax == ay and clear_path(board, sx, sy, dx, dy)

    elif piece == "R":
        valid = (
            (sx == dx or sy == dy)
            and clear_path(board, sx, sy, dx, dy)
        )

    elif piece == "Q":
        valid = (
            (sx == dx or sy == dy or ax == ay)
            and clear_path(board, sx, sy, dx, dy)
        )

    elif piece == "K":
        valid = max(ax, ay) == 1

    if not valid:
        return False, f"Illegal {piece} move from {src} to {dst}."

    del board[(sx, sy)]
    board[(dx, dy)] = (side, piece)

    return True, ""


def analyse(content):
    board = initial_board()

    side = "W"
    move_count = 0

    lines = content.splitlines()

    for number, raw in enumerate(lines, 1):
        line = raw.strip()

        if not line:
            continue

        parts = line.split()

        if len(parts) != 2:
            return False, f"Invalid format on line {number}. Expected: e2 e4", None, None

        src, dst = parts

        ok, error = validate_move(
            board,
            side,
            src,
            dst
        )

        if not ok:
            return False, f"Line {number}: {error}", None, None

        move_count += 1
        side = "B" if side == "W" else "W"

    if move_count == 0:
        return False, "The chess file contains no moves.", None, None

    # This simplified project format does not contain explicit result
    # metadata. We determine whether a king remains on the board.
    white_king = any(
        color == "W" and piece == "K"
        for color, piece in board.values()
    )

    black_king = any(
        color == "B" and piece == "K"
        for color, piece in board.values()
    )

    if not white_king and not black_king:
        winner = "Draw"
    elif not white_king:
        winner = "Black"
    elif not black_king:
        winner = "White"
    else:
        winner = "Draw"

    return True, "", winner, move_count


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


def process_submission(submission_id):
    item = TABLE.get_item(
        Key={"submissionId": submission_id}
    ).get("Item")

    if not item:
        return

    if item.get("status") != "PROCESSING":
        return

    try:
        obj = s3.get_object(
            Bucket=os.environ["BUCKET_NAME"],
            Key=item["s3Key"]
        )

        content = obj["Body"].read().decode("utf-8")

        valid, error, winner, move_count = analyse(content)

        now = datetime.now(timezone.utc).isoformat()

        if not valid:
            TABLE.update_item(
                Key={"submissionId": submission_id},
                UpdateExpression="""
                    SET #s = :failed,
                        errorReason = :error,
                        completedAt = :now
                """,
                ExpressionAttributeNames={
                    "#s": "status"
                },
                ExpressionAttributeValues={
                    ":failed": "FAILED",
                    ":error": error,
                    ":now": now
                }
            )

            send_email(
                item["email"],
                "Checkmate Replay Hub - Processing failed",
                f"""Your chess submission could not be processed.

Reason:

{error}

Please correct the chess file and submit it again.
"""
            )

            return

        TABLE.update_item(
            Key={"submissionId": submission_id},
            UpdateExpression="""
                SET #s = :done,
                    winner = :winner,
                    moveCount = :moves,
                    completedAt = :now
            """,
            ExpressionAttributeNames={
                "#s": "status"
            },
            ExpressionAttributeValues={
                ":done": "DONE",
                ":winner": winner,
                ":moves": move_count,
                ":now": now
            }
        )

        send_email(
            item["email"],
            "Checkmate Replay Hub - Game Result",
            f"""Your chess submission was processed successfully.

Result: {winner}
Number of moves: {move_count}

Thank you for using Checkmate Replay Hub.
"""
        )

    except Exception as exc:
        print("PROCESSING ERROR:", repr(exc))

        now = datetime.now(timezone.utc).isoformat()

        TABLE.update_item(
            Key={"submissionId": submission_id},
            UpdateExpression="""
                SET #s = :failed,
                    errorReason = :error,
                    completedAt = :now
            """,
            ExpressionAttributeNames={
                "#s": "status"
            },
            ExpressionAttributeValues={
                ":failed": "FAILED",
                ":error": "Internal processing error.",
                ":now": now
            }
        )


def lambda_handler(event, context):
    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            submission_id = body["submissionId"]
            process_submission(submission_id)
        except Exception as exc:
            print("QUEUE ERROR:", repr(exc))

    return {"statusCode": 200}
