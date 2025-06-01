# ml_logic/db_storer.py
import psycopg2
from psycopg2 import sql
import traceback
import os
import re
import json # To store embedding as JSON string
import logging
from urllib.parse import urlparse # For parsing DATABASE_URL

def get_db_connection_params():
    """
    Retrieves database connection parameters.
    Prioritizes DATABASE_URL if available (common in PaaS like Railway).
    Falls back to individual DB_HOST, DB_PORT, etc., for local/alternative setups.
    """
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        print(f"DATABASE_URL found. Parsing: {database_url[:30]}...") # Log a portion for debugging
        try:
            result = urlparse(database_url)
            # Ensure "postgresql" scheme if "postgres" is used by Railway
            scheme = result.scheme
            if scheme == "postgres":
                scheme = "postgresql" # psycopg2 might prefer this, though often handles both

            params = {
                'dsn': database_url, # Keep the original DSN for direct use if preferred
                'dbname': result.path[1:], # Remove leading '/'
                'user': result.username,
                'password': result.password,
                'host': result.hostname,
                'port': result.port,
                'scheme': scheme # Store the scheme for reference
            }
            # Remove None values if any component is missing (shouldn't happen with a valid URL)
            params = {k: v for k, v in params.items() if v is not None}
            print(f"Parsed DB params from DATABASE_URL: { {k:v for k,v in params.items() if k != 'password'} }") # Don't log password
            return params
        except Exception as e:
            print(f"Error parsing DATABASE_URL '{database_url}': {e}. Falling back to individual env vars.")
            # Fallback to individual vars if DATABASE_URL parsing fails
            return {
                "host": os.getenv("DB_HOST", "localhost"),
                "port": os.getenv("DB_PORT", "5432"),
                "dbname": os.getenv("DB_NAME", "votechain_db"),
                "user": os.getenv("DB_USER", "postgres"),
                "password": os.getenv("DB_PASSWORD", "root")
            }
    else:
        print("DATABASE_URL not found. Using individual DB_HOST, DB_PORT, etc., or defaults.")
        return {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "5432")), # Ensure port is int
            "dbname": os.getenv("DB_NAME", "votechain_db"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "root")
        }

# def create_user_table_if_not_exists():
#     """Creates the user_id_details table if it doesn't already exist."""
#     conn = None
#     cur = None
#     params_dict = get_db_connection_params()
    
#     # Prepare connection arguments
#     # If DATABASE_URL was parsed successfully, params_dict contains 'dsn'
#     # psycopg2.connect() can take a DSN string directly or keyword arguments.
#     # We'll use the DSN if available, otherwise unpack the dict for keyword args.
    
#     connect_args = {}
#     if 'dsn' in params_dict:
#         # If using the DSN directly:
#         # Note: Railway often provides a "postgres://" scheme, which psycopg2 usually handles fine.
#         # If you encounter issues, you might need to replace "postgres://" with "postgresql://".
#         # Example: dsn_to_use = params_dict['dsn'].replace("postgres://", "postgresql://", 1)
#         dsn_to_use = params_dict['dsn']
#         if dsn_to_use.startswith("postgres://"): # Ensure psycopg2 compatibility
#              dsn_to_use = dsn_to_use.replace("postgres://", "postgresql://", 1)
#         connect_args['dsn'] = dsn_to_use
#         print(f"Connecting using DSN: {dsn_to_use[:30]}...")
#     else:
#         # Fallback to individual parameters
#         connect_args = {k: v for k, v in params_dict.items() if k not in ['dsn', 'scheme']} # Exclude helper keys
#         print(f"Connecting using individual params: host={connect_args.get('host')}")


