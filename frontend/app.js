window.CHECKMATE_API_URL = "https://3cnwsveo2i.execute-api.us-east-1.amazonaws.com ";
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
    fetch("https://3cnwsveo2i.execute-api.us-east-1.amazonaws.com/upload", {
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
});
