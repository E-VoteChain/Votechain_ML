from deepface import DeepFace
import numpy as np
import traceback
import os
import json # For printing results if needed
# cv2 import is not needed here unless you uncomment the __main__ block and use cv2.imwrite

# --- Configuration ---
VERIFICATION_MODEL_NAME = 'Facenet'
DISTANCE_METRIC = 'cosine'
DETECTOR_BACKEND_LIVE = 'retinaface'

# --- Threshold Configuration ---
CUSTOM_SYSTEM_THRESHOLD = 0.48  # YOUR DESIRED THRESHOLD FOR THE SYSTEM'S DECISION

try:
    STANDARD_DEEPFACE_THRESHOLD = DeepFace.verification.find_threshold(VERIFICATION_MODEL_NAME, DISTANCE_METRIC)
    print(f"Standard DeepFace threshold for {VERIFICATION_MODEL_NAME}/{DISTANCE_METRIC}: {STANDARD_DEEPFACE_THRESHOLD}")
except Exception:
    STANDARD_DEEPFACE_THRESHOLD = 0.40 
    print(f"Warning: Using fallback standard DeepFace threshold {STANDARD_DEEPFACE_THRESHOLD} for {VERIFICATION_MODEL_NAME}/{DISTANCE_METRIC}")


def perform_liveness_check(live_image_path, dummy_reference_image_path):
    print(f"\n--- Performing Liveness Check on: {live_image_path} ---")
    liveness_passed = False
    liveness_outcome_message = "Not Performed"

    if not os.path.exists(live_image_path):
        print(f"Liveness FAILED: Live image not found at '{live_image_path}'")
        return False, "Liveness FAILED: Live image file missing."
    if not os.path.exists(dummy_reference_image_path):
        print(f"CRITICAL ERROR: Dummy liveness reference image not found at '{dummy_reference_image_path}'")
        return False, "Liveness FAILED: System configuration error (missing reference image)."

    try:
        liveness_result_dict = DeepFace.verify(
            img1_path=live_image_path,
            img2_path=dummy_reference_image_path,
            model_name=VERIFICATION_MODEL_NAME,
            detector_backend=DETECTOR_BACKEND_LIVE,
            distance_metric=DISTANCE_METRIC,
            anti_spoofing=True,
            enforce_detection=True
        )
        print(f"Liveness check (DeepFace.verify) raw result: {json.dumps(liveness_result_dict, default=str)}")
        is_spoof_flag = liveness_result_dict.get("is_spoof", False)
        if is_spoof_flag:
            liveness_outcome_message = "FAILED (Spoof Detected via 'is_spoof' flag)"
        else:
            liveness_outcome_message = "PASSED"
            liveness_passed = True
    except ValueError as ve:
        error_str = str(ve)
        original_cause_error_str = str(ve.__cause__) if ve.__cause__ else ""
        print(f"Liveness Check raised ValueError: {ve}")
        if ve.__cause__: print(f"Original cause: {ve.__cause__}")
        if "Spoof detected" in error_str or "Spoof detected" in original_cause_error_str:
            liveness_outcome_message = "FAILED (Spoof Detected via ValueError)"
        elif "face could not be detected" in error_str.lower() or \
             ("face could not be detected" in original_cause_error_str.lower()):
            liveness_outcome_message = "FAILED (Face Detection Error during Liveness)"
        else:
            liveness_outcome_message = f"ERROR (Other ValueError: {error_str[:100]})"
        liveness_passed = False
    except Exception as e_live:
        print(f"Unexpected error during liveness check: {e_live}")
        traceback.print_exc()
        liveness_outcome_message = f"ERROR (Unexpected: {str(e_live)[:100]})"
        liveness_passed = False
    print(f"Liveness Outcome: {liveness_outcome_message}")
    return liveness_passed, liveness_outcome_message


def verify_faces(live_image_path, id_card_embedding_list):
    print(f"\n--- Performing Face Verification: Live vs ID Card (System Threshold: {CUSTOM_SYSTEM_THRESHOLD}) ---")
    system_verification_passed = False 
    # Initialize with a structure that matches the TS interface, using default/error values
    match_details = {
        "verified": False, # Will be updated based on CUSTOM_SYSTEM_THRESHOLD
        "distance": "N/A",
        "threshold": f"{CUSTOM_SYSTEM_THRESHOLD:.4f}", # System's threshold
        "model": VERIFICATION_MODEL_NAME,
        "metric": DISTANCE_METRIC,
        "message": "Verification not fully performed or error occurred."
        # "status" will be added by app.py by copying "message"
        # Additional DeepFace specific info (optional, not directly in TS interface):
        # "deepface_standard_threshold": f"{STANDARD_DEEPFACE_THRESHOLD:.4f}",
        # "deepface_verified_flag": False,
    }

    if not os.path.exists(live_image_path):
        match_details["message"] = "Face Verification FAILED: Live image file missing."
        print(match_details["message"])
        return False, match_details # system_verification_passed is already False

    if id_card_embedding_list is None or not isinstance(id_card_embedding_list, list) or not id_card_embedding_list:
        match_details["message"] = "Cannot verify: Missing or invalid ID card embedding."
        print(match_details["message"])
        return False, match_details # system_verification_passed is already False

    try:
        result = DeepFace.verify(
            img1_path=live_image_path,
            img2_path=id_card_embedding_list,
            model_name=VERIFICATION_MODEL_NAME,
            detector_backend=DETECTOR_BACKEND_LIVE,
            distance_metric=DISTANCE_METRIC,
            anti_spoofing=False,
            enforce_detection=True
        )
        print(f"Face verification (DeepFace.verify) raw result: {json.dumps(result, default=str)}")

        distance_val = result.get("distance", float('inf'))
        # deepface_internal_threshold_val = result.get("threshold", STANDARD_DEEPFACE_THRESHOLD)
        # deepface_verified_flag_val = result.get("verified", False)

        # YOUR SYSTEM'S VERIFICATION LOGIC using CUSTOM_SYSTEM_THRESHOLD
        if distance_val <= CUSTOM_SYSTEM_THRESHOLD:
            system_verification_passed = True
            current_message = f"Face Verification PASSED (System Threshold: {CUSTOM_SYSTEM_THRESHOLD:.4f}, Distance: {distance_val:.4f})."
        else:
            system_verification_passed = False
            current_message = f"Face Verification FAILED (System Threshold: {CUSTOM_SYSTEM_THRESHOLD:.4f}, Distance: {distance_val:.4f})."

        # Update match_details with actual results, aligning with TS interface
        match_details["verified"] = system_verification_passed
        match_details["distance"] = f"{distance_val:.4f}"
        match_details["threshold"] = f"{CUSTOM_SYSTEM_THRESHOLD:.4f}" # Show the threshold used by system
        match_details["message"] = current_message
        # Optional: include DeepFace's own assessment for debugging if needed elsewhere
        # match_details["deepface_standard_threshold"] = f"{deepface_internal_threshold_val:.4f}"
        # match_details["deepface_verified_flag"] = deepface_verified_flag_val
        
    except ValueError as ve:
        error_str = str(ve).lower()
        er_msg = ""
        if "face could not be detected" in error_str:
            er_msg = "Face Verification FAILED: Face not detected in live image."
        elif "embedding for face" in error_str and "could not be generated" in error_str:
             er_msg = "Face Verification FAILED: Could not generate embedding for live face."
        else:
            er_msg = f"Face Verification FAILED (ValueError: {str(ve)[:150]})"
        
        match_details["message"] = er_msg
        match_details["verified"] = False # Ensure this is False on error
        print(f"Error during face verification: {ve}")
        if ve.__cause__: print(f"Original cause: {ve.__cause__}")
    except Exception as e_verify:
        er_msg = f"Face Verification FAILED (Unexpected Error: {str(e_verify)[:150]})"
        match_details["message"] = er_msg
        match_details["verified"] = False # Ensure this is False on error
        print(f"Unexpected error during face verification: {e_verify}")
        traceback.print_exc()

    print(f"Face Match Outcome: {match_details['message']}")
    return system_verification_passed, match_details