#     try:
#         conn = psycopg2.connect(**connect_args)
#         cur = conn.cursor()
#         create_table_query = """
#         CREATE TABLE IF NOT EXISTS user_id_details (
#             id SERIAL PRIMARY KEY,
#             card_type VARCHAR(50),
#             name VARCHAR(255),
#             dob VARCHAR(20),
#             aadhaar_no VARCHAR(50) UNIQUE,
#             pan_no VARCHAR(50) UNIQUE,
#             license_no VARCHAR(50) UNIQUE,
#             voter_id_number VARCHAR(50) UNIQUE,
#             expiration_date VARCHAR(20),
#             father_mother_name VARCHAR(255),
#             face_embedding TEXT,
#             registration_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
#         );
#         """
#         cur.execute(create_table_query)
#         conn.commit()
#         print("Table 'user_id_details' checked/created successfully.")
#     except psycopg2.Error as db_err:
#         print(f"Database error during table creation: {db_err}")
#         traceback.print_exc()
#     except Exception as e:
#         print(f"An unexpected error occurred during table creation: {e}")
#         traceback.print_exc()
#     finally:
#         if cur: cur.close()
#         if conn: conn.close()




def create_user_table_if_not_exists():
    conn = None
    cur = None
    params_dict = get_db_connection_params() # This already prints "Connecting using DSN..."
    
    connect_args = {}
    if 'dsn' in params_dict:
        dsn_to_use = params_dict['dsn']
        if dsn_to_use.startswith("postgres://"):
             dsn_to_use = dsn_to_use.replace("postgres://", "postgresql://", 1)
        connect_args['dsn'] = dsn_to_use
        # logging.info(f"Connecting using DSN (from db_storer): {dsn_to_use[:30]}...") # Already logged in app.py's call to get_db_connection_params
    else:
        connect_args = {k: v for k, v in params_dict.items() if k not in ['dsn', 'scheme']}
        # logging.info(f"Connecting using individual params (from db_storer): host={connect_args.get('host')}")

    logging.info("DB_STORER: Attempting psycopg2.connect()...") # NEW LOG
    try:
        conn = psycopg2.connect(**connect_args)
        logging.info("DB_STORER: psycopg2.connect() successful.") # NEW LOG
        cur = conn.cursor()
        logging.info("DB_STORER: Cursor created.") # NEW LOG
        
        create_table_query = """
        CREATE TABLE IF NOT EXISTS user_id_details (
            id SERIAL PRIMARY KEY,
            card_type VARCHAR(50),
            name VARCHAR(255),
            dob VARCHAR(20),
            aadhaar_no VARCHAR(50) UNIQUE,
            pan_no VARCHAR(50) UNIQUE,
            license_no VARCHAR(50) UNIQUE,
            voter_id_number VARCHAR(50) UNIQUE,
            expiration_date VARCHAR(20),
            father_mother_name VARCHAR(255),
            face_embedding TEXT,
            registration_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        """
        logging.info("DB_STORER: Executing CREATE TABLE query...") # NEW LOG
        cur.execute(create_table_query)
        logging.info("DB_STORER: CREATE TABLE query executed.") # NEW LOG
        conn.commit()
        logging.info("DB_STORER: Transaction committed.") # NEW LOG
        print("Table 'user_id_details' checked/created successfully.") # Your existing print
        logging.info("Table 'user_id_details' checked/created successfully. (via logging)") # Match with logging

    except psycopg2.Error as db_err:
        logging.error(f"DB_STORER: Database error during table creation: {db_err}", exc_info=True) # exc_info=True for traceback
        # traceback.print_exc() # Already covered by exc_info=True
    except Exception as e:
        logging.error(f"DB_STORER: An unexpected error occurred during table creation: {e}", exc_info=True)
        # traceback.print_exc()
    finally:
        logging.info("DB_STORER: Entering finally block for DB connection cleanup.") # NEW LOG
        if cur:
            cur.close()
            logging.info("DB_STORER: Cursor closed.") # NEW LOG
        if conn:
            conn.close()
            logging.info("DB_STORER: Connection closed.") # NEW LOG
        logging.info("DB_STORER: Exiting finally block.") # NEW LOG
        
        
        
        
