# ml_logic/id_card_processor.py
from google.generativeai import GenerativeModel
from PIL import Image as PIL_Image
import io
import json
import os
import re
import numpy as np
from deepface import DeepFace
import cv2
import traceback

EXTRACTION_MODEL_NAME  = 'Facenet'
DETECTOR_BACKEND_ID    = 'retinaface'


def preprocess_face_image_for_id(face_image_np):
    """Preprocessing specific for ID card faces — CLAHE contrast enhancement."""
    print("Preprocessing ID card face...")
    processed_face = face_image_np.copy()
    if len(processed_face.shape) == 2 or processed_face.shape[2] == 1:
        processed_face = cv2.cvtColor(processed_face, cv2.COLOR_GRAY2BGR)
    elif processed_face.shape[2] == 4:
        processed_face = cv2.cvtColor(processed_face, cv2.COLOR_BGRA2BGR)

    lab  = cv2.cvtColor(processed_face, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    cl   = clahe.apply(l)
    limg = cv2.merge((cl, a, b))
    processed_face = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    print("  Applied CLAHE contrast enhancement")
    return processed_face


# ── Step 1 ────────────────────────────────────────────────────────────────────
def extract_text_from_id(image_path: str, gemini_model) -> dict:
    """
    Sends the ID card image to Gemini and returns a dict of extracted text fields.
    Raises on hard failure so the caller can emit the correct SSE event.
    """
    print(f"\n--- [OCR] Sending ID card to Gemini: {image_path} ---")

    pil_img = PIL_Image.open(image_path)
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG")
    buf.seek(0)
    image_part = {"mime_type": "image/jpeg", "data": buf.read()}

    prompt = """
    You are an expert OCR and document understanding assistant specialising in Indian ID cards.
    Identify the card type and extract details into a JSON object with ONLY these exact keys:

    {
      "card_type":         "One of: 'Voter ID', 'Aadhaar card', 'PAN card', 'Driving License'",
      "name":              "Full name as printed.",
      "dob":               "Date of birth in DD-MM-YYYY format.",
      "aadhaar_no":        "12-digit primary Aadhaar number ONLY (not the 16-digit VID).",
      "pan_no":            "PAN number, if present.",
      "license_no":        "Driving licence number, if present.",
      "expiration_date":   "Validity/expiry date, if present.",
      "father_mother_name":"Father's or Mother's name, if present.",
      "voter_id_number":   "EPIC/Voter ID number, ONLY for Voter ID cards."
    }

    Rules:
    - Omit keys not applicable to this card type (do NOT use 'N/A').
    - Extract the 12-digit Aadhaar number without spaces (e.g. '751490185308').
    - Never confuse the 16-digit VID on Aadhaar cards with a Voter ID number.
    - Return ONLY the JSON object — no markdown, no extra text.
    """

    response     = gemini_model.generate_content([prompt, image_part])
    cleaned_text = re.sub(r"```json|```", "", response.text).strip()

    try:
        details = json.loads(cleaned_text)
        print(f"  Gemini extracted: {details}")
        return details
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}\n  Raw: {cleaned_text}")
        return {"error": "Failed to parse OCR details", "raw_ocr": cleaned_text}


# ── Step 2 ────────────────────────────────────────────────────────────────────
def extract_face_from_id(image_path: str):
    """
    Detects the face on an ID card, preprocesses it, and returns a Facenet embedding.

    Returns:
        (embedding_list, info_str)  — embedding is None on failure, info_str explains outcome.
    """
    print(f"\n--- [Face] Detecting face on ID card: {image_path} ---")
    temp_path = None

    try:
        # ── 1. Detect & align face ────────────────────────────────────────────
        print(f"  Running {DETECTOR_BACKEND_ID} face detector...")
        extracted_faces = DeepFace.extract_faces(
            img_path=image_path,
            detector_backend=DETECTOR_BACKEND_ID,
            enforce_detection=True,
            align=True,
        )

        if not extracted_faces:
            return None, "No face detected on the ID card. Ensure the photo is clearly visible."

        face_np = extracted_faces[0]['face']
        confidence = extracted_faces[0]['confidence']
        print(f"  Face detected — confidence: {confidence:.2f}")

        if face_np.dtype in (np.float32, np.float64):
            face_np = (face_np * 255).astype(np.uint8)

        # ── 2. Preprocess (CLAHE) ─────────────────────────────────────────────
        print("  Applying CLAHE contrast enhancement...")
        preprocessed = preprocess_face_image_for_id(face_np)

        temp_path = "temp_preprocessed_id_face.jpg"
        cv2.imwrite(temp_path, preprocessed)

        # ── 3. Generate Facenet embedding ─────────────────────────────────────
        print(f"  Generating {EXTRACTION_MODEL_NAME} embedding...")
        embedding_objs = DeepFace.represent(
            img_path=temp_path,
            model_name=EXTRACTION_MODEL_NAME,
            enforce_detection=True,
            detector_backend=DETECTOR_BACKEND_ID,
        )

        if embedding_objs:
            embedding = embedding_objs[0]['embedding']
            print(f"  Generated {len(embedding)}-d embedding.")
            return embedding, f"Face detected (confidence {confidence:.2f}). {len(embedding)}-d {EXTRACTION_MODEL_NAME} embedding generated."
        else:
            return None, "Face detected but embedding generation failed."

    except ValueError as ve:
        msg = str(ve)
        if "Face could not be detected" in msg:
            return None, f"Face detection failed: {msg}"
        return None, f"ValueError during face extraction: {msg}"

    except Exception as e:
        traceback.print_exc()
        return None, f"Error during face extraction: {str(e)}"

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e_clean:
                print(f"  Warning: could not remove temp face file: {e_clean}")


# ── Legacy wrapper (keeps existing /process_and_verify route working) ─────────
def extract_text_and_face_from_id(image_path: str, gemini_model):
    """
    Original combined function — kept so the existing non-streaming route
    (/process_and_verify) continues to work without any changes.
    """
    details_dict         = extract_text_from_id(image_path, gemini_model)
    embedding, _info_str = extract_face_from_id(image_path)
    return details_dict, embedding
