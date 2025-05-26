from deepface import DeepFace
import cv2
import traceback
import numpy as np
import time
import json
import sys
import os
import psycopg2
from psycopg2 import sql

# --- Capture an image from webcam ---
def capture_image(filename="live_capture.jpg"):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return None

    print("Camera opened. Look directly at the camera.")
    print("Press 's' to capture the image for verification.")
    print("Press 'q' to quit.")

    window_name = "Capture Frame for Verification"
    cv2.namedWindow(window_name)
    frame_num = 0
    capture_success = False

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Warning: Failed to grab frame.")
            time.sleep(0.1)
            continue

        display_frame = frame.copy()

        if frame_num < 60:
             cv2.putText(display_frame, "Position face centrally. Press 's' when ready.", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        else:
             cv2.putText(display_frame, "Press 's' to capture. Press 'q' to quit.", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

        cv2.imshow(window_name, display_frame)
        frame_num += 1

        key = cv2.waitKey(1) & 0xFF
        if key == ord("s"):
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
                print(f"Image Clarity (Laplacian Variance): {lap_var:.2f}")
                if lap_var < 50:
                    print("Warning: Captured image might be blurry.")

                if cv2.imwrite(filename, frame):
                    print(f"Image saved as {filename}")
                    capture_success = True
                    break
                else:
                    print(f"Error: Failed to save image to {filename}.")
            except Exception as e:
                 print(f"Error during imwrite: {e}")

        elif key == ord("q"):
            print("Capture cancelled by user.")
            filename = None
            break

    cap.release()
    cv2.destroyAllWindows()
    time.sleep(0.5)

    if capture_success:
         return filename
    else:
         return None

# --- Database Configuration ---
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "votechain_db"
DB_USER = "postgres"
DB_PASSWORD = "root"

# --- DeepFace Configuration ---
MODEL_NAME = 'Facenet'
DISTANCE_METRIC = 'cosine'
DETECTOR_BACKEND = 'retinaface'
EXPECTED_EMBEDDING_SHAPE = (128,)

# --- Verification Threshold ---
try:
    VERIFICATION_THRESHOLD = DeepFace.verification.find_threshold(MODEL_NAME, DISTANCE_METRIC)
    print(f"Using threshold for {MODEL_NAME}/{DISTANCE_METRIC}: {VERIFICATION_THRESHOLD:.4f}")
except Exception as e:
     if DISTANCE_METRIC == 'cosine': VERIFICATION_THRESHOLD = 0.40
     elif DISTANCE_METRIC == 'euclidean_l2': VERIFICATION_THRESHOLD = 1.1
     else: VERIFICATION_THRESHOLD = 0.40
     print(f"Warning: Using fallback threshold {VERIFICATION_THRESHOLD:.4f}. Could not get from DeepFace. Error: {e}")

# --- Function to retrieve stored embedding ---
def get_stored_embedding(user_identifier, lookup_column='voter_id_number'):
    conn = None
    cur = None
    embedding = None
    user_details = {}
    allowed_lookup_columns = ['aadhaar_no', 'name', 'voter_id_number', 'pan_no', 'license_no']
    if lookup_column not in allowed_lookup_columns:
        print(f"Error: Invalid lookup column specified: {lookup_column}")
        return None, None
    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        query = sql.SQL("SELECT id, name, card_type, dob, aadhaar_no, pan_no, license_no, voter_id_number, face_embedding FROM user_id_details WHERE {} = %s LIMIT 1").format(sql.Identifier(lookup_column))
        cur.execute(query, (user_identifier,))
        result = cur.fetchone()
        if result:
            keys = ['db_id', 'name', 'card_type', 'dob', 'aadhaar_no', 'pan_no', 'license_no', 'voter_id_number', 'face_embedding_json']
            user_details = dict(zip(keys, result))
            stored_embedding_json = user_details.pop('face_embedding_json', None)
            if stored_embedding_json:
                try:
                    stored_embedding_list = json.loads(stored_embedding_json)
                    embedding = np.array(stored_embedding_list, dtype=np.float32)
                    print(f"Retrieved details and embedding for {user_details.get('name', user_identifier)}")
                except (json.JSONDecodeError, TypeError, ValueError) as e:
                    print(f"Error processing stored JSON embedding for user ({user_identifier}): {e}")
            else:
                 print(f"Embedding not found in DB record for user: {user_identifier}")
        else:
            print(f"No DB record found for user matching {lookup_column}: {user_identifier}")
    except psycopg2.Error as db_err:
        print(f"Database error: {db_err}")
    except Exception as e:
        print(f"An error occurred retrieving embedding: {e}")
        traceback.print_exc() # Added for more detail on general errors
    finally:
        if cur: cur.close()
        if conn: conn.close()
    return embedding, user_details


import re # Ensure re is imported
import sys # Ensure sys is imported for sys.argv and sys.exit

# --- Main Execution ---
if __name__ == "__main__":
    # --- Get User Identifier ---
    lookup_key_column = None # Initialize
    target_user_identifier = None # Initialize

    if len(sys.argv) > 1:
        target_user_identifier_from_arg = sys.argv[1]
        # --- Optional Regex-based type guessing for single command-line arg ---
        # These are preferred ID types if a format matches
        if re.fullmatch(r'\d{12}', target_user_identifier_from_arg):
             lookup_key_column = 'aadhaar_no'
        elif re.fullmatch(r'[A-Z]{5}[0-9]{4}[A-Z]{1}', target_user_identifier_from_arg.upper()):
             lookup_key_column = 'pan_no'
        elif re.fullmatch(r'[A-Z]{3}\d{7}', target_user_identifier_from_arg.upper()) or \
             re.fullmatch(r'[A-Z0-9]{10}', target_user_identifier_from_arg.upper()): # Generic 10 char, could be Voter or PAN
             # If PAN regex didn't match above, this might be Voter ID
             if lookup_key_column != 'pan_no': # Prioritize PAN if it matched its specific regex
                lookup_key_column = 'voter_id_number'
        elif len(target_user_identifier_from_arg) > 5 and len(target_user_identifier_from_arg) < 20 and \
             any(c.isalpha() for c in target_user_identifier_from_arg) and \
             any(c.isdigit() for c in target_user_identifier_from_arg):
            lookup_key_column = 'license_no'
        
        if lookup_key_column: # If regex guessing was successful
            target_user_identifier = target_user_identifier_from_arg
            print(f"Using command line argument: {target_user_identifier} (Auto-determined type: {lookup_key_column})")
        else:
            # If no regex matches, or if you prefer to always confirm for a single arg:
            print(f"Identifier '{target_user_identifier_from_arg}' received from command line. Could not auto-determine type.")
            # Removed 'name' from allowed_lookups for command-line fallback
            allowed_lookups_cmd = ['voter_id_number', 'aadhaar_no', 'pan_no', 'license_no']
            lookup_key_column_input = input(f"Enter the type for '{target_user_identifier_from_arg}' (options: {', '.join(allowed_lookups_cmd)}): ").strip().lower()
            if lookup_key_column_input in allowed_lookups_cmd:
                lookup_key_column = lookup_key_column_input
                target_user_identifier = target_user_identifier_from_arg # Use the ID from command line
            else:
                print("Invalid type entered for command-line ID. Please run again and choose a valid type or provide no arguments for interactive mode.")
                sys.exit(1)
        # --- End of optional regex guessing ---

    else: # Interactive input
        print("\nFor verification, please provide the user's unique identifier.")
        # Removed 'name' from allowed_lookups for interactive mode
        allowed_lookups_interactive = ['voter_id_number', 'aadhaar_no', 'pan_no', 'license_no']
        lookup_key_column = input(f"Enter identifier type ({', '.join(allowed_lookups_interactive)}): ").strip().lower()

        if lookup_key_column not in allowed_lookups_interactive:
             print(f"Invalid identifier type. Please use one of: {', '.join(allowed_lookups_interactive)}")
             sys.exit(1)
        target_user_identifier = input(f"Enter the {lookup_key_column}: ").strip()

    if not target_user_identifier: # Should be caught by earlier exits if type was invalid
         print("Error: No user identifier provided or process aborted.")
         sys.exit(1)

    # Final validation of lookup_key_column (if not already exited)
    # This list now excludes 'name'
    allowed_lookups_final_check = ['voter_id_number', 'aadhaar_no', 'pan_no', 'license_no']
    if lookup_key_column not in allowed_lookups_final_check:
        # This case should ideally be rare if logic above is correct, but good as a safeguard
        print(f"Error: Invalid identifier type '{lookup_key_column}' selected for lookup. Must be one of {', '.join(allowed_lookups_final_check)}")
        sys.exit(1)


    print(f"\nAttempting verification lookup for {lookup_key_column}: {target_user_identifier}")
    # Ensure get_stored_embedding and other subsequent parts of your script are defined
    stored_embedding, user_info = get_stored_embedding(target_user_identifier, lookup_key_column)

    # ... (rest of your script: embedding validation, capture_image, liveness check, face verification) ...

    is_embedding_valid = False
    if stored_embedding is not None and isinstance(stored_embedding, np.ndarray):
        if stored_embedding.shape == EXPECTED_EMBEDDING_SHAPE:
            if np.issubdtype(stored_embedding.dtype, np.floating):
                print("Stored embedding format appears valid.")
                is_embedding_valid = True
            else: print(f"Error: Stored embedding dtype invalid ({stored_embedding.dtype})")
        else: print(f"Error: Stored embedding shape invalid ({stored_embedding.shape})")
    else: print("Error: Stored embedding is missing or not a NumPy array.")

    if not is_embedding_valid:
        print("Cannot proceed without a valid stored embedding.")
        sys.exit(1)

    retrieved_user_name = user_info.get('name', 'Unknown User')
    print(f"\nPlease look at the camera for liveness check and verification against {retrieved_user_name}'s record...")
    live_image_path = capture_image()

    verification_successful = False
    final_message = "Process did not complete."
    liveness_outcome = "Not Performed"
    match_outcome = "Not Performed"
    face_verification_details = {} # For the actual face match

    if live_image_path:
        print(f"\nCaptured image: {live_image_path}")
        print(f"Using Model: {MODEL_NAME}, Metric: {DISTANCE_METRIC}, Detector: {DETECTOR_BACKEND}")
        print(f"Using Verification Threshold: {VERIFICATION_THRESHOLD:.4f}")
        
        
        # --- STAGE 1: LIVENESS CHECK on the live_image_path ---
        print("\n--- Performing Liveness Check ---")
        # For a real run, instruct the user to look live at the camera.
        # For testing spoof, you'd instruct to show a photo/video.
        print("Please look LIVE at the camera.") # Changed instruction for normal operation

        liveness_passed = False
        # Ensure dummy_face_for_liveness.jpg (or .png) exists and is a real face photo
        dummy_image_for_liveness_check = "dummy_face_for_liveness.jpg" # Or .png
        if not os.path.exists(dummy_image_for_liveness_check):
            print(f"CRITICAL ERROR: Dummy image for liveness ('{dummy_image_for_liveness_check}') not found.")
            # In a real app, you might have a default pre-packaged dummy image.
            # For now, we'll exit if it's not there.
            sys.exit(f"Required asset '{dummy_image_for_liveness_check}' is missing.")


        try:
            print(f"Liveness Check: Verifying LIVE_USER_IMAGE ({live_image_path}) against DUMMY_REFERENCE ({dummy_image_for_liveness_check})")
            # This call is primarily for its side effect (raising ValueError on spoof)
            # or returning a dict (which we'll now ignore for liveness status).
            # The 'verified', 'distance' etc. from this call are not relevant for liveness.
            liveness_check_result = DeepFace.verify(
                img1_path=live_image_path,            # Live webcam capture
                img2_path=dummy_image_for_liveness_check, # Dummy real face photo
                model_name=MODEL_NAME,
                detector_backend=DETECTOR_BACKEND,
                distance_metric=DISTANCE_METRIC,
                anti_spoofing=True,
                enforce_detection=True
            )
            # If verify completes WITHOUT raising a "Spoof detected" ValueError,
            # it means no spoof was detected by the exception mechanism.
            # We still check if 'is_spoof' key exists and is True, just in case
            # future DeepFace versions change behavior to use the flag AND raise errors.

            print("\n--- Raw Liveness Check (Verify with Dummy) Result ---")
            try: print(json.dumps(liveness_check_result, indent=2, default=str))
            except TypeError: print(liveness_check_result)
            print("----------------------------------------------------")

            is_spoof_flag_in_result = liveness_check_result.get("is_spoof")
            print(f"DEBUG: 'is_spoof' flag in result dict: {is_spoof_flag_in_result}")

            if is_spoof_flag_in_result is True:
                # This path means an 'is_spoof': True flag was found AND no exception was raised.
                liveness_outcome = "FAILED (Spoof Detected via is_spoof flag)"
                final_message = "Verification FAILED: Liveness check indicates spoof attempt (via is_spoof flag)."
                liveness_passed = False
            else:
                # No "Spoof detected" ValueError was raised, and is_spoof flag is not True.
                # This is the "live" path.
                liveness_outcome = "PASSED"
                final_message = "Liveness check PASSED (no spoof exception, is_spoof flag not True)." # Temp message
                liveness_passed = True
                print("Liveness check PASSED (no spoof exception was raised).")

        
        except ValueError as ve:
            error_str = str(ve) # The message of the top-level ValueError
            original_cause_error_str = ""
            if ve.__cause__: # Check if there's an original cause
                original_cause_error_str = str(ve.__cause__)
            
            print(f"Liveness Check raised ValueError: {ve}")
            if ve.__cause__:
                print(f"Original cause: {ve.__cause__}")
            traceback.print_exc()

            # Check both the direct error message and the original cause
            if "Spoof detected in given image." in error_str or \
               "Spoof detected in given image." in original_cause_error_str:
                 liveness_outcome = "FAILED (Spoof Detected via ValueError)"
                 final_message = "Verification FAILED: Liveness check indicates spoof attempt (detected via ValueError)."
                 liveness_passed = False
            elif "face could not be detected" in error_str.lower() or \
                 ("face could not be detected" in original_cause_error_str.lower() if ve.__cause__ else False):
                final_message = "Liveness Check FAILED: Face not detected in live image or dummy image."
                liveness_outcome = "FAILED (Detection Failed)"
                liveness_passed = False
            else: # Other ValueErrors
                 final_message = f"Liveness Check FAILED (Other ValueError): {ve}"
                 liveness_outcome = "ERROR (Other ValueError)"
                 liveness_passed = False


        # --- STAGE 2: FACE VERIFICATION (only if liveness passed) ---
        if liveness_passed:
            print("\n--- Performing Face Verification against Stored Embedding ---")
            try:
                stored_embedding_as_list = stored_embedding.tolist()

                # Now verify the live image against the stored embedding
                # anti_spoofing is False here as it's already done
                face_verification_details = DeepFace.verify(
                    img1_path=live_image_path,
                    img2_path=stored_embedding_as_list, # Pass the pre-computed embedding
                    model_name=MODEL_NAME,
                    detector_backend=DETECTOR_BACKEND,
                    distance_metric=DISTANCE_METRIC,
                    anti_spoofing=False, # Liveness already checked
                    enforce_detection=True
                )
                print("\n--- Raw Face Verification Result ---")
                try: print(json.dumps(face_verification_details, indent=2, default=str))
                except TypeError: print(face_verification_details)
                print("----------------------------------")

                is_verified = face_verification_details.get("verified")

                if is_verified is True:
                    match_outcome = "PASSED"
                    final_message = f"Verification SUCCESSFUL for {retrieved_user_name}."
                    verification_successful = True
                elif is_verified is False:
                    match_outcome = "FAILED"
                    distance = face_verification_details.get("distance", float('inf'))
                    final_message = f"Verification FAILED for {retrieved_user_name}: Faces do not match (Distance: {distance:.4f} > Threshold: {VERIFICATION_THRESHOLD:.4f})."
                else: # Should not happen
                    match_outcome = "Inconclusive"
                    final_message = "Verification FAILED: Face match result missing after liveness."
            
            except ValueError as ve: # Catch errors from the second verify call
                error_str = str(ve).lower()
                if "face could not be detected" in error_str: # Should be caught by liveness, but defensive
                    final_message = "Face Verification FAILED: Face not detected in live image."
                    match_outcome = "FAILED (Detection Failed)"
                else:
                    final_message = f"Face Verification FAILED (ValueError): {ve}"
                    match_outcome = "ERROR"
                print(f"Stopping. Reason: {final_message}")
                traceback.print_exc()
            except Exception as e:
                final_message = f"An unexpected error occurred during face verification: {e}"
                match_outcome = "ERROR"
                print(f"Stopping. Reason: {final_message}")
                traceback.print_exc()
        else: # Liveness did not pass
            # final_message is already set by the liveness check block
            pass


        # --- Cleanup Live Image ---
        try:
            if live_image_path and os.path.exists(live_image_path):
                os.remove(live_image_path)
                print(f"\nCleaned up temporary image: {live_image_path}")
        except Exception as e:
            print(f"\nWarning: Could not remove temporary image {live_image_path}: {e}")

    else: # live_image_path was None
        print("No image captured. Exiting.")
        final_message = "User cancelled capture."

    print("\n" + "="*30)
    print("  FINAL VERIFICATION RESULT")
    print("="*30)
    print(f"User Identifier Used ({lookup_key_column}): {target_user_identifier}")
    print(f"Verified Against Record For: {retrieved_user_name}")
    print(f"Status: {'SUCCESS' if verification_successful else 'FAILED'}")
    print(f"Message: {final_message}")
    print("-" * 30)
    print(f"Liveness Check Outcome: {liveness_outcome}")
    if liveness_passed: # Only show match details if liveness passed and match was attempted
         dist = face_verification_details.get('distance', float('inf'))
         # Use threshold from face_verification_details if available, else the global one
         thresh = face_verification_details.get('threshold', VERIFICATION_THRESHOLD)
         print(f"Face Match Outcome: {match_outcome}")
         print(f"Verification Distance ({DISTANCE_METRIC}): {dist:.4f}")
         print(f"Verification Threshold Used: {thresh:.4f}")
    print("="*30)