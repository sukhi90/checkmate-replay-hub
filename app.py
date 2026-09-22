from flask import Flask, request, jsonify, send_from_directory
from pathlib import Path
from werkzeug.utils import secure_filename
import uuid
import re
import os

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


def allowed_file(filename):
    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS


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

    print(
        f"UPLOAD: email={email}, "
        f"original={original_filename}, "
        f"stored={random_filename}"
    )

    return jsonify({
        "status": "UPLOADED",
        "message": "File uploaded successfully."
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