def store_verified_user_details(extracted_details, id_face_embedding_list):
    """
    Stores the extracted text details and the ID face embedding into the database.
    Uses UPSERT logic based on the card type's unique identifier.
    """
    if not extracted_details:
        return False, "No valid details to store."
    if id_face_embedding_list is None:
        return False, "Cannot store: ID face embedding is missing."

    conn = None
    cur = None
    params_dict = get_db_connection_params()
    success = False
    message = "Storage failed."

    connect_args = {}
    if 'dsn' in params_dict:
        dsn_to_use = params_dict['dsn']
        if dsn_to_use.startswith("postgres://"): # Ensure psycopg2 compatibility
             dsn_to_use = dsn_to_use.replace("postgres://", "postgresql://", 1)
        connect_args['dsn'] = dsn_to_use
        print(f"Connecting (store) using DSN: {dsn_to_use[:30]}...")
    else:
        connect_args = {k: v for k, v in params_dict.items() if k not in ['dsn', 'scheme']}
        print(f"Connecting (store) using individual params: host={connect_args.get('host')}")


    try:
        conn = psycopg2.connect(**connect_args)
        cur = conn.cursor()

        card_type = extracted_details.get("card_type")
        name = extracted_details.get("name")
        dob = extracted_details.get("dob")
        
        aadhaar_no = extracted_details.get("aadhaar_no")
        if aadhaar_no: aadhaar_no = re.sub(r'\s+', '', str(aadhaar_no))

        pan_no = extracted_details.get("pan_no")
        if pan_no: pan_no = re.sub(r'\s+', '', str(pan_no))

        license_no = extracted_details.get("license_no")
        if license_no: license_no = re.sub(r'\s+', '', str(license_no)).upper()

        voter_id_number = extracted_details.get("voter_id_number")
        if voter_id_number: voter_id_number = re.sub(r'\s+', '', str(voter_id_number)).upper()
        
        expiration_date = extracted_details.get("expiration_date")
        father_mother_name = extracted_details.get("father_mother_name")
        
        face_embedding_json = json.dumps(id_face_embedding_list)

        conflict_target_column_name = None
        if card_type == 'Aadhaar card' and aadhaar_no:
            conflict_target_column_name = 'aadhaar_no'
        elif card_type == 'Voter ID' and voter_id_number:
            conflict_target_column_name = 'voter_id_number'
        elif card_type == 'PAN card' and pan_no:
            conflict_target_column_name = 'pan_no'
        elif card_type == 'Driving License' and license_no:
            conflict_target_column_name = 'license_no'
        
        if conflict_target_column_name is None:
            # For a critical system like voting, you might want to prevent registration
            # if a known unique ID type (Aadhaar, Voter ID for example) is not provided,
            # or if the provided card_type doesn't have a corresponding unique ID.
            # This depends on your system's rules.
            if name and dob: # A very weak fallback, consider disallowing.
                print(f"Warning: No clear unique ID field for '{card_type}'. Attempting insert without ON CONFLICT. This is not recommended for production voting systems if uniqueness on name/dob is not guaranteed.")
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
                success = False
                message = f"Cannot store: No unique identifier found for card type '{card_type}' and insufficient fallback data (name/dob)."
                print(message)
                if conn: conn.rollback()
                return success, message # Exit early
        else:
            conflict_target = sql.Identifier(conflict_target_column_name)
            # Corrected UPSERT to be more robust when other ID fields are NULL
            upsert_query = sql.SQL("""
            INSERT INTO user_id_details
            (card_type, name, dob, aadhaar_no, pan_no, license_no, voter_id_number, expiration_date, father_mother_name, face_embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ({conflict_col})
            DO UPDATE SET
                card_type = EXCLUDED.card_type,
                name = EXCLUDED.name,
                dob = EXCLUDED.dob,
                aadhaar_no = COALESCE(EXCLUDED.aadhaar_no, user_id_details.aadhaar_no),
                pan_no = COALESCE(EXCLUDED.pan_no, user_id_details.pan_no),
                license_no = COALESCE(EXCLUDED.license_no, user_id_details.license_no),
                voter_id_number = COALESCE(EXCLUDED.voter_id_number, user_id_details.voter_id_number),
                expiration_date = EXCLUDED.expiration_date,
                father_mother_name = EXCLUDED.father_mother_name,
                face_embedding = EXCLUDED.face_embedding,
                registration_timestamp = CURRENT_TIMESTAMP
            WHERE user_id_details.{conflict_col} = EXCLUDED.{conflict_col} -- ensure we're updating the correct row
            RETURNING id;
            """).format(conflict_col=conflict_target)

            cur.execute(upsert_query, (
                card_type, name, dob, aadhaar_no, pan_no, license_no, voter_id_number,
                expiration_date, father_mother_name, face_embedding_json
            ))
        
        inserted_id_row = cur.fetchone()
        if inserted_id_row:
            conn.commit()
            success = True
            message = f"User details for '{name}' (DB ID: {inserted_id_row[0]}) stored/updated successfully."
            print(message)
        else:
            # This case should ideally not be reached if the query is correct and there's data to insert/update.
            # It could happen if the ON CONFLICT condition is met but the WHERE clause in DO UPDATE is not.
            # Or if attempting a plain insert that somehow fails silently (very unlikely with RETURNING id).
            conn.rollback()
            message = "Storage failed: No ID returned or update condition not met after conflict."
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

