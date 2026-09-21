const API_URL =
    "http://checkmate-replay-web-sukhi90-786469175346.s3-website-us-east-1.amazonaws.com/prod";


const form =
    document.getElementById("submissionForm");

const emailInput =
    document.getElementById("email");

const fileInput =
    document.getElementById("file");

const submitButton =
    document.getElementById("submitButton");

const statusElement =
    document.getElementById("status");

const messageElement =
    document.getElementById("message");


function setStatus(status, message = "") {

    statusElement.textContent = status;

    messageElement.textContent = message;
}


form.addEventListener("submit", async (event) => {

    event.preventDefault();

    const email =
        emailInput.value.trim();

    const file =
        fileInput.files[0];


    if (!email) {

        setStatus(
            "ERROR",
            "Please enter your email address."
        );

        return;
    }


    if (!file) {

        setStatus(
            "ERROR",
            "Please select a chess replay file."
        );

        return;
    }


    if (!file.name.toLowerCase().endsWith(".txt")) {

        setStatus(
            "ERROR",
            "Only .txt replay files are allowed."
        );

        return;
    }


    submitButton.disabled = true;

    setStatus(
        "UPLOADING",
        "Preparing your upload..."
    );


    try {

        // ------------------------------------------------
        // STEP 1
        // Ask backend for a presigned S3 URL
        // ------------------------------------------------

        const createResponse =
            await fetch(
                `${API_URL}/submissions`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        email: email,
                        fileName: file.name
                    })
                }
            );


        const createData =
            await createResponse.json();


        if (!createResponse.ok) {

            throw new Error(
                createData.error ||
                "Could not create submission."
            );
        }


        // ------------------------------------------------
        // STEP 2
        // Upload directly to S3
        // ------------------------------------------------

        const uploadResponse =
            await fetch(
                createData.uploadUrl,
                {
                    method: "PUT",

                    headers: {
                        "Content-Type":
                            "text/plain"
                    },

                    body: file
                }
            );


        if (!uploadResponse.ok) {

            throw new Error(
                "File upload to S3 failed."
            );
        }


        // ------------------------------------------------
        // STEP 3
        // Tell backend that upload completed
        // ------------------------------------------------

        const completeResponse =
            await fetch(
                `${API_URL}/submissions/${createData.submissionId}/complete`,
                {
                    method: "POST"
                }
            );


        const completeData =
            await completeResponse.json();


        if (!completeResponse.ok) {

            throw new Error(
                completeData.error ||
                "Could not complete submission."
            );
        }


        setStatus(
            "UPLOADED",
            "Your chess replay was uploaded successfully."
        );


        form.reset();


    } catch (error) {

        console.error(error);

        setStatus(
            "ERROR",
            error.message
        );

    } finally {

        submitButton.disabled = false;

    }

});
