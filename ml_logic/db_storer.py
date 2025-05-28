# ml_logic/db_storer.py
import psycopg2
from psycopg2 import sql
import traceback
import os
import re
import json # To store embedding as JSON string

def get_db_connection_params():
    """Retrieves database connection parameters from environment variables."""
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "dbname": os.getenv("DB_NAME", "votechain_db"), # Ensure your .env has DB_NAME
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "root")
    }

def create_user_table_if_not_exists():
    """Creates the user_id_details table if it doesn't already exist."""
    conn = None
    cur = None
    params = get_db_connection_params()
    try:
        conn = psycopg2.connect(**params)
        cur = conn.cursor()
        create_table_query = """
        CREATE TABLE IF NOT EXISTS user_id_details (
            id SERIAL PRIMARY KEY,
            card_type VARCHAR(50),
            name VARCHAR(255),
            dob VARCHAR(20),
            aadhaar_no VARCHAR(50) UNIQUE,      -- For Aadhaar
            pan_no VARCHAR(50) UNIQUE,          -- For PAN
            license_no VARCHAR(50) UNIQUE,      -- For Driving License
            voter_id_number VARCHAR(50) UNIQUE, -- For Voter ID
            expiration_date VARCHAR(20),        -- For Driving License
            father_mother_name VARCHAR(255),
            face_embedding TEXT,                -- Storing as JSON string
            registration_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        """
        cur.execute(create_table_query)
        conn.commit()
        print("Table 'user_id_details' checked/created successfully.")
    except psycopg2.Error as db_err:
        print(f"Database error during table creation: {db_err}")
        traceback.print_exc()
    except Exception as e:
        print(f"An unexpected error occurred during table creation: {e}")
        traceback.print_exc()
    finally:
        if cur: cur.close()
        if conn: conn.close()