# Add other database interaction functions as needed, e.g., to retrieve embeddings
def get_user_by_id_number(id_value, id_type):
    """
    Retrieves user details and face embedding by a specific ID number and type.
    Args:
        id_value (str): The value of the ID number (e.g., Aadhaar number, Voter ID).
        id_type (str): The type of ID ('aadhaar_no', 'voter_id_number', 'pan_no', 'license_no').
    Returns:
        dict: User details and embedding, or None if not found.
    """
    if id_type not in ['aadhaar_no', 'voter_id_number', 'pan_no', 'license_no']:
        print(f"Error: Invalid id_type '{id_type}' for retrieval.")
        return None

    conn = None
    cur = None
    params_dict = get_db_connection_params()
    
    connect_args = {}
    if 'dsn' in params_dict:
        dsn_to_use = params_dict['dsn']
        if dsn_to_use.startswith("postgres://"): # Ensure psycopg2 compatibility
             dsn_to_use = dsn_to_use.replace("postgres://", "postgresql://", 1)
        connect_args['dsn'] = dsn_to_use
    else:
        connect_args = {k: v for k, v in params_dict.items() if k not in ['dsn', 'scheme']}

    user_data = None
    try:
        conn = psycopg2.connect(**connect_args)
        cur = conn.cursor()

        # Use psycopg2.sql for safe dynamic column names
        query = sql.SQL("SELECT name, dob, face_embedding, card_type, aadhaar_no, pan_no, license_no, voter_id_number FROM user_id_details WHERE {} = %s;").format(
            sql.Identifier(id_type)
        )
        
        # Clean the id_value similar to how it's stored
        cleaned_id_value = re.sub(r'\s+', '', str(id_value))
        if id_type in ['voter_id_number', 'license_no', 'pan_no']: # PAN is case-insensitive but often stored upper
            cleaned_id_value = cleaned_id_value.upper()

        cur.execute(query, (cleaned_id_value,))
        row = cur.fetchone()

        if row:
            name, dob, face_embedding_json, card_type_db, aadhaar_db, pan_db, license_db, voter_db = row
            try:
                face_embedding_list = json.loads(face_embedding_json) if face_embedding_json else None
            except json.JSONDecodeError:
                print(f"Error decoding face embedding JSON for ID {cleaned_id_value}")
                face_embedding_list = None
            
            user_data = {
                "name": name,
                "dob": dob,
                "face_embedding": face_embedding_list,
                "card_type": card_type_db,
                # Include all potential IDs for completeness if needed by calling code
                "aadhaar_no": aadhaar_db,
                "pan_no": pan_db,
                "license_no": license_db,
                "voter_id_number": voter_db,
                f"{id_type}": cleaned_id_value # The ID used for lookup
            }
            print(f"User found by {id_type} = {cleaned_id_value}")
        else:
            print(f"No user found with {id_type} = {cleaned_id_value}")

    except psycopg2.Error as db_err:
        print(f"Database error during user retrieval by {id_type}: {db_err}")
        traceback.print_exc()
    except Exception as e:
        print(f"An unexpected error occurred while retrieving user by {id_type}: {e}")
        traceback.print_exc()
    finally:
        if cur: cur.close()
        if conn: conn.close()
    
    return user_data