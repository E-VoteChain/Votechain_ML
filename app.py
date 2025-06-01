# # app.py
# import os
# from flask import Flask, request, jsonify
# from flask_cors import CORS
# from werkzeug.utils import secure_filename
# import uuid # For generating unique filenames
# from dotenv import load_dotenv
# from google.generativeai import GenerativeModel, configure as configure_gemini # Renamed configure
# import traceback

# # Import your ML logic modules
# from ml_logic import id_card_processor
# from ml_logic import face_verifier
# from ml_logic import db_storer

# # --- Configuration ---
# load_dotenv() # Load .env file for local development

# # Gemini Configuration
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# if GEMINI_API_KEY:
#     configure_gemini(api_key=GEMINI_API_KEY)
#     gemini_model_instance = GenerativeModel("gemini-1.5-flash") # Or your preferred model
# else:
#     print("CRITICAL: GEMINI_API_KEY not found. OCR functionality will fail.")
#     gemini_model_instance = None # Handle this appropriately

# # File Upload Configuration
# UPLOAD_FOLDER = 'uploads' # Make sure this folder exists
# ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
# if not os.path.exists(UPLOAD_FOLDER):
#     os.makedirs(UPLOAD_FOLDER)

# # Liveness Reference Image
# DUMMY_LIVENESS_REF_IMAGE = os.path.join(os.path.dirname(__file__), "dummy_face_for_liveness.jpg")
# if not os.path.exists(DUMMY_LIVENESS_REF_IMAGE):
#     print(f"CRITICAL WARNING: Dummy liveness reference image not found at {DUMMY_LIVENESS_REF_IMAGE}")
#     # You might want to exit or have a fallback if this is critical for deployment


# app = Flask(__name__)
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB upload limit
# CORS(app) # Enable CORS for all routes, good for development

# def allowed_file(filename):
#     return '.' in filename and \
#            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# # <<< Initialize Database Table on App Start >>>
# with app.app_context(): # Ensures this runs within Flask's application context
#     db_storer.create_user_table_if_not_exists()
    
    
    
# # In app.py
# @app.route('/healthz', methods=['GET'])
# def health_check():
#     return jsonify({"status": "healthy"}), 200


# @app.route('/process_and_verify', methods=['POST'])
# def process_and_verify_endpoint():
#     if gemini_model_instance is None:
#         return jsonify({"error": "OCR service not available due to missing API key."}), 503

#     if 'id_card_image' not in request.files or 'live_face_image' not in request.files:
#         return jsonify({"error": "Missing id_card_image or live_face_image file"}), 400

#     id_card_file = request.files['id_card_image']
#     live_face_file = request.files['live_face_image']

#     if id_card_file.filename == '' or live_face_file.filename == '':
#         return jsonify({"error": "No selected file"}), 400

#     id_card_path = None
#     live_face_path = None
#     response_data = {
#         "text_details": None,
#         "id_card_processing_status": "Not Processed",
#         "liveness_check": {"passed": False, "status": "Not Performed"},
#         "face_verification": {"verified": False, "status": "Not Performed"},
#         "database_storage": {"stored": False, "message": "Not Attempted"},
#         "overall_status": "Failed"
#     }
    
#     # Initialize db_success and db_message to safe defaults
#     db_success = False
#     db_message = "Database operation not reached or failed early."

#     try:
#         if id_card_file and allowed_file(id_card_file.filename) and \
#            live_face_file and allowed_file(live_face_file.filename):
            
#             # Secure filenames and save temporarily
#             id_filename_secure = secure_filename(f"{uuid.uuid4()}_{id_card_file.filename}")
#             live_filename_secure = secure_filename(f"{uuid.uuid4()}_{live_face_file.filename}")
            
#             id_card_path = os.path.join(app.config['UPLOAD_FOLDER'], id_filename_secure)
#             live_face_path = os.path.join(app.config['UPLOAD_FOLDER'], live_filename_secure)
            
#             id_card_file.save(id_card_path)
#             live_face_file.save(live_face_path)
#             print(f"ID Card saved to: {id_card_path}")
#             print(f"Live Face saved to: {live_face_path}")

#             # --- STAGE 1: Process ID Card (OCR and Face Embedding) ---
#             print("\n>>> Processing ID Card...")
#             extracted_details, id_embedding = id_card_processor.extract_text_and_face_from_id(
#                 id_card_path, gemini_model_instance
#             )
#             response_data["text_details"] = extracted_details
#             if "error" in extracted_details or "id_processing_error" in extracted_details:
#                  response_data["id_card_processing_status"] = f"Failed: {extracted_details.get('error', extracted_details.get('id_processing_error', 'Unknown ID processing error'))}"
#             elif id_embedding is None:
#                  response_data["id_card_processing_status"] = "Failed: Could not get face embedding from ID card."
#             else:
#                  response_data["id_card_processing_status"] = "Successfully processed ID card text and face."
            
#             if id_embedding is None: # Critical failure for next steps
#                 response_data["overall_status"] = "Failed at ID card processing."
#                 return jsonify(response_data), 422 # Unprocessable Entity

#             # --- STAGE 2: Liveness Check on Live Face Image ---
#             print("\n>>> Performing Liveness Check...")
#             liveness_passed, liveness_status_msg = face_verifier.perform_liveness_check(
#                 live_face_path, DUMMY_LIVENESS_REF_IMAGE
#             )
#             response_data["liveness_check"]["passed"] = liveness_passed
#             response_data["liveness_check"]["status"] = liveness_status_msg

#             if not liveness_passed:
#                 response_data["overall_status"] = "Failed: Liveness check failed."
#                 return jsonify(response_data), 403 # Forbidden (spoof or error)

#             # --- STAGE 3: Face Verification (Live Face vs ID Card Face Embedding) ---
#             print("\n>>> Performing Face Verification...")
#             verification_passed, verification_details_dict = face_verifier.verify_faces(
#                 live_face_path, id_embedding
#             )
#             response_data["face_verification"] = verification_details_dict # Contains 'verified' and 'message'
#             response_data["face_verification"]["status"] = verification_details_dict.get("message", "Status Unknown")


#             if verification_passed: # This is the condition for attempting DB storage
#                 # response_data["overall_status"] = "Success: Liveness and Face Verification Passed." # Moved this down
                
#                 print("\n>>> Storing verified user details in database...")
#                 try: # Add a specific try-except around database operation
#                     db_success, db_message = db_storer.store_verified_user_details(
#                         extracted_details, id_embedding
#                     )
#                     response_data["database_storage"]["stored"] = db_success
#                     response_data["database_storage"]["message"] = db_message
#                 except Exception as db_op_error:
#                     print(f"Error during database storage operation call: {db_op_error}")
#                     traceback.print_exc()
#                     db_success = False # Ensure it's False
#                     db_message = f"Error during database storage: {str(db_op_error)}"
#                     response_data["database_storage"]["stored"] = False
#                     response_data["database_storage"]["message"] = db_message
                
#                 if db_success:
#                     response_data["overall_status"] = "Success: Liveness, Face Verification, and Database Storage Passed."
#                 else:
#                     response_data["overall_status"] = "Success: Liveness and Face Verification Passed (Warning: Database storage failed)"
#                     print(f"Warning: Database storage failed: {db_message}")
                
#                 # ... (cleanup and return jsonify(response_data), 200) ...
#                 # (Ensure cleanup happens before return)
#                 if id_card_path and os.path.exists(id_card_path): os.remove(id_card_path)
#                 if live_face_path and os.path.exists(live_face_path): os.remove(live_face_path)
#                 return jsonify(response_data), 200
#             else: # verification_passed is False
#                 response_data["overall_status"] = "Failed: Face verification failed."
#                 # ... (cleanup and return jsonify(response_data), 403) ...
#                 if id_card_path and os.path.exists(id_card_path): os.remove(id_card_path)
#                 if live_face_path and os.path.exists(live_face_path): os.remove(live_face_path)
#                 return jsonify(response_data), 403
#         # ... (else for file type not allowed) ...

#     except Exception as e:
#         print(f"Unhandled error in /process_and_verify: {e}")
#         traceback.print_exc()
#         # Ensure response_data["overall_status"] is updated robustly
#         # response_data["database_storage"] is already initialized, so accessing its keys should be fine.
#         # The error might be before db_message is properly set if the exception is not from the DB part.
#         response_data["overall_status"] = f"Server Error: {str(e)}"
#         if 'message' not in response_data["database_storage"] or response_data["database_storage"]["message"] == "Not Attempted":
#             response_data["database_storage"]["message"] = "Database operation likely not reached due to earlier error."
        
#         # ... (cleanup) ...
#         if id_card_path and os.path.exists(id_card_path):
#             try: os.remove(id_card_path)
#             except Exception as e_clean: print(f"Error cleaning ID file on exception: {e_clean}")
#         if live_face_path and os.path.exists(live_face_path):
#             try: os.remove(live_face_path)
#             except Exception as e_clean: print(f"Error cleaning live face file on exception: {e_clean}")
#         return jsonify(response_data), 500

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)

















# app.py
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import uuid
from dotenv import load_dotenv
from google.generativeai import GenerativeModel, configure as configure_gemini
import traceback
import logging # Import the logging module

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Import your ML logic modules
from ml_logic import id_card_processor
from ml_logic import face_verifier
from ml_logic import db_storer

# --- Configuration ---
print("Starting Flask app initialization...") # New Log
logging.info("Starting Flask app initialization...")

load_dotenv()

# Gemini Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    try:
        configure_gemini(api_key=GEMINI_API_KEY)
        gemini_model_instance = GenerativeModel("gemini-1.5-flash")
        logging.info("Gemini configured successfully.")
    except Exception as e:
        logging.critical(f"CRITICAL: Error configuring Gemini: {e}")
        gemini_model_instance = None
else:
    logging.critical("CRITICAL: GEMINI_API_KEY not found. OCR functionality will fail.")
    gemini_model_instance = None

# File Upload Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
if not os.path.exists(UPLOAD_FOLDER):
    try:
        os.makedirs(UPLOAD_FOLDER)
        logging.info(f"Upload folder '{UPLOAD_FOLDER}' created.")
    except OSError as e:
        logging.critical(f"Could not create upload folder '{UPLOAD_FOLDER}': {e}")
        # Decide if this is a fatal error for your app

# Liveness Reference Image
DUMMY_LIVENESS_REF_IMAGE = os.path.join(os.path.dirname(__file__), "dummy_face_for_liveness.jpg")
if not os.path.exists(DUMMY_LIVENESS_REF_IMAGE):
    logging.warning(f"WARNING: Dummy liveness reference image not found at {DUMMY_LIVENESS_REF_IMAGE}")
    # Consider if the app can run without it or if it should be fatal

# --- Flask App Creation ---
logging.info("Creating Flask app instance...")
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
CORS(app)
logging.info("Flask app instance created and CORS enabled.")

# --- Database Initialization ---
# This should be done ONCE when the application starts.
# Gunicorn will typically create multiple worker processes. Each worker
# will run this initialization code.
# The `IF NOT EXISTS` in your SQL handles concurrent table creation attempts.
           
           
def allowed_file(filename):
    """Checks if the uploaded file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def initialize_database():
    logging.info("Attempting to initialize database table...")
    try:
        db_storer.create_user_table_if_not_exists()
        # The success/failure print is inside create_user_table_if_not_exists
    except Exception as e:
        logging.critical(f"CRITICAL ERROR during database initialization: {e}")
        traceback.print_exc()
        # Depending on the severity, you might want to exit or prevent app from starting
        # For now, we'll let it continue and it will likely fail on DB operations.

# Call database initialization
# This will run for each Gunicorn worker process when it starts.
initialize_database()
logging.info("Database initialization routine completed.")


# --- Routes ---
# (Your routes remain largely the same, but I'll add a few logging points)
# In app.py
@app.route('/healthz', methods=['GET'])
def health_check():
    # You could add a simple DB ping here to check DB connectivity too
    # e.g., try: db_storer.ping_db(); except: return "unhealthy"
    logging.debug("Health check endpoint called.")
    return jsonify({"status": "healthy"}), 200


@app.route('/process_and_verify', methods=['POST'])
def process_and_verify_endpoint():
    logging.info("Received request for /process_and_verify")
    if gemini_model_instance is None:
        logging.error("OCR service unavailable due to missing API key or config error.")
        return jsonify({"error": "OCR service not available."}), 503

    if 'id_card_image' not in request.files or 'live_face_image' not in request.files:
        logging.warning("Missing id_card_image or live_face_image in request.")
        return jsonify({"error": "Missing id_card_image or live_face_image file"}), 400

    id_card_file = request.files['id_card_image']
    live_face_file = request.files['live_face_image']

    if id_card_file.filename == '' or live_face_file.filename == '':
        logging.warning("Empty filename for uploaded file(s).")
        return jsonify({"error": "No selected file"}), 400

    id_card_path = None
    live_face_path = None
    # Initialize response_data with more detail for each step
    response_data = {
        "text_details": None,
        "id_card_processing": {"status": "Not Processed", "message": ""},
        "liveness_check": {"passed": False, "status": "Not Performed", "message": ""},
        "face_verification": {"verified": False, "status": "Not Performed", "message": ""},
        "database_storage": {"stored": False, "status": "Not Attempted", "message": ""},
        "overall_status": "Pending"
    }
    
    try:
        if id_card_file and allowed_file(id_card_file.filename) and \
           live_face_file and allowed_file(live_face_file.filename):
            
            id_filename_secure = secure_filename(f"{uuid.uuid4()}_{id_card_file.filename}")
            live_filename_secure = secure_filename(f"{uuid.uuid4()}_{live_face_file.filename}")
            
            id_card_path = os.path.join(app.config['UPLOAD_FOLDER'], id_filename_secure)
            live_face_path = os.path.join(app.config['UPLOAD_FOLDER'], live_filename_secure)
            
            id_card_file.save(id_card_path)
            live_face_file.save(live_face_path)
            logging.info(f"ID Card saved to: {id_card_path}")
            logging.info(f"Live Face saved to: {live_face_path}")

            # --- STAGE 1: Process ID Card ---
            logging.info("Processing ID Card...")
            extracted_details, id_embedding = id_card_processor.extract_text_and_face_from_id(
                id_card_path, gemini_model_instance
            )
            response_data["text_details"] = extracted_details
            if isinstance(extracted_details, dict) and ("error" in extracted_details or "id_processing_error" in extracted_details):
                 err_msg = extracted_details.get('error', extracted_details.get('id_processing_error', 'Unknown ID processing error'))
                 response_data["id_card_processing"]["status"] = "Failed"
                 response_data["id_card_processing"]["message"] = err_msg
                 logging.error(f"ID Card Processing Failed: {err_msg}")
            elif id_embedding is None:
                 response_data["id_card_processing"]["status"] = "Failed"
                 response_data["id_card_processing"]["message"] = "Could not get face embedding from ID card."
                 logging.error("ID Card Processing Failed: No face embedding from ID.")
            else:
                 response_data["id_card_processing"]["status"] = "Success"
                 response_data["id_card_processing"]["message"] = "Successfully processed ID card text and face."
                 logging.info("ID Card processed successfully.")
            
            if id_embedding is None:
                response_data["overall_status"] = "Failed: Critical error in ID card processing."
                # No return here yet, cleanup happens at the end of try or in finally

            # --- STAGE 2: Liveness Check (only if ID embedding was successful) ---
            if id_embedding is not None:
                logging.info("Performing Liveness Check...")
                liveness_passed, liveness_status_msg = face_verifier.perform_liveness_check(
                    live_face_path, DUMMY_LIVENESS_REF_IMAGE # Ensure this image is in your Docker image
                )
                response_data["liveness_check"]["passed"] = liveness_passed
                response_data["liveness_check"]["message"] = liveness_status_msg
                response_data["liveness_check"]["status"] = "Completed"
                if not liveness_passed:
                    logging.warning(f"Liveness Check Failed: {liveness_status_msg}")
                    response_data["overall_status"] = "Failed: Liveness check failed."
                else:
                    logging.info("Liveness Check Passed.")
            else: # id_embedding is None
                response_data["liveness_check"]["status"] = "Skipped due to ID processing failure"


            # --- STAGE 3: Face Verification (only if ID embedding and Liveness passed) ---
            if id_embedding is not None and response_data["liveness_check"]["passed"]:
                logging.info("Performing Face Verification...")
                # verify_faces should return a dict like: {"verified": True/False, "message": "...", "distance": 0.x}
                verification_details_dict = face_verifier.verify_faces(
                    live_face_path, id_embedding
                )
                response_data["face_verification"] = verification_details_dict
                response_data["face_verification"]["status"] = "Completed" # Or Failed based on verification_details_dict["verified"]
                if not verification_details_dict.get("verified"):
                    logging.warning(f"Face Verification Failed: {verification_details_dict.get('message')}")
                    response_data["overall_status"] = "Failed: Face verification failed."
                else:
                    logging.info("Face Verification Passed.")
            elif id_embedding is None:
                response_data["face_verification"]["status"] = "Skipped due to ID processing failure"
            else: # Liveness failed
                response_data["face_verification"]["status"] = "Skipped due to Liveness failure"


            # --- STAGE 4: Database Storage (only if all previous critical steps passed) ---
            if id_embedding is not None and \
               response_data["liveness_check"]["passed"] and \
               response_data["face_verification"].get("verified"):
                
                logging.info("Storing verified user details in database...")
                db_success, db_message = db_storer.store_verified_user_details(
                    extracted_details, id_embedding # Make sure id_embedding is list if db_storer expects list
                )
                response_data["database_storage"]["stored"] = db_success
                response_data["database_storage"]["message"] = db_message
                response_data["database_storage"]["status"] = "Attempted"
                if db_success:
                    logging.info(f"Database Storage Success: {db_message}")
                    response_data["overall_status"] = "Success: All checks passed and data stored."
                    http_status_code = 200
                else:
                    logging.error(f"Database Storage Failed: {db_message}")
                    response_data["overall_status"] = "Partial Success: Verification passed but database storage failed."
                    http_status_code = 207 # Multi-Status, or 200 with error in body
            
            elif response_data["overall_status"] == "Pending": # No critical failure yet but not all conditions met for DB
                if id_embedding is None:
                    response_data["overall_status"] = "Failed: ID Card Processing Incomplete."
                elif not response_data["liveness_check"]["passed"]:
                    response_data["overall_status"] = "Failed: Liveness Check Failed."
                elif not response_data["face_verification"].get("verified"):
                    response_data["overall_status"] = "Failed: Face Verification Failed."
                http_status_code = 422 # Unprocessable Entity if a step failed
            
            if response_data["overall_status"].startswith("Failed"):
                http_status_code = 400 # Or more specific like 403, 422 depending on failure
            elif not response_data["database_storage"].get("stored", False) and \
                     response_data["overall_status"].startswith("Partial Success"):
                http_status_code = 207
            else: # Full success
                http_status_code = 200
                
            return jsonify(response_data), http_status_code
        
        else: # File not allowed
            logging.warning("Uploaded file type not allowed.")
            response_data["overall_status"] = "Failed: Invalid file type."
            return jsonify(response_data), 400

    except Exception as e:
        logging.critical(f"Unhandled error in /process_and_verify: {e}", exc_info=True) # exc_info=True logs traceback
        response_data["overall_status"] = f"Server Error: An unexpected error occurred."
        response_data["id_card_processing"]["message"] = response_data["id_card_processing"].get("message") or "Error occurred before or during this step."
        # ... (similar for other steps)
        return jsonify(response_data), 500
    finally:
        # Cleanup uploaded files
        logging.debug("Cleaning up temporary files...")
        if id_card_path and os.path.exists(id_card_path):
            try: os.remove(id_card_path)
            except Exception as e_clean: logging.error(f"Error cleaning ID file: {e_clean}")
        if live_face_path and os.path.exists(live_face_path):
            try: os.remove(live_face_path)
            except Exception as e_clean: logging.error(f"Error cleaning live face file: {e_clean}")
        logging.info(f"Finished request for /process_and_verify. Overall status: {response_data.get('overall_status')}")


if __name__ == '__main__':
    logging.info("Starting Flask development server...")
    # Ensure PORT is an int for app.run, getenv returns string
    port = int(os.getenv('PORT', 5000)) # Heroku/Railway often set PORT
    app.run(host='0.0.0.0', port=port, debug=True) # debug=True for dev only
else:
    # This block is for when Gunicorn (or another WSGI server) imports app.py
    # You might want to do Gunicorn-specific logging setup here if needed.
    logging.info("Flask app module loaded (likely by WSGI server like Gunicorn).")

print("Flask app module execution completed.") # New Log
logging.info("Flask app module execution completed (end of app.py).")