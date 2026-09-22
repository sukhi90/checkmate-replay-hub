const form = document.getElementById("uploadForm");
const statusBox = document.getElementById("status");

const params = new URLSearchParams(window.location.search);

if (params.get("confirmed") === "1") {
    statusBox.textContent =
        "Your email has been confirmed. Your submission is now being processed.";
}

form.addEventListener("submit", async (event) => {

    event.preventDefault();

    const email = document.getElementById("email").value;
    const file = document.getElementById("file").files[0];

    if (!file) {
        statusBox.textContent = "Please select a chess file.";
        return;
    }

    statusBox.textContent = "UPLOADING";

    try {

        const content = await file.text();

        const response = await fetch(
            window.CHECKMATE_API_URL + "/upload",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    email: email,
                    filename: file.name,
                    content: content
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || "Upload failed.");
        }

        statusBox.textContent =
            data.status || "AWAITING_CONFIRMATION";

    } catch (error) {

        console.error(error);

        statusBox.textContent =
            "ERROR: " + error.message;
    }
});
