from flask import Flask, request, jsonify, send_from_directory
from pathlib import Path
from werkzeug.utils import secure_filename
import uuid
import re
import os
import boto3  # <-- AWS SDK ਜੋੜਿਆ
from botocore.exceptions import ClientError

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = BASE_DIR / "uploads"

UPLOAD_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.chmod(0o700)

app = Flask(__name__)

# Maximum upload size: 10 MB
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "pgn",
    "txt",
    "json",
    "zip"
}

EMAIL_PATTERN = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)

# ---------------- AWS Configuration ----------------
# Environment Variables ਤੋਂ ਟੇਬਲ ਦਾ ਨਾਮ ਅਤੇ API ਦਾ URL ਲਵਾਂਗੇ
TABLE_NAME = os.environ.get('DYNAMODB_TABLE', 'YourDynamoDBTableName')
PUBLIC_URL = os.environ.get('API_GATEWAY_URL', 'http://localhost:8000') 
SENDER_EMAIL = "your-verified-ses-email@example.com" # <--- ਇੱਥੇ ਆਪਣੀ AWS SES ਵਾਲੀ ਵੈਰੀਫਾਈਡ ਈਮੇਲ ਲਿਖੋ

# AWS Clients ਸੈੱਟਅੱਪ
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
ses_client = boto3.client('ses', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
# ---------------------------------------------------

def allowed_file(filename):
    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS  # Indentation ਸਹੀ ਕੀਤੀ


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.post("/upload")
def upload():
    email = request.form.get("email", "").strip()
    uploaded_file = request.files.get("file")

    # Validate email
    if not email or not EMAIL_PATTERN.match(email):
        return jsonify({
            "status": "ERROR",
            "message": "Please enter a valid E-Mail address."
        }), 400

    # Validate file
    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({
            "status": "ERROR",
            "message": "Please select a file."
        }), 400

    original_filename = secure_filename(uploaded_file.filename)

    if not original_filename:
        return jsonify({
            "status": "ERROR",
            "message": "Invalid filename."
        }), 400

    if not allowed_file(original_filename):
        return jsonify({
            "status": "ERROR",
            "message": "File type is not allowed."
        }), 400

    # Generate a random filename so the uploaded file
    # cannot be guessed from its original name.
    extension = Path(original_filename).suffix.lower()
    random_filename = f"{uuid.uuid4().hex}{extension}"

    destination = UPLOAD_DIR / random_filename

    try:
        uploaded_file.save(destination)

        # Make sure uploaded file is not executable by default.
        os.chmod(destination, 0o600)

    except Exception:
        return jsonify({
            "status": "ERROR",
            "message": "The file could not be stored."
        }), 500

    # ---------------- ਨਵਾਂ ਕੋਡ: DynamoDB ਅਤੇ SES Email ----------------
    try:
        # 1. ਰੈਂਡਮ ਕਨਫਰਮੇਸ਼ਨ ਟੋਕਨ ਬਣਾਓ
        confirmation_token = str(uuid.uuid4())

        # 2. DynamoDB ਵਿੱਚ ਡਾਟਾ ਸੇਵ ਕਰੋ
        table = dynamodb.Table(TABLE_NAME)
        table.put_item(
            Item={
                'email': email,
                'confirmationToken': confirmation_token,
                'filename': random_filename,
                'status': 'PENDING'
            }
        )

        # 3. API Gateway / Server URL ਮੁਤਾਬਕ ਕਨਫਰਮ ਲਿੰਕ ਤਿਆਰ ਕਰੋ
        confirm_url = f"{PUBLIC_URL}/confirm/{confirmation_token}"

        # 4. Email Template (HTML) ਤਿਆਰ ਕਰੋ
        subject = "Confirm your ChessMate upload"
        body_html = f"""
        <html>
        <body>
          <h2>File Uploaded Successfully!</h2>
          <p>Thank you for uploading <b>{original_filename}</b>.</p>
          <p>Please click the button below to confirm your upload and process the chess file:</p>
          <p><a href='{confirm_url}' style='background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;'>Confirm Upload</a></p>
          <br>
          <p>If the button doesn't work, copy and paste this link into your browser:</p>
          <p>{confirm_url}</p>
        </body>
        </html>
        """

        # 5. AWS SES ਰਾਹੀਂ ਯੂਜ਼ਰ ਨੂੰ ਈਮੇਲ ਭੇਜੋ
        ses_client.send_email(
            Source=SENDER_EMAIL,
            Destination={'ToAddresses': [email]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {'Html': {'Data': body_html, 'Charset': 'UTF-8'}}
            }
        )

    except ClientError as e:
        print(f"AWS ERROR: {e.response['Error']['Message']}")
        # ਫਾਈਲ ਅਪਲੋਡ ਹੋ ਗਈ ਹੈ ਪਰ ਈਮੇਲ ਫੇਲ ਹੋਈ, ਤੁਸੀਂ ਚਾਹੋ ਤਾਂ ਇੱਥੇ Error ਰਿਟਰਨ ਕਰ ਸਕਦੇ ਹੋ
    # ------------------------------------------------------------------

    print(
        f"UPLOAD: email={email}, "
        f"original={original_filename}, "
        f"stored={random_filename}"
    )

    return jsonify({
        "status": "UPLOADED",
        "message": "File uploaded successfully. Please check your email to confirm."
    }), 200


@app.errorhandler(413)
def file_too_large(error):
    return jsonify({
        "status": "ERROR",
        "message": "File is too large. Maximum size is 10 MB."
    }), 413


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8000,
        debug=False
    )
