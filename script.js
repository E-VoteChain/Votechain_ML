document.addEventListener("DOMContentLoaded", () => {
  const idCardInput = document.getElementById("id-card-image");
  const liveFaceInput = document.getElementById("live-face-image");
  const idCardPreview = document.getElementById("id-card-preview");
  const liveFacePreview = document.getElementById("live-face-preview");
  const verifyButton = document.getElementById("verify-button");

  const progressSection = document.getElementById("progress-section");
  const statusOverall = document.getElementById("status-overall");
  const statusOverallText = statusOverall.querySelector(".status-text");
  const statusOverallSpinner = statusOverall.querySelector(".spinner");

  const stepIdCard = document.getElementById("step-id-card");
  const stepLiveness = document.getElementById("step-liveness");
  const stepFaceVerification = document.getElementById(
    "step-face-verification"
  );
  const stepDatabase = document.getElementById("step-database");

  const resultsSection = document.getElementById("results-section");
  const finalStatusMessage = document.getElementById("final-status-message");
  const extractedDetailsDisplay = document.getElementById(
    "extracted-details-display"
  );
  const extractedDetailsJson = document.getElementById(
    "extracted-details-json"
  );

  // --- Helper: Update a single step’s status (Pending / Processing / Success / Failed) ---
  function updateStepStatus(
    stepElement,
    statusType,
    icon,
    mainMessage = "",
    detailsText = ""
  ) {
    const statusTextElement = stepElement.querySelector(".status-text");
    const iconElement = stepElement.querySelector(".step-icon");
    const detailsElement = stepElement.querySelector(".details");

    // Clear out any of the old status- classes
    stepElement.className = "";
    if (statusType === "processing")
      stepElement.classList.add("step-status-processing");
    else if (statusType === "success")
      stepElement.classList.add("step-status-success");
    else if (statusType === "failed")
      stepElement.classList.add("step-status-failed");
    else if (statusType === "pending")
      stepElement.classList.add("step-status-pending");
    else if (statusType === "warning")
      stepElement.classList.add("step-status-failed");

    statusTextElement.textContent =
      mainMessage || statusType.charAt(0).toUpperCase() + statusType.slice(1);
    iconElement.textContent = icon;

    if (detailsText && detailsText.trim() !== "") {
      detailsElement.textContent = detailsText;
      detailsElement.style.display = "block";
    } else {
      detailsElement.style.display = "none";
    }
  }

  // --- Helper: Update overall status banner (Processing / Success / Failed) ---
  function updateOverallStatus(statusType, message) {
    statusOverallText.textContent = message;
    statusOverallSpinner.style.display =
      statusType === "processing" ? "inline-block" : "none";

    statusOverall.className = "status-indicator"; // reset
    if (statusType === "processing") statusOverall.classList.add("processing");
    else if (statusType === "success") statusOverall.classList.add("success");
    else if (statusType === "failed") statusOverall.classList.add("failed");
    else if (statusType === "warning") statusOverall.classList.add("failed");
  }

  // --- Helper: Show final results area and populate it ---
  function updateFinalResults(statusType, message, extractedDetails = null) {
    resultsSection.style.display = "block";
    finalStatusMessage.textContent = message;
    finalStatusMessage.className = "";
    if (statusType === "success") finalStatusMessage.classList.add("success");
    else if (statusType === "failed")
      finalStatusMessage.classList.add("failed");
    else if (statusType === "warning")
      finalStatusMessage.classList.add("warning");

    if (
      extractedDetails &&
      typeof extractedDetails === "object" &&
      Object.keys(extractedDetails).length > 0 &&
      !extractedDetails.error
    ) {
      extractedDetailsDisplay.style.display = "block";
      extractedDetailsJson.textContent = JSON.stringify(
        extractedDetails,
        null,
        2
      );
    } else {
      extractedDetailsDisplay.style.display = "none";
      extractedDetailsJson.textContent = "";
    }
  }

  // --- Reset just the step banners and overall status (don’t clear inputs) ---
  async function resetSteps() {
    await new Promise((resolve) => setTimeout(resolve, 10000));
    progressSection.style.display = "none";
    resultsSection.style.display = "none";
    extractedDetailsDisplay.style.display = "none";

    updateStepStatus(stepIdCard, "pending", "⏳", "Pending");
    updateStepStatus(stepLiveness, "pending", "⏳", "Pending");
    updateStepStatus(stepFaceVerification, "pending", "⏳", "Pending");
    updateStepStatus(stepDatabase, "pending", "⏳", "Pending");

    updateOverallStatus("pending", "Not Started");

    finalStatusMessage.textContent = "";
    finalStatusMessage.className = "";
    extractedDetailsJson.textContent = "";

    verifyButton.disabled = false;
    verifyButton.textContent = "Verify Identity";
  }

  // // --- “Hard” reset: clear everything (inputs, previews, and statuses) ---
  // async function resetAll() {
  //   console.log("I am in this ");
  //   await new Promise((resolve) => setTimeout(resolve, 20000));
  //   resetSteps();
  //   idCardPreview.style.display = "none";
  //   idCardPreview.src = "#";
  //   liveFacePreview.style.display = "none";
  //   liveFacePreview.src = "#";
  //   idCardInput.value = "";
  //   liveFaceInput.value = "";
  // }

  // --- Set up thumbnail preview for both inputs ---
  function setupImagePreview(inputElement, previewElement) {
    inputElement.addEventListener("change", (event) => {
      if (event.target.files && event.target.files[0]) {
        const reader = new FileReader();
        reader.onload = (e) => {
          previewElement.src = e.target.result;
          previewElement.style.display = "block";
        };
        reader.readAsDataURL(event.target.files[0]);
      } else {
        previewElement.style.display = "none";
        previewElement.src = "#";
      }
    });
  }

  setupImagePreview(idCardInput, idCardPreview);
  setupImagePreview(liveFaceInput, liveFacePreview);

  // On initial page load, completely reset
  // resetAll();

  // --- Main click handler for “Verify Identity” ---
  verifyButton.addEventListener("click", async (event) => {
    event.preventDefault();
    verifyButton.disabled = true;
    verifyButton.textContent = "Loading";
    console.log("1");
    const idCardFile = idCardInput.files[0];
    const liveFaceFile = liveFaceInput.files[0];
    console.log("1");

    if (!idCardFile || !liveFaceFile) {
      alert("Please select both ID card and live face images.");
      return;
    }

    // 2) Show progress UI & disable the button
    progressSection.style.display = "block";
    verifyButton.disabled = true;
    verifyButton.textContent = "Processing...";
    updateOverallStatus("processing", "Processing…");
    updateStepStatus(stepIdCard, "processing", "⚙️", "Processing ID card…");

    console.log("id_card_image", idCardFile);
    console.log("live_Face_image", liveFaceFile);
    const formData = new FormData();
    formData.append("id_card_image", idCardFile);
    formData.append("live_face_image", liveFaceFile);

    try {
      const response = await axios.post(
        "http://localhost:5000/process_and_verify",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        }
      );
      const data = response.data;
      console.log("data", data);

      // — Update each step based on response —
      // 1. ID Card Processing
      if (data.id_card_processing_status) {
        if (
          data.id_card_processing_status.toLowerCase().includes("successfully")
        ) {
          updateStepStatus(
            stepIdCard,
            "success",
            "✅",
            "Processed",
            data.id_card_processing_status
          );
        } else {
          updateStepStatus(
            stepIdCard,
            "failed",
            "❌",
            "Failed",
            data.id_card_processing_status
          );
        }
      } else {
        updateStepStatus(
          stepIdCard,
          "failed",
          "❌",
          "Status Missing",
          "ID card processing status not returned."
        );
      }

      // 2. Liveness Check
      if (data.liveness_check) {
        if (data.liveness_check.passed) {
          updateStepStatus(
            stepLiveness,
            "success",
            "✅",
            "Passed",
            data.liveness_check.status
          );
        } else {
          updateStepStatus(
            stepLiveness,
            "failed",
            "❌",
            "Failed",
            data.liveness_check.status || "Liveness check failed."
          );
        }
      } else {
        updateStepStatus(stepLiveness, "failed", "❌", "Not Performed");
      }

      // 3. Face Verification
      if (data.face_verification) {
        if (data.face_verification.verified) {
          updateStepStatus(
            stepFaceVerification,
            "success",
            "✅",
            "Verified",
            data.face_verification.status
          );
        } else {
          updateStepStatus(
            stepFaceVerification,
            "failed",
            "❌",
            "Not Verified",
            data.face_verification.status || "Face verification failed."
          );
        }
      } else {
        updateStepStatus(stepFaceVerification, "failed", "❌", "Not Performed");
      }

      // 4. Database Storage
      if (data.database_storage) {
        const isWarningDb =
          data.overall_status &&
          data.overall_status
            .toLowerCase()
            .includes("warning: database storage failed");
        if (data.database_storage.stored) {
          updateStepStatus(
            stepDatabase,
            "success",
            "✅",
            "Stored",
            data.database_storage.message
          );
        } else if (isWarningDb) {
          updateStepStatus(
            stepDatabase,
            "warning",
            "⚠️",
            "Storage Issue",
            data.database_storage.message
          );
        } else {
          updateStepStatus(
            stepDatabase,
            "failed",
            "❌",
            "Storage Failed",
            data.database_storage.message
          );
        }
      } else {
        updateStepStatus(stepDatabase, "failed", "❌", "Not Attempted");
      }

      // — Final overall status (Success / Warning / Failed) —
      let finalOverallType = "failed";
      if (data.overall_status) {
        const lower = data.overall_status.toLowerCase();
        if (lower.includes("success") && !lower.includes("warning")) {
          finalOverallType = "success";
        } else if (lower.includes("warning")) {
          finalOverallType = "warning";
        }
      }

      updateOverallStatus(
        finalOverallType,
        data.overall_status || "Completed with unknown status."
      );
      updateFinalResults(
        finalOverallType,
        data.overall_status || "Completed with unknown status.",
        data.text_details
      );
    } catch (error) {
      console.error("Error during verification fetch or JSON parsing:", error);
      const errorMsg = "A network or server error occurred. Please try again.";
      updateOverallStatus("failed", "Error!");
      updateFinalResults("failed", errorMsg);

      // Mark all steps as failed/not performed
      updateStepStatus(
        stepIdCard,
        "failed",
        "❌",
        "Error",
        "Process interrupted"
      );
      updateStepStatus(stepLiveness, "failed", "❌", "Not Performed");
      updateStepStatus(stepFaceVerification, "failed", "❌", "Not Performed");
      updateStepStatus(stepDatabase, "failed", "❌", "Not Performed");
    } finally {
      // Re-enable button now that everything (UI and fetch) is done,
      // but don’t auto-clear the inputs. Let the user click “Verify Identity” again if needed.
      verifyButton.disabled = false;
      verifyButton.textContent = "Verify Identity";
    }
  });
});
