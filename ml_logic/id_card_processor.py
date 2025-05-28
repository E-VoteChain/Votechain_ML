# ml_logic/id_card_processor.py
from google.generativeai import GenerativeModel # Removed configure here, will be done in app.py
from PIL import Image as PIL_Image
import io
import json
import os
import re
import numpy as np
from deepface import DeepFace
import cv2
import traceback

# Configuration (can be passed from app.py or set as constants)
EXTRACTION_MODEL_NAME = 'Facenet' # Or VGG-Face, Facenet512 etc.
DETECTOR_BACKEND_ID = 'retinaface' # For ID card face detection
# Note: Ensure this DETECTOR_BACKEND_ID is robust for ID photos. 'mtcnn' or 'ssd' might also be options.

def preprocess_face_image_for_id(face_image_np):
    """ Preprocessing specific for ID card faces. """
    print("Preprocessing ID card face...")
    processed_face = face_image_np.copy()
    if len(processed_face.shape) == 2 or processed_face.shape[2] == 1:
        processed_face = cv2.cvtColor(processed_face, cv2.COLOR_GRAY2BGR)
    elif processed_face.shape[2] == 4:
        processed_face = cv2.cvtColor(processed_face, cv2.COLOR_BGRA2BGR)

    lab = cv2.cvtColor(processed_face, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)) # Slightly stronger CLAHE
    cl = clahe.apply(l)
    limg = cv2.merge((cl, a, b))
    processed_face = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    print("- Applied CLAHE for ID face")
    return processed_face

def extract_text_and_face_from_id(image_path, gemini_model):
    """
    Extracts text details using Gemini and face embedding from an ID card image.
    Args:
        image_path (str): Path to the ID card image.
        gemini_model (GenerativeModel): Initialized Gemini model instance.
    Returns:
        tuple: (details_dict, id_face_embedding_list or None)
               details_dict contains text info, id_face_embedding_list is the facial embedding.
    """
    print(f"\n--- Processing ID Card: {image_path} ---")
    details_dict = {}
    id_face_embedding_list = None
    temp_preprocessed_face_path_id = None

    try:
        # --- Gemini Text Extraction ---
        pil_img_for_gemini = PIL_Image.open(image_path)
        if pil_img_for_gemini.mode != "RGB":
            pil_img_for_gemini = pil_img_for_gemini.convert("RGB")
        buffer = io.BytesIO()
        pil_img_for_gemini.save(buffer, format="JPEG") # Use JPEG for consistency
        buffer.seek(0)
        image_data = buffer.read()
        image_part = {"mime_type": "image/jpeg", "data": image_data}

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
        """ # Your detailed Gemini prompt
        response = gemini_model.generate_content([prompt, image_part])
        extracted_text = response.text
        cleaned_text = re.sub(r"```json|```", "", extracted_text).strip()
        try:
            details_dict = json.loads(cleaned_text)
            print(f"Gemini extracted details: {details_dict}")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from Gemini: {e}\nRaw response: {cleaned_text}")
            details_dict = {"error": "Failed to parse OCR details", "raw_ocr": cleaned_text}
            # Continue to face extraction if possible
        
        # --- Face Extraction & Embedding from ID Card ---
        print(f"Detecting faces in ID card '{image_path}' using {DETECTOR_BACKEND_ID}...")
        extracted_faces_info = DeepFace.extract_faces(
            img_path=image_path,
            detector_backend=DETECTOR_BACKEND_ID,
            enforce_detection=True,
            align=True
        )

        if not extracted_faces_info or not isinstance(extracted_faces_info, list):
            print("No face detected on ID card or unexpected format.")
            details_dict["id_face_detection_error"] = "No face detected on ID card"
            return details_dict, None

        first_face_np_bgr = extracted_faces_info[0]['face']
        if first_face_np_bgr.dtype == np.float32 or first_face_np_bgr.dtype == np.float64:
            first_face_np_bgr = (first_face_np_bgr * 255).astype(np.uint8)
        print(f"ID Card Face detected. Confidence: {extracted_faces_info[0]['confidence']:.2f}")

        preprocessed_id_face_np = preprocess_face_image_for_id(first_face_np_bgr)
        
        temp_preprocessed_face_path_id = "temp_preprocessed_id_face.jpg"
        cv2.imwrite(temp_preprocessed_face_path_id, preprocessed_id_face_np)
        print(f"Saved preprocessed ID face to '{temp_preprocessed_face_path_id}'")

        embedding_objs_id = DeepFace.represent(
            img_path=temp_preprocessed_face_path_id,
            model_name=EXTRACTION_MODEL_NAME,
            enforce_detection=True, # Should find face
            detector_backend=DETECTOR_BACKEND_ID # Keep consistent
        )
        if embedding_objs_id and len(embedding_objs_id) > 0:
            id_face_embedding_list = embedding_objs_id[0]['embedding']
            print(f"Generated {len(id_face_embedding_list)}-d embedding from ID card face.")
        else:
            print("Failed to generate embedding from ID card face.")
            details_dict["id_face_embedding_error"] = "Failed to generate embedding from ID face"

    except ValueError as ve:
        if "Face could not be detected" in str(ve):
            print(f"ID Face detection failed: {ve}")
            details_dict["id_face_detection_error"] = f"ID Face detection failed: {ve}"
        else:
            print(f"ValueError during ID card processing: {ve}")
            details_dict["id_processing_error"] = f"ValueError: {ve}"
            traceback.print_exc()
    except Exception as e_id:
        print(f"Error processing ID card: {e_id}")
        details_dict["id_processing_error"] = f"General error: {e_id}"
        traceback.print_exc()
    finally:
        if temp_preprocessed_face_path_id and os.path.exists(temp_preprocessed_face_path_id):
            try:
                os.remove(temp_preprocessed_face_path_id)
            except Exception as e_clean:
                print(f"Warning: Could not remove temp ID face file: {e_clean}")
    
    return details_dict, id_face_embedding_list