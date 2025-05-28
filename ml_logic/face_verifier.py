# ml_logic/face_verifier.py
from deepface import DeepFace
import numpy as np
import traceback
import os
import json # For printing results if needed

# Configuration (can be passed or set as constants)
VERIFICATION_MODEL_NAME = 'Facenet' # Must match model used for ID card embedding
DISTANCE_METRIC = 'cosine'
DETECTOR_BACKEND_LIVE = 'retinaface' # For live face detection

try:
    VERIFICATION_THRESHOLD = DeepFace.verification.find_threshold(VERIFICATION_MODEL_NAME, DISTANCE_METRIC)
except Exception:
    VERIFICATION_THRESHOLD = 0.40 # Fallback for cosine, adjust if using other metrics
    print(f"Warning: Using fallback threshold {VERIFICATION_THRESHOLD} for {VERIFICATION_MODEL_NAME}/{DISTANCE_METRIC}")


def perform_liveness_check(live_image_path, dummy_reference_image_path):
    """
    Performs liveness check on the live_image_path using DeepFace's anti_spoofing.
    Args:
        live_image_path (str): Path to the live captured face image.
        dummy_reference_image_path (str): Path to a dummy real face photo for reference.
    Returns:
        tuple: (liveness_passed (bool), liveness_outcome_message (str))
    """
    print(f"\n--- Performing Liveness Check on: {live_image_path} ---")
    liveness_passed = False
    liveness_outcome = "Not Performed"

    if not os.path.exists(dummy_reference_image_path):
        print(f"CRITICAL ERROR: Dummy liveness reference image not found at '{dummy_reference_image_path}'")
        return False, "Liveness FAILED: System configuration error (missing reference image)."

    try:
        # The verify call for liveness raises ValueError on spoof.
        # The actual 'verified' result against the dummy image is not what we care about for liveness,
        # only whether it raises a spoofing error or has 'is_spoof': True.
        liveness_result_dict = DeepFace.verify(
            img1_path=live_image_path,
            img2_path=dummy_reference_image_path, # Reference against a known live face image
            model_name=VERIFICATION_MODEL_NAME,   # Model doesn't matter as much for spoof
            detector_backend=DETECTOR_BACKEND_LIVE,
            distance_metric=DISTANCE_METRIC,      # Metric doesn't matter as much for spoof
            anti_spoofing=True,
            enforce_detection=True # Ensure faces are detected in both
        )
        print(f"Liveness check (DeepFace.verify) raw result: {json.dumps(liveness_result_dict, default=str)}")

        # If anti_spoofing is True, 'is_spoof' key should be present.
        is_spoof_flag = liveness_result_dict.get("is_spoof", False) # Default to False if key missing

        if is_spoof_flag:
            liveness_outcome = "FAILED (Spoof Detected via 'is_spoof' flag)"
            liveness_passed = False
        else:
            # No ValueError and is_spoof is False means live
            liveness_outcome = "PASSED"
            liveness_passed = True
        
    except ValueError as ve:
        error_str = str(ve)
        original_cause_error_str = str(ve.__cause__) if ve.__cause__ else ""
        print(f"Liveness Check raised ValueError: {ve}")
        if ve.__cause__: print(f"Original cause: {ve.__cause__}")
        
        if "Spoof detected" in error_str or "Spoof detected" in original_cause_error_str:
            liveness_outcome = "FAILED (Spoof Detected via ValueError)"
        elif "face could not be detected" in error_str.lower() or \
             ("face could not be detected" in original_cause_error_str.lower()):
            liveness_outcome = "FAILED (Face Detection Error during Liveness)"
        else:
            liveness_outcome = f"ERROR (Other ValueError: {error_str[:100]})"
        liveness_passed = False
    except Exception as e_live:
        print(f"Unexpected error during liveness check: {e_live}")
        traceback.print_exc()
        liveness_outcome = f"ERROR (Unexpected: {str(e_live)[:100]})"
        liveness_passed = False
        
    print(f"Liveness Outcome: {liveness_outcome}")
    return liveness_passed, liveness_outcome


def verify_faces(live_image_path, id_card_embedding_list):
    """
    Verifies the face in live_image_path against the stored id_card_embedding.
    Args:
        live_image_path (str): Path to the live captured face image.
        id_card_embedding_list (list): The embedding list from the ID card.
    Returns:
        tuple: (verification_passed (bool), verification_details (dict))
    """
    print(f"\n--- Performing Face Verification: Live vs ID Card ---")
    verification_passed = False
    match_details = {"message": "Verification not fully performed"}

    if id_card_embedding_list is None:
        match_details["message"] = "Cannot verify: Missing ID card embedding."
        return False, match_details

    try:
        # Verify live image against the pre-computed ID embedding
        # anti_spoofing is False here as liveness is a separate step
        result = DeepFace.verify(
            img1_path=live_image_path,
            img2_path=id_card_embedding_list, # Pass the pre-computed embedding
            model_name=VERIFICATION_MODEL_NAME,
            detector_backend=DETECTOR_BACKEND_LIVE,
            distance_metric=DISTANCE_METRIC,
            anti_spoofing=False, # Liveness already checked
            enforce_detection=True # Ensure face detected in live image
        )
        print(f"Face verification (DeepFace.verify) raw result: {json.dumps(result, default=str)}")

        is_verified = result.get("verified", False)
        distance = result.get("distance", float('inf'))
        threshold = result.get("threshold", VERIFICATION_THRESHOLD) # Use threshold from result if available

        match_details = {
            "verified": is_verified,
            "distance": f"{distance:.4f}",
            "threshold": f"{threshold:.4f}",
            "model": VERIFICATION_MODEL_NAME,
            "metric": DISTANCE_METRIC
        }

        if is_verified:
            match_details["message"] = "Face Verification PASSED."
            verification_passed = True
        else:
            match_details["message"] = f"Face Verification FAILED (Distance: {distance:.4f} > Threshold: {threshold:.4f})."
        
    except ValueError as ve:
        error_str = str(ve).lower()
        if "face could not be detected" in error_str:
            match_details["message"] = "Face Verification FAILED: Face not detected in live image."
        elif "embedding for face" in error_str and "could not be generated" in error_str: # For live image
             match_details["message"] = "Face Verification FAILED: Could not generate embedding for live face."
        else:
            match_details["message"] = f"Face Verification FAILED (ValueError: {str(ve)[:100]})"
        print(f"Error during face verification: {ve}")
        traceback.print_exc()
    except Exception as e_verify:
        match_details["message"] = f"Face Verification FAILED (Unexpected Error: {str(e_verify)[:100]})"
        print(f"Unexpected error during face verification: {e_verify}")
        traceback.print_exc()

    print(f"Face Match Outcome: {match_details['message']}")
    return verification_passed, match_details