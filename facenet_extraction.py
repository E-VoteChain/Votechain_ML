from google.generativeai import GenerativeModel, configure
from PIL import Image as PIL_Image # Rename to avoid conflict with cv2.Image
import io
import json
import os
import psycopg2
import re
import numpy as np
from deepface import DeepFace
import cv2 # OpenCV for image processing
from psycopg2 import sql
import traceback # Make sure traceback is imported at the top

# ... (your API_KEY and configure call remain the same) ...
API_KEY = "AIzaSyDWRc2RBGhZi6ozJIsYm_BPTwSObDDy6Qg"
configure(api_key=API_KEY)

image_path = "voter_id\\ayush_voter_id.jpg"

# --- DeepFace Configuration for EXTRACTION ---
EXTRACTION_MODEL_NAME = 'Facenet'
DETECTOR_BACKEND = 'retinaface'

def preprocess_face_image(face_image_np):
    """
    Applies various preprocessing techniques to a cropped face image (NumPy array).
    Returns the preprocessed face image (NumPy array).
    """
    print("Preprocessing detected face...")
    processed_face = face_image_np.copy()

    # 1. Ensure 3 Channels (DeepFace models expect RGB)
    if len(processed_face.shape) == 2 or processed_face.shape[2] == 1: # Grayscale
        processed_face = cv2.cvtColor(processed_face, cv2.COLOR_GRAY2BGR)
    elif processed_face.shape[2] == 4: # BGRA/RGBA
        processed_face = cv2.cvtColor(processed_face, cv2.COLOR_BGRA2BGR) # Assuming BGR from OpenCV load

    # 2. Contrast Enhancement (CLAHE on Luminance channel)
    # Convert to LAB color space
    lab = cv2.cvtColor(processed_face, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    limg = cv2.merge((cl, a, b))
    processed_face = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    print("- Applied CLAHE")

    # 3. Denoising (Optional, can sometimes blur too much if not careful)
    # processed_face = cv2.medianBlur(processed_face, 3)
    # print("- Applied Median Blur (denoising)")
    # OR
    # processed_face = cv2.GaussianBlur(processed_face, (5, 5), 0)
    # print("- Applied Gaussian Blur (denoising)")


    # 4. Sharpening (Optional, use cautiously, can amplify noise)
    # kernel_sharpening = np.array([[-1,-1,-1],
    #                               [-1, 9,-1],
    #                               [-1,-1,-1]])
    # processed_face = cv2.filter2D(processed_face, -1, kernel_sharpening)
    # print("- Applied Sharpening")

    # 5. Brightness/Contrast Adjustment (Alternative or addition to CLAHE)
    # alpha = 1.1  # Contrast control (1.0-3.0)
    # beta = 5    # Brightness control (0-100)
    # processed_face = cv2.convertScaleAbs(processed_face, alpha=alpha, beta=beta)
    # print(f"- Adjusted Brightness/Contrast (alpha={alpha}, beta={beta})")

    # (Resizing is typically handled by DeepFace's internal processing when it gets the image,
    # but if you wanted to normalize face size before saving temp image, you could add it here)

    return processed_face


def extract_details_from_id(image_path):
    """
    Extracts text details from an ID card image using the Gemini API,
    detects the face, preprocesses it, and extracts a face embedding.
    """
    try:
        # --- Gemini Text Extraction (remains the same) ---
        pil_img_for_gemini = PIL_Image.open(image_path)
        if pil_img_for_gemini.mode != "RGB":
            pil_img_for_gemini = pil_img_for_gemini.convert("RGB")
        buffer = io.BytesIO()
        pil_img_for_gemini.save(buffer, format="JPEG")
        buffer.seek(0)
        image_data = buffer.read()
        image_part = {"mime_type": "image/jpeg", "data": image_data}

        model_gemini = GenerativeModel("gemini-1.5-flash")
        # ... (your Gemini prompt remains the same) ...
        prompt = """
        You are an expert OCR and document understanding assistant specializing in Indian ID cards. Your primary goal is to accurately extract specific details from the provided ID card image and return them in a structured JSON format.

        First, identify the type of card presented in the image. It will be one of: 'Voter ID', 'Aadhaar card', 'PAN card', or 'Driving License'.

        **CRITICAL INSTRUCTIONS for Aadhaar Cards:**
        1.  Locate the primary **12-digit Aadhaar number**. This number is usually displayed prominently, often formatted in groups (e.g., XXXX XXXX XXXX). This is the number that should go into the `aadhaar_no` field.
        2.  Aadhaar cards also contain a **16-digit Virtual ID (VID)**, which is often explicitly labelled "VID". **DO NOT extract the VID number.** The `aadhaar_no` field must **ONLY** contain the 12-digit main Aadhaar number.
        3.  **DO NOT confuse the 16-digit VID found on Aadhaar cards with the 'Voter ID number'** found on completely different Voter ID cards.

        Return a JSON object containing ONLY the following exact keys. Populate the values based on the information extracted from the card image:

        {
        "card_type": "One of: 'Voter ID', 'Aadhaar card', 'PAN card', 'Driving License'",
        "name": "The full name of the person as printed on the card.",
        "dob": "Date of birth in DD/MM/YYYY or DD-MM-YYYY format. Standardize to DD-MM-YYYY if possible.",
        "aadhaar_no": "The 12-digit primary Aadhaar number ONLY (formatted without spaces if possible). IGNORE the 16-digit VID.",
        "pan_no": "The Permanent Account Number (PAN), if present.",
        "license_no": "The Driving License number, if present.",
        "expiration_date": "The driving license expiration or validity date (e.g., 'Valid Till'), if present.",
        "father_mother_name": "The name listed as Father's Name or Mother's Name, if present.",
        "voter_id_number": "The EPIC number or Voter ID number, ONLY if the card is identified as a 'Voter ID'."
        }

        **Rules:**
        - Only include the keys listed above in your JSON response.
        - If a specific piece of information (like PAN number on an Aadhaar card, or Aadhaar number on a PAN card) is not present on the identified card type, or if it is illegible/unclear, OMIT that key-value pair entirely from the JSON response. Do not use placeholders like 'N/A' or 'Not Found'.
        - Extract numbers accurately and preferably without extra spaces within the number itself (e.g., "751490185308", not "7514 9018 5308").
        - Pay close attention to correctly identifying the main 12-digit Aadhaar number versus the 16-digit VID.
        """
        response = model_gemini.generate_content([prompt, image_part])
        extracted_text = response.text
        cleaned_text = re.sub(r"```json|```", "", extracted_text).strip()
        try:
            details = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response from Gemini: {e}")
            print(f"Raw response text: {cleaned_text}")
            return None
        # --- End Gemini Text Extraction ---


        # --- FACE EXTRACTION, PREPROCESSING & EMBEDDING ---
        print("\n--- Starting Face Processing ---")
        details["face_embedding"] = None # Initialize
        temp_preprocessed_face_path = None # For storing preprocessed face image

        try:
            # 1. Detect faces using DeepFace.extract_faces
            # It returns a list of dictionaries, each with 'face' (numpy array of face),
            # 'facial_area' (coordinates), and 'confidence'.
            print(f"Detecting faces in '{image_path}' using {DETECTOR_BACKEND}...")
            # target_size can be adjusted; DeepFace models have their own input sizes
            # align=True is generally recommended for better embedding quality
            extracted_faces_info = DeepFace.extract_faces(
                img_path=image_path,
                detector_backend=DETECTOR_BACKEND,
                enforce_detection=True, # Ensure at least one face is found
                align=True # Perform facial alignment
            )

            if not extracted_faces_info or not isinstance(extracted_faces_info, list):
                print("No faces detected or unexpected format from extract_faces.")
                return details # Return details without embedding

            # We'll process the first detected face (assuming ID card has one primary face)
            # The 'face' key contains the face image as a NumPy array (BGR format, values 0-255)
            first_face_np_bgr = extracted_faces_info[0]['face']
            
            # Convert face from 0-255 BGR (DeepFace's output) to 0-1 if needed or ensure correct format
            # DeepFace.represent expects image path or a BGR numpy array (0-255 range).
            # The output of extract_faces is already in BGR, 0-255 float, so scale to uint8
            if first_face_np_bgr.dtype == np.float32 or first_face_np_bgr.dtype == np.float64:
                 first_face_np_bgr = (first_face_np_bgr * 255).astype(np.uint8)

            print(f"Face detected. Confidence: {extracted_faces_info[0]['confidence']:.2f}")

            # 2. Preprocess the detected face image
            preprocessed_face_np = preprocess_face_image(first_face_np_bgr)

            # 3. Save the preprocessed face to a temporary file
            # This is necessary because DeepFace.represent primarily takes img_path
            temp_preprocessed_face_path = "temp_preprocessed_face.jpg"
            cv2.imwrite(temp_preprocessed_face_path, preprocessed_face_np)
            print(f"Saved preprocessed face to '{temp_preprocessed_face_path}'")

            # 4. Generate embedding from the preprocessed face image
            print(f"Attempting to extract embedding from preprocessed face using {EXTRACTION_MODEL_NAME}...")
            embedding_objs = DeepFace.represent(
                img_path=temp_preprocessed_face_path, # Use path to preprocessed face
                model_name=EXTRACTION_MODEL_NAME,
                enforce_detection=True, # Should find a face, as it's a cropped face
                detector_backend=DETECTOR_BACKEND # Good to keep consistent, though less critical here
            )

            if embedding_objs and len(embedding_objs) > 0:
                embedding_list = embedding_objs[0]['embedding']
                details["face_embedding"] = json.dumps(embedding_list)
                print(f"Generated {len(embedding_list)}-d embedding from PREPROCESSED face.")
            else:
                print("Failed to generate embedding from preprocessed face.")

        except ValueError as ve:
             if "Face could not be detected" in str(ve) or "No face detected" in str(ve):
                 print(f"Face detection failed: {ve}")
             else:
                 print(f"ValueError during face processing or embedding: {ve}")
                 traceback.print_exc()
        except Exception as e_face:
            print(f"An error occurred during face processing or embedding: {e_face}")
            traceback.print_exc()
        finally:
            # Clean up the temporary preprocessed face image
            if temp_preprocessed_face_path and os.path.exists(temp_preprocessed_face_path):
                try:
                    os.remove(temp_preprocessed_face_path)
                    print(f"Cleaned up temporary file: '{temp_preprocessed_face_path}'")
                except Exception as e_clean:
                    print(f"Warning: Could not remove temporary file '{temp_preprocessed_face_path}': {e_clean}")
        
        return details

    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
        return None
    except Exception as e:
        print(f"An critical error occurred in extract_details_from_id: {e}")
        traceback.print_exc()
        return None

# --- Database Storage Function (remains the same) ---
# ... (your store_id_details function) ...
def store_id_details(details):
    if details is None:
        print("No valid details to store.")
        return

    conn = None
    cur = None
    try:
        conn = psycopg2.connect(
            host="localhost",
            port="5432",
            dbname="votechain_db",
            user="postgres",
            password="root"
        )
        cur = conn.cursor()

        create_table_query = """
        CREATE TABLE IF NOT EXISTS user_id_details (
            id SERIAL PRIMARY KEY,
            card_type VARCHAR(50),
            name VARCHAR(255),
            dob VARCHAR(20),
            aadhaar_no VARCHAR(50) UNIQUE,
            pan_no VARCHAR(50) UNIQUE,
            license_no VARCHAR(50) UNIQUE,
            expiration_date VARCHAR(20),
            father_mother_name VARCHAR(255),
            voter_id_number VARCHAR(50) UNIQUE,
            face_embedding TEXT
        );
        """
        cur.execute(create_table_query)
        conn.commit()

        card_type = details.get("card_type", "Not Found")
        name = details.get("name", "Not Found")
        dob = details.get("dob", None)
        aadhaar_no = details.get("aadhaar_no")
        if aadhaar_no: aadhaar_no = re.sub(r'\s+', '', str(aadhaar_no))

        pan_no = details.get("pan_no")
        if pan_no: pan_no = re.sub(r'\s+', '', str(pan_no))

        license_no = details.get("license_no")
        if license_no: license_no = re.sub(r'\s+', '', str(license_no))

        expiration_date = details.get("expiration_date", None)
        father_mother_name = details.get("father_mother_name", None)

        voter_id_number = details.get("voter_id_number")
        if voter_id_number: voter_id_number = re.sub(r'\s+', '', str(voter_id_number))

        face_embedding = details.get("face_embedding", None)

        conflict_target = None
        # conflict_value = None # Not directly used in simplified UPSERT
        if card_type == 'Aadhaar card' and aadhaar_no:
            conflict_target = sql.Identifier('aadhaar_no')
            # conflict_value = aadhaar_no
        elif card_type == 'Voter ID' and voter_id_number:
            conflict_target = sql.Identifier('voter_id_number')
            # conflict_value = voter_id_number
        elif card_type == 'PAN card' and pan_no:
            conflict_target = sql.Identifier('pan_no')
            # conflict_value = pan_no
        elif card_type == 'Driving License' and license_no:
            conflict_target = sql.Identifier('license_no')
            # conflict_value = license_no
        
        if conflict_target is None:
             print("Warning: Could not determine primary unique identifier for UPSERT. Attempting plain INSERT.")
             insert_query_plain = sql.SQL("""
             INSERT INTO user_id_details
             (card_type, name, dob, aadhaar_no, pan_no, license_no, expiration_date, father_mother_name, voter_id_number, face_embedding)
             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
             """)
             cur.execute(insert_query_plain, (
                 card_type, name, dob, aadhaar_no, pan_no, license_no, expiration_date, father_mother_name, voter_id_number, face_embedding
             ))
        else:
             upsert_query = sql.SQL("""
             INSERT INTO user_id_details
             (card_type, name, dob, aadhaar_no, pan_no, license_no, expiration_date, father_mother_name, voter_id_number, face_embedding)
             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
             ON CONFLICT ({})
             DO UPDATE SET
                 card_type = EXCLUDED.card_type,
                 name = EXCLUDED.name,
                 dob = EXCLUDED.dob,
                 aadhaar_no = CASE WHEN EXCLUDED.aadhaar_no IS NOT NULL THEN EXCLUDED.aadhaar_no ELSE user_id_details.aadhaar_no END,
                 pan_no = CASE WHEN EXCLUDED.pan_no IS NOT NULL THEN EXCLUDED.pan_no ELSE user_id_details.pan_no END,
                 license_no = CASE WHEN EXCLUDED.license_no IS NOT NULL THEN EXCLUDED.license_no ELSE user_id_details.license_no END,
                 voter_id_number = CASE WHEN EXCLUDED.voter_id_number IS NOT NULL THEN EXCLUDED.voter_id_number ELSE user_id_details.voter_id_number END,
                 expiration_date = EXCLUDED.expiration_date,
                 father_mother_name = EXCLUDED.father_mother_name,
                 face_embedding = EXCLUDED.face_embedding;
             """).format(conflict_target)
             cur.execute(upsert_query, (
                 card_type, name, dob, aadhaar_no, pan_no, license_no,
                 expiration_date, father_mother_name, voter_id_number, face_embedding
             ))
        conn.commit()
        print("Details inserted/updated successfully using UPSERT logic.")
    except psycopg2.Error as db_err:
        print(f"Database error during UPSERT: {db_err}")
        traceback.print_exc()
    except Exception as e:
        print(f"An unexpected error occurred while storing details: {e}")
        traceback.print_exc()
    finally:
        if cur: cur.close()
        if conn: conn.close()

# --- Main Execution Block ---
if __name__ == '__main__':
    # Make sure image_path is defined before calling functions that use it.
    # Example:
    # image_path = "path/to/your/id_card_image.png"
    if not os.path.exists(image_path): # Add a check for image_path if it's hardcoded
        print(f"ERROR: Main image_path '{image_path}' not found. Please set it correctly.")
        exit()


    extracted_info = extract_details_from_id(image_path)

    if extracted_info:
        print("\n--- Extracted Information ---")
        for key, value in extracted_info.items():
            if key == "face_embedding" and value is not None:
                 print(f"- {key}: Present (Type: {type(json.loads(value))}, Length: {len(json.loads(value))})") # Show type and length
            elif key == "face_embedding" and value is None:
                 print(f"- {key}: Not Generated/Found")
            else:
                 print(f"- {key}: {value}")
        print("-" * 27)
        store_id_details(extracted_info)
    else:
        print("\nNo valid information extracted from the ID card.")