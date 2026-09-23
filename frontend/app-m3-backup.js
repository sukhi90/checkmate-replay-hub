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
   const reader = new FileReader();
reader.onload = function() {
    fetch("https://amazonaws.com", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            email: email,
            filename: file.name,
            content: reader.result
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log(data);
        statusBox.textContent = "Upload successful. Check your email for confirmation.";
        statusBox.style.color = "green";
    })
    .catch(error => {
        console.error(error);
        statusBox.textContent = "Upload failed.";
        statusBox.style.color = "red";
    });
};
reader.readAsText(file);

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
