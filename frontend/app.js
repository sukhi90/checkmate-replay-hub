window.CHECKMATE_API_URL = "https://bawj7v9wl8.execute-api.us-east-1.amazonaws.com";
const form = document.getElementById("uploadForm");
const statusBox = document.getElementById("status");

const params = new URLSearchParams(window.location.search);

if (params.get("confirmed") === "1") {
    statusBox.textContent = "Your email has been confirmed. Your submission is now being processed.";
}

// Form Submit Event Handler
form.addEventListener("submit", function(e) {
    e.preventDefault(); // Page refresh rokda hai
    
    statusBox.textContent = "UPLOADING...";
    statusBox.style.color = "orange";

    const email = document.getElementById("email").value;
    const fileInput = document.getElementById("file");
    const file = fileInput.files[0]; // <-- FIXED: Added [0] to grab the actual file object

    if (!file) {
        statusBox.textContent = "Please select a file first.";
        statusBox.style.color = "red";
        return;
    }

    // 1. Get presigned URL from API Gateway
   fetch(window.CHECKMATE_API_URL + "/upload", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            email: email,
            filename: file.name // <-- NOW VALID: file.name will work perfectly
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error("Backend API error");
        }
        return response.json();
    })
    .then(data => {
        // 2. Direct upload to S3 using presigned URL
        return fetch(data.uploadUrl, {
            method: "PUT",
            body: file,
            headers: {
                "Content-Type": "text/plain"
            }
        });
    })
    .then(s3Response => {
        if (s3Response.ok) {
            statusBox.textContent = "UPLOADED Successfully!";
            statusBox.style.color = "green";
        } else {
            throw new Error("S3 Upload Failed");
        }
    })
    .catch(error => {
        console.error("Error:", error);
        statusBox.textContent = "ERROR: Upload failed. Please try again.";
        statusBox.style.color = "red";
    });
});