def store_verified_user_details(extracted_details, id_face_embedding_list):
    """
    Stores the extracted text details and the ID face embedding into the database.
    Uses UPSERT logic based on the card type's unique identifier.
    Args:
        extracted_details (dict): Dictionary of text details from OCR.
        id_face_embedding_list (list): The face embedding from the ID card.
    Returns:
        bool: True if storage was successful, False otherwise.
        str: Message indicating success or failure.
    """
    if not extracted_details:
        return False, "No valid details to store."
    if id_face_embedding_list is None:
        # Decide if you want to store details even without an embedding,
        # or if embedding is mandatory for registration.
        # For a voting system, embedding is likely mandatory.
        return False, "Cannot store: ID face embedding is missing."

    conn = None
    cur = None
    params = get_db_connection_params()
    success = False
    message = "Storage failed."

    try:
        conn = psycopg2.connect(**params)
        cur = conn.cursor()

        # Prepare data from extracted_details
        card_type = extracted_details.get("card_type")
        name = extracted_details.get("name")
        dob = extracted_details.get("dob")
        
        # Standardize and clean ID numbers
        aadhaar_no = extracted_details.get("aadhaar_no")
        if aadhaar_no: aadhaar_no = re.sub(r'\s+', '', str(aadhaar_no))

        pan_no = extracted_details.get("pan_no")
        if pan_no: pan_no = re.sub(r'\s+', '', str(pan_no))

        license_no = extracted_details.get("license_no")
        # Add more specific cleaning for license_no if needed
        if license_no: license_no = re.sub(r'\s+', '', str(license_no)).upper()


        voter_id_number = extracted_details.get("voter_id_number")
        if voter_id_number: voter_id_number = re.sub(r'\s+', '', str(voter_id_number)).upper()
        
        expiration_date = extracted_details.get("expiration_date")
        father_mother_name = extracted_details.get("father_mother_name")
        
        # Convert embedding list to JSON string for storage
        face_embedding_json = json.dumps(id_face_embedding_list)

        # Determine conflict target for UPSERT
        conflict_target_column_name = None
        if card_type == 'Aadhaar card' and aadhaar_no:
            conflict_target_column_name = 'aadhaar_no'
        elif card_type == 'Voter ID' and voter_id_number:
            conflict_target_column_name = 'voter_id_number'
        elif card_type == 'PAN card' and pan_no:
            conflict_target_column_name = 'pan_no'
        elif card_type == 'Driving License' and license_no:
            conflict_target_column_name = 'license_no'
        
        if conflict_target_column_name is None and name: # Fallback to name if no clear ID, less ideal
            print(f"Warning: No clear unique ID field for {card_type}. This might lead to issues if name is not unique.")
            # For a voting system, a unique ID (Aadhaar, Voter ID) should be enforced.
            # If allowing other cards, a robust unique key strategy is needed.
            # For now, we'll proceed with a plain insert if no conflict target.
            insert_query_plain = sql.SQL("""
             INSERT INTO user_id_details
             (card_type, name, dob, aadhaar_no, pan_no, license_no, voter_id_number, expiration_date, father_mother_name, face_embedding)
             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
             """)
            cur.execute(insert_query_plain, (
                 card_type, name, dob, aadhaar_no, pan_no, license_no, voter_id_number,
                 expiration_date, father_mother_name, face_embedding_json
             ))
        else:
            # Build UPSERT query dynamically for the conflict target
            # Ensures that other unique ID fields are not inadvertently overwritten with NULL
            # if an update occurs on a different ID type.
            conflict_target = sql.Identifier(conflict_target_column_name)
            upsert_query = sql.SQL("""
            INSERT INTO user_id_details
            (card_type, name, dob, aadhaar_no, pan_no, license_no, voter_id_number, expiration_date, father_mother_name, face_embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ({conflict_col})
            DO UPDATE SET
                card_type = EXCLUDED.card_type,
                name = EXCLUDED.name,
                dob = EXCLUDED.dob,
                aadhaar_no = CASE WHEN EXCLUDED.card_type = 'Aadhaar card' THEN EXCLUDED.aadhaar_no ELSE user_id_details.aadhaar_no END,
                pan_no = CASE WHEN EXCLUDED.card_type = 'PAN card' THEN EXCLUDED.pan_no ELSE user_id_details.pan_no END,
                license_no = CASE WHEN EXCLUDED.card_type = 'Driving License' THEN EXCLUDED.license_no ELSE user_id_details.license_no END,
                voter_id_number = CASE WHEN EXCLUDED.card_type = 'Voter ID' THEN EXCLUDED.voter_id_number ELSE user_id_details.voter_id_number END,
                expiration_date = EXCLUDED.expiration_date,
                father_mother_name = EXCLUDED.father_mother_name,
                face_embedding = EXCLUDED.face_embedding,
                registration_timestamp = CURRENT_TIMESTAMP
            RETURNING id;
            """).format(conflict_col=conflict_target)

            cur.execute(upsert_query, (
                card_type, name, dob, aadhaar_no, pan_no, license_no, voter_id_number,
                expiration_date, father_mother_name, face_embedding_json
            ))
        
        inserted_id = cur.fetchone()
        if inserted_id:
            conn.commit()
            success = True
            message = f"User details for '{name}' (ID: {inserted_id[0]}) stored/updated successfully."
            print(message)
        else:
            conn.rollback() # Should not happen if query is correct and RETURNING id is used
            message = "Storage failed: No ID returned after insert/update."
            print(message)

    except psycopg2.Error as db_err:
        print(f"Database error during user detail storage: {db_err}")
        message = f"Database error: {db_err}"
        traceback.print_exc()
        if conn: conn.rollback()
    except Exception as e:
        print(f"An unexpected error occurred while storing user details: {e}")
        message = f"Unexpected error: {e}"
        traceback.print_exc()
        if conn: conn.rollback()
    finally:
        if cur: cur.close()
        if conn: conn.close()
    
    return success, message