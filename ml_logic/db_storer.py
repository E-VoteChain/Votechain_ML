#---------------------------------------LOCAL----------------------------------------------

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




















#--------------------------------------Deploy on PaaS------------------------------------------------


# # ml_logic/db_storer.py
# import psycopg2
# from psycopg2 import sql # Keep this if you use it elsewhere, not strictly needed for this function
# import traceback
# import os
# import re # Keep if used elsewhere
# import json # To store embedding as JSON string
# from urllib.parse import urlparse
# import logging # Import the logging module

# # If logging is not configured in app.py and this module is run standalone,
# # this basicConfig will help. If app.py configures it, this won't reconfigure.
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__) # Use a module-specific logger

# def get_db_connection_params():
#     """
#     Retrieves database connection parameters.
#     Prioritizes DATABASE_URL if available (common in PaaS like Railway).
#     Falls back to individual DB_HOST, DB_PORT, etc., for local/alternative setups.
#     """
#     database_url = os.getenv("DATABASE_URL")

#     if database_url:
#         logger.info(f"DATABASE_URL found. Parsing: {database_url[:30]}...")
#         try:
#             result = urlparse(database_url)
#             scheme = result.scheme
#             if scheme == "postgres": # psycopg2 often expects postgresql
#                 scheme = "postgresql"

#             # Prepare a DSN that psycopg2 will reliably use
#             # Sometimes direct DSN from Railway has "postgres://" which might need adjustment
#             dsn_for_connect = f"{scheme}://{result.username}:{result.password}@{result.hostname}:{result.port}{result.path}"

#             params = {
#                 'dsn_original': database_url, # For reference
#                 'dsn_for_connect': dsn_for_connect, # The one we'll use
#                 'dbname': result.path[1:],
#                 'user': result.username,
#                 'password': result.password, # Be careful logging this
#                 'host': result.hostname,
#                 'port': result.port,
#                 'scheme': scheme
#             }
#             # Don't log the full params dict if it contains password in clear text
#             log_params = {k:v for k,v in params.items() if k not in ['password', 'dsn_original', 'dsn_for_connect'] or k == 'dsn_for_connect' and isinstance(v, str) and v.startswith(scheme)}
#             if 'dsn_for_connect' in log_params: log_params['dsn_for_connect'] = log_params['dsn_for_connect'][:30] + "..."

#             logger.info(f"Parsed DB params from DATABASE_URL: {log_params}")
#             return params
#         except Exception as e:
#             logger.error(f"Error parsing DATABASE_URL '{database_url}': {e}. Falling back to individual env vars.", exc_info=True)
#             return { # Fallback dictionary structure
#                 "host": os.getenv("DB_HOST", "localhost"),
#                 "port": int(os.getenv("DB_PORT", "5432")),
#                 "dbname": os.getenv("DB_NAME", "votechain_db"),
#                 "user": os.getenv("DB_USER", "postgres"),
#                 "password": os.getenv("DB_PASSWORD", "root"),
#                 "using_fallback": True
#             }
#     else:
#         logger.info("DATABASE_URL not found. Using individual DB_HOST, DB_PORT, etc., or defaults.")
#         return {
#             "host": os.getenv("DB_HOST", "localhost"),
#             "port": int(os.getenv("DB_PORT", "5432")),
#             "dbname": os.getenv("DB_NAME", "votechain_db"),
#             "user": os.getenv("DB_USER", "postgres"),
#             "password": os.getenv("DB_PASSWORD", "root"),
#             "using_fallback": True
#         }

# def create_user_table_if_not_exists():
#     """Creates the user_id_details table if it doesn't already exist."""
#     conn = None
#     cur = None
#     logger.info("DB_STORER: Entered create_user_table_if_not_exists()")
#     params_dict = get_db_connection_params()
    
#     connect_args_or_dsn = None
#     db_connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "10")) # Default 10 seconds timeout

#     if 'dsn_for_connect' in params_dict:
#         connect_args_or_dsn = params_dict['dsn_for_connect']
#         # Append connect_timeout to DSN if using DSN string method
#         # DSN format for timeout: "postgresql://user:pass@host:port/db?connect_timeout=10"
#         # However, psycopg2.connect also takes it as a keyword argument, which is cleaner
#         logger.info(f"DB_STORER: Will connect using DSN: {str(connect_args_or_dsn)[:30]}... with timeout {db_connect_timeout}s")
#     elif 'using_fallback' in params_dict and params_dict['using_fallback']:
#         # Construct dict for keyword arguments from fallback
#         connect_args_or_dsn = {
#             k: v for k, v in params_dict.items()
#             if k in ['host', 'port', 'dbname', 'user', 'password']
#         }
#         connect_args_or_dsn['connect_timeout'] = db_connect_timeout # Add timeout here
#         logger.info(f"DB_STORER: Will connect using individual params: host={params_dict.get('host')} with timeout {db_connect_timeout}s")
#     else:
#         logger.error("DB_STORER: Could not determine connection parameters (neither DSN nor fallback).")
#         return # Cannot proceed

#     logger.info(f"DB_STORER: Attempting psycopg2.connect() with timeout {db_connect_timeout}s...")
#     try:
#         if isinstance(connect_args_or_dsn, str): # It's a DSN string
#             conn = psycopg2.connect(dsn=connect_args_or_dsn, connect_timeout=db_connect_timeout)
#         else: # It's a dictionary of parameters
#             conn = psycopg2.connect(**connect_args_or_dsn) # connect_timeout is already in the dict

#         logger.info("DB_STORER: psycopg2.connect() successful.")
#         cur = conn.cursor()
#         logger.info("DB_STORER: Cursor created.")
        
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
#         logger.info("DB_STORER: Executing CREATE TABLE IF NOT EXISTS query...")
#         cur.execute(create_table_query)
#         logger.info("DB_STORER: CREATE TABLE query executed.")
#         conn.commit()
#         logger.info("DB_STORER: Transaction committed.")
#         # Use logger instead of print for consistency in server logs
#         logger.info("Table 'user_id_details' checked/created successfully.")

#     except psycopg2.OperationalError as op_err:
#         if "timeout expired" in str(op_err).lower():
#             logger.error("DB_STORER: Connection timed out!", exc_info=True)
#         else:
#             logger.error(f"DB_STORER: Database operational error during table creation: {op_err}", exc_info=True)
#     except psycopg2.Error as db_err: # Catch other psycopg2 specific errors
#         logger.error(f"DB_STORER: Generic Psycopg2 database error during table creation: {db_err}", exc_info=True)
#     except Exception as e:
#         logger.error(f"DB_STORER: An unexpected error occurred during table creation: {e}", exc_info=True)
#     finally:
#         logger.info("DB_STORER: Entering finally block for DB connection cleanup.")
#         if cur:
#             try:
#                 cur.close()
#                 logger.info("DB_STORER: Cursor closed.")
#             except Exception as e_cur:
#                 logger.error(f"DB_STORER: Error closing cursor: {e_cur}", exc_info=True)
#         if conn:
#             try:
#                 conn.close()
#                 logger.info("DB_STORER: Connection closed.")
#             except Exception as e_conn:
#                 logger.error(f"DB_STORER: Error closing connection: {e_conn}", exc_info=True)
#         logger.info("DB_STORER: Exiting create_user_table_if_not_exists().")


# # --- store_verified_user_details and get_user_by_id_number functions ---
# # Apply similar logic for get_db_connection_params() and psycopg2.connect()
# # with detailed logging and timeout for these functions as well.
# # For brevity, I'll show the pattern for store_verified_user_details:

# def store_verified_user_details(extracted_details, id_face_embedding_list):
#     logger.info("DB_STORER: Entered store_verified_user_details()")
#     if not extracted_details:
#         logger.warning("DB_STORER: No valid details to store (store_verified_user_details).")
#         return False, "No valid details to store."
#     if id_face_embedding_list is None:
#         logger.warning("DB_STORER: Cannot store: ID face embedding is missing (store_verified_user_details).")
#         return False, "Cannot store: ID face embedding is missing."

#     conn = None
#     cur = None
#     params_dict = get_db_connection_params()
#     success = False
#     message = "Storage failed."
    
#     connect_args_or_dsn = None
#     db_connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))

#     if 'dsn_for_connect' in params_dict:
#         connect_args_or_dsn = params_dict['dsn_for_connect']
#         logger.info(f"DB_STORER (store): Will connect using DSN: {str(connect_args_or_dsn)[:30]}... with timeout {db_connect_timeout}s")
#     elif 'using_fallback' in params_dict and params_dict['using_fallback']:
#         connect_args_or_dsn = {
#             k: v for k, v in params_dict.items()
#             if k in ['host', 'port', 'dbname', 'user', 'password']
#         }
#         connect_args_or_dsn['connect_timeout'] = db_connect_timeout
#         logger.info(f"DB_STORER (store): Will connect using individual params: host={params_dict.get('host')} with timeout {db_connect_timeout}s")
#     else:
#         logger.error("DB_STORER (store): Could not determine connection parameters.")
#         return False, "Internal configuration error for database connection."

#     logger.info(f"DB_STORER (store): Attempting psycopg2.connect() with timeout {db_connect_timeout}s...")
#     try:
#         if isinstance(connect_args_or_dsn, str):
#             conn = psycopg2.connect(dsn=connect_args_or_dsn, connect_timeout=db_connect_timeout)
#         else:
#             conn = psycopg2.connect(**connect_args_or_dsn)
#         logger.info("DB_STORER (store): psycopg2.connect() successful.")
#         cur = conn.cursor()
#         logger.info("DB_STORER (store): Cursor created.")

#         # ... (rest of your existing store_verified_user_details logic with SQL and commit/rollback) ...
#         # Make sure to use logger.info/error/warning within this try block too.
#         # Example:
#         card_type = extracted_details.get("card_type")
#         name = extracted_details.get("name")
#         # ... (your data preparation)
#         face_embedding_json = json.dumps(id_face_embedding_list) # Ensure id_face_embedding_list is a list

#         conflict_target_column_name = None
#         # ... (your conflict target logic) ...
        
#         if conflict_target_column_name is None:
#             # ... (your plain insert logic)
#             logger.info(f"DB_STORER (store): Attempting plain insert for {name}...")
#             # cur.execute(...)
#         else:
#             # ... (your upsert logic)
#             logger.info(f"DB_STORER (store): Attempting UPSERT for {name} on {conflict_target_column_name}...")
#             # cur.execute(...)

#         inserted_id_row = cur.fetchone()
#         if inserted_id_row:
#             conn.commit()
#             success = True
#             message = f"User details for '{name}' (DB ID: {inserted_id_row[0]}) stored/updated successfully."
#             logger.info(f"DB_STORER (store): {message}")
#         else:
#             conn.rollback()
#             message = "Storage failed: No ID returned or update condition not met after conflict."
#             logger.warning(f"DB_STORER (store): {message}")
#             # ... (rest of your logic for success/failure)

#     except psycopg2.OperationalError as op_err:
#         if "timeout expired" in str(op_err).lower():
#             logger.error("DB_STORER (store): Connection timed out!", exc_info=True)
#             message = "Database connection timed out."
#         else:
#             logger.error(f"DB_STORER (store): Database operational error: {op_err}", exc_info=True)
#             message = f"Database operational error: {op_err}"
#         if conn: conn.rollback()
#     except psycopg2.Error as db_err:
#         logger.error(f"DB_STORER (store): Generic Psycopg2 database error: {db_err}", exc_info=True)
#         message = f"Database error: {db_err}"
#         if conn: conn.rollback()
#     except Exception as e:
#         logger.error(f"DB_STORER (store): An unexpected error occurred: {e}", exc_info=True)
#         message = f"Unexpected error: {e}"
#         if conn: conn.rollback()
#     finally:
#         logger.info("DB_STORER (store): Entering finally block.")
#         if cur:
#             try: cur.close()
#             except Exception as e_cur: logger.error(f"DB_STORER (store): Error closing cursor: {e_cur}", exc_info=True)
#         if conn:
#             try: conn.close()
#             except Exception as e_conn: logger.error(f"DB_STORER (store): Error closing connection: {e_conn}", exc_info=True)
#         logger.info("DB_STORER (store): Exiting store_verified_user_details().")
    
#     return success, message

# # --- Apply similar detailed logging and timeout to get_user_by_id_number ---
# def get_user_by_id_number(id_value, id_type):
#     logger.info(f"DB_STORER: Entered get_user_by_id_number() for type '{id_type}', value '{str(id_value)[:10]}...'")
#     # ... (rest of your logic, but use the same pattern for get_db_connection_params,
#     #      psycopg2.connect with timeout, and detailed logging within try/except/finally)
#     # For brevity, not fully re-writing it here, but the pattern is the same as above.
#     # ...
#     user_data = None # Placeholder
#     # ...
#     return user_data



























# # ml_logic/db_storer.py
# import psycopg2
# from psycopg2 import sql # Used for dynamic identifiers in get_user_by_id_number
# import traceback
# import os
# import re
# import json
# from urllib.parse import urlparse
# import logging

# # Configure logger for this module.
# # Ensure app.py calls logging.basicConfig() once at its top for root logger setup.
# logger = logging.getLogger(__name__)

# def get_db_connection_params():
#     """
#     Retrieves database connection parameters.
#     Prioritizes DATABASE_URL if available (common in PaaS like Railway).
#     Falls back to individual DB_HOST, DB_PORT, etc., for local/alternative setups.
#     """
#     database_url = os.getenv("DATABASE_URL")

#     if database_url:
#         # Using logger.info for deployment, print for very basic local debugging if needed
#         logger.info(f"DATABASE_URL found. Parsing: {database_url[:40]}...")
#         try:
#             result = urlparse(database_url)
#             scheme = result.scheme
#             if scheme == "postgres": # psycopg2 often expects postgresql
#                 scheme = "postgresql"
            
#             # Construct DSN that psycopg2 should handle, including scheme adjustment
#             dsn_for_connect = f"{scheme}://{result.username}:{result.password}@{result.hostname}:{result.port}{result.path}"

#             params = {
#                 'dsn_original': database_url, # For reference only
#                 'dsn_for_connect': dsn_for_connect, # This will be used for connection
#                 # Parsed components, useful for logging or alternative connection methods
#                 'dbname': result.path[1:], 
#                 'user': result.username,
#                 'password': result.password, # Be cautious logging this directly
#                 'host': result.hostname,
#                 'port': result.port,
#                 'scheme': scheme
#             }
#             # Log subset of params for security and brevity
#             log_params_subset = {k:v for k,v in params.items() if k not in ['password', 'dsn_original']}
#             if 'dsn_for_connect' in log_params_subset: 
#                 log_params_subset['dsn_for_connect'] = str(log_params_subset['dsn_for_connect'])[:40] + "..."
#             logger.info(f"Parsed DB params from DATABASE_URL: {log_params_subset}")
#             return params
#         except Exception as e:
#             logger.error(f"Error parsing DATABASE_URL '{database_url}': {e}. Falling back to individual env vars.", exc_info=True)
#             # Fallback dictionary structure
#             return {
#                 "host": os.getenv("DB_HOST", "localhost"),
#                 "port": int(os.getenv("DB_PORT", "5432")),
#                 "dbname": os.getenv("DB_NAME", "votechain_db"),
#                 "user": os.getenv("DB_USER", "postgres"),
#                 "password": os.getenv("DB_PASSWORD", "root"),
#                 "using_fallback": True # Flag to indicate fallback was used
#             }
#     else:
#         logger.info("DATABASE_URL not found. Using individual DB_HOST, DB_PORT, etc., or defaults.")
#         return {
#             "host": os.getenv("DB_HOST", "localhost"),
#             "port": int(os.getenv("DB_PORT", "5432")),
#             "dbname": os.getenv("DB_NAME", "votechain_db"),
#             "user": os.getenv("DB_USER", "postgres"),
#             "password": os.getenv("DB_PASSWORD", "root"),
#             "using_fallback": True
#         }

# def _connect_to_db(params_dict_from_get_db):
#     """
#     Helper function to establish a database connection using parameters
#     from get_db_connection_params(). Includes timeout.
#     Raises ConnectionError on failure to connect.
#     """
#     connect_params = {}
#     db_connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "15")) # Default 15 seconds

#     if 'dsn_for_connect' in params_dict_from_get_db: # Prioritize DSN if parsed from DATABASE_URL
#         connect_params['dsn'] = params_dict_from_get_db['dsn_for_connect']
#         logger.debug(f"DB_STORER: Will connect using DSN: {str(connect_params['dsn'])[:40]}...")
#     elif 'using_fallback' in params_dict_from_get_db and params_dict_from_get_db['using_fallback']:
#         # Use individual parameters from fallback
#         connect_params = {
#             k: v for k, v in params_dict_from_get_db.items()
#             if k in ['host', 'port', 'dbname', 'user', 'password']
#         }
#         logger.debug(f"DB_STORER: Will connect using individual params: host={params_dict_from_get_db.get('host')}")
#     else:
#         logger.error("DB_STORER: Critical error - Could not determine connection parameters.")
#         raise ConnectionError("Internal configuration error: Database connection parameters not found.")

#     logger.info(f"DB_STORER: Attempting psycopg2.connect() with timeout {db_connect_timeout}s...")
#     try:
#         # Pass connect_timeout as a keyword argument for both DSN and dict methods
#         conn = psycopg2.connect(connect_timeout=db_connect_timeout, **connect_params)
#         logger.info("DB_STORER: psycopg2.connect() successful.")
#         return conn
#     except psycopg2.OperationalError as op_err:
#         if "timeout expired" in str(op_err).lower():
#             logger.error("DB_STORER: Connection timed out!", exc_info=True)
#         else:
#             logger.error(f"DB_STORER: Database operational error during connect: {op_err}", exc_info=True)
#         raise ConnectionError(f"Failed to connect to database: {op_err}") from op_err
#     except Exception as e:
#         logger.error(f"DB_STORER: Unexpected error during psycopg2.connect(): {e}", exc_info=True)
#         raise ConnectionError(f"Unexpected error connecting to database: {e}") from e


# def create_user_table_if_not_exists():
#     """Creates the user_id_details table if it doesn't already exist."""
#     logger.info("DB_STORER: Entered create_user_table_if_not_exists()")
#     conn = None
#     cur = None
#     try:
#         params_dict = get_db_connection_params() # Get params (logs internally)
#         conn = _connect_to_db(params_dict) # Connect (logs internally)
        
#         cur = conn.cursor()
#         logger.info("DB_STORER: Cursor created for table creation.")
        
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
#         logger.info("DB_STORER: Executing CREATE TABLE IF NOT EXISTS query...")
#         cur.execute(create_table_query)
#         logger.info("DB_STORER: CREATE TABLE query executed.")
#         conn.commit()
#         logger.info("DB_STORER: Transaction committed for table creation.")
#         # Use logger, your app.py should configure basicConfig for print to be visible in Railway
#         logger.info("Table 'user_id_details' checked/created successfully.") 
#     except ConnectionError as conn_err: # Catch connection errors from _connect_to_db
#         logger.error(f"DB_STORER: Connection error prevented table creation: {conn_err}")
#         # No traceback here as _connect_to_db already logged it with exc_info=True
#     except psycopg2.Error as db_err:
#         logger.error(f"DB_STORER: Psycopg2 error during table creation: {db_err}", exc_info=True)
#     except Exception as e:
#         logger.error(f"DB_STORER: An unexpected error occurred during table creation: {e}", exc_info=True)
#     finally:
#         logger.debug("DB_STORER: Entering finally block for table creation.")
#         if cur:
#             try: cur.close()
#             except Exception as e_cur: logger.error(f"DB_STORER: Error closing cursor (table creation): {e_cur}", exc_info=True)
#         if conn:
#             try: conn.close()
#             except Exception as e_conn: logger.error(f"DB_STORER: Error closing connection (table creation): {e_conn}", exc_info=True)
#         logger.info("DB_STORER: Exiting create_user_table_if_not_exists().")


# def store_verified_user_details(extracted_details, id_face_embedding_list):
#     """Stores verified user details with UPSERT logic."""
#     logger.info(f"DB_STORER: Entered store_verified_user_details() for user: {extracted_details.get('name', 'N/A')}")
#     if not extracted_details:
#         logger.warning("DB_STORER (store): No valid details to store.")
#         return False, "No valid details to store."
#     if id_face_embedding_list is None:
#         logger.warning("DB_STORER (store): Cannot store: ID face embedding is missing.")
#         return False, "Cannot store: ID face embedding is missing."

#     conn = None
#     cur = None
#     success = False
#     message = "Storage failed due to an unexpected issue."

#     try:
#         params_dict = get_db_connection_params()
#         conn = _connect_to_db(params_dict)
#         cur = conn.cursor()
#         logger.info("DB_STORER (store): Cursor created.")

#         card_type = extracted_details.get("card_type")
#         name = extracted_details.get("name")
#         dob = extracted_details.get("dob")
        
#         aadhaar_no = extracted_details.get("aadhaar_no")
#         if aadhaar_no: aadhaar_no = re.sub(r'\s+', '', str(aadhaar_no))

#         pan_no = extracted_details.get("pan_no")
#         if pan_no: pan_no = re.sub(r'\s+', '', str(pan_no))

#         license_no = extracted_details.get("license_no")
#         if license_no: license_no = re.sub(r'\s+', '', str(license_no)).upper()

#         voter_id_number = extracted_details.get("voter_id_number")
#         if voter_id_number: voter_id_number = re.sub(r'\s+', '', str(voter_id_number)).upper()
        
#         expiration_date = extracted_details.get("expiration_date")
#         father_mother_name = extracted_details.get("father_mother_name")
        
#         # Ensure id_face_embedding_list is actually a list for json.dumps
#         # If it's a NumPy array, it needs .tolist()
#         if hasattr(id_face_embedding_list, 'tolist'): # Check if it's a NumPy array
#             face_embedding_json = json.dumps(id_face_embedding_list.tolist())
#         else:
#             face_embedding_json = json.dumps(list(id_face_embedding_list))


#         conflict_target_column_name = None
#         # This logic for determining conflict target is from your previous code
#         if card_type == 'Aadhaar card' and aadhaar_no:
#             conflict_target_column_name = 'aadhaar_no'
#         elif card_type == 'Voter ID' and voter_id_number:
#             conflict_target_column_name = 'voter_id_number'
#         elif card_type == 'PAN card' and pan_no:
#             conflict_target_column_name = 'pan_no'
#         elif card_type == 'Driving License' and license_no:
#             conflict_target_column_name = 'license_no'
        
#         if conflict_target_column_name is None:
#             # Fallback to plain insert if no conflict target identified
#             # This part matches your original logic's fallback
#             if name and dob: # Your original condition for fallback
#                 logger.warning(f"DB_STORER (store): No clear unique ID for '{card_type}'. Attempting plain insert for {name}. Not ideal for uniqueness.")
#                 insert_query_plain = sql.SQL("""
#                 INSERT INTO user_id_details
#                 (card_type, name, dob, aadhaar_no, pan_no, license_no, voter_id_number, expiration_date, father_mother_name, face_embedding)
#                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
#                 """)
#                 cur.execute(insert_query_plain, (
#                     card_type, name, dob, aadhaar_no, pan_no, license_no, voter_id_number,
#                     expiration_date, father_mother_name, face_embedding_json
#                 ))
#             else: # Fallback condition not met
#                 success = False
#                 message = f"Cannot store: No unique identifier found for card type '{card_type}' and insufficient fallback data (name/dob)."
#                 logger.error(f"DB_STORER (store): {message}")
#                 # No database transaction to rollback if we didn't even try to execute
#                 return success, message # Exit early
#         else:
#             # UPSERT logic, using COALESCE for robust updates
#             conflict_target = sql.Identifier(conflict_target_column_name)
#             logger.info(f"DB_STORER (store): Attempting UPSERT for {name} on conflict target {conflict_target_column_name}...")
#             upsert_query = sql.SQL("""
#             INSERT INTO user_id_details
#             (card_type, name, dob, aadhaar_no, pan_no, license_no, voter_id_number, expiration_date, father_mother_name, face_embedding)
#             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
#             ON CONFLICT ({conflict_col})
#             DO UPDATE SET
#                 card_type = EXCLUDED.card_type,
#                 name = EXCLUDED.name,
#                 dob = EXCLUDED.dob,
#                 aadhaar_no = COALESCE(EXCLUDED.aadhaar_no, user_id_details.aadhaar_no),
#                 pan_no = COALESCE(EXCLUDED.pan_no, user_id_details.pan_no),
#                 license_no = COALESCE(EXCLUDED.license_no, user_id_details.license_no),
#                 voter_id_number = COALESCE(EXCLUDED.voter_id_number, user_id_details.voter_id_number),
#                 expiration_date = EXCLUDED.expiration_date,
#                 father_mother_name = EXCLUDED.father_mother_name,
#                 face_embedding = EXCLUDED.face_embedding,
#                 registration_timestamp = CURRENT_TIMESTAMP
#             WHERE user_id_details.{conflict_col} = EXCLUDED.{conflict_col}
#             RETURNING id;
#             """).format(conflict_col=conflict_target)

#             cur.execute(upsert_query, (
#                 card_type, name, dob, aadhaar_no, pan_no, license_no, voter_id_number,
#                 expiration_date, father_mother_name, face_embedding_json
#             ))
        
#         inserted_id_row = cur.fetchone()
#         if inserted_id_row:
#             conn.commit()
#             success = True
#             message = f"User details for '{name}' (DB ID: {inserted_id_row[0]}) stored/updated successfully."
#             logger.info(f"DB_STORER (store): {message}")
#         else:
#             # This might happen if ON CONFLICT DO NOTHING was used, or if RETURNING id had no row to return
#             # For UPSERT with DO UPDATE, if no update happened (e.g. WHERE clause in DO UPDATE failed),
#             # and no insert happened, fetchone() could be None.
#             if conn: conn.rollback() # Rollback if no ID returned from an attempted modification
#             message = "Storage action completed, but no ID was returned (e.g., UPSERT condition not met for update and no insert)."
#             logger.warning(f"DB_STORER (store): {message}")
#             # Success might still be true if an ON CONFLICT DO NOTHING was intended and hit,
#             # but for this UPSERT, no ID means the specific update/insert path wasn't fully successful.
#             success = False # Explicitly set to false if no ID returned on an UPSERT.

#     except ConnectionError as conn_err:
#         logger.error(f"DB_STORER (store): Connection error: {conn_err}")
#         message = f"Database connection error: {conn_err}"
#         # No rollback needed if connection failed
#     except psycopg2.Error as db_err:
#         logger.error(f"DB_STORER (store): Psycopg2 database error: {db_err}", exc_info=True)
#         message = f"Database error: {db_err}"
#         if conn: conn.rollback() # Rollback on other DB errors
#     except Exception as e:
#         logger.error(f"DB_STORER (store): An unexpected error occurred: {e}", exc_info=True)
#         message = f"Unexpected error: {e}"
#         if conn: conn.rollback()
#     finally:
#         logger.debug("DB_STORER (store): Entering finally block.")
#         if cur:
#             try: cur.close()
#             except Exception as e_cur: logger.error(f"DB_STORER (store): Error closing cursor: {e_cur}", exc_info=True)
#         if conn:
#             try: conn.close()
#             except Exception as e_conn: logger.error(f"DB_STORER (store): Error closing connection: {e_conn}", exc_info=True)
#         logger.info("DB_STORER (store): Exiting store_verified_user_details().")
    
#     return success, message

# def get_user_by_id_number(id_value, id_type):
#     """Retrieves user details by a specific ID number and type."""
#     logger.info(f"DB_STORER: Entered get_user_by_id_number() for type '{id_type}', value '{str(id_value)[:10]}...'")
#     if id_type not in ['aadhaar_no', 'voter_id_number', 'pan_no', 'license_no']:
#         logger.error(f"DB_STORER (get_user): Invalid id_type '{id_type}' for retrieval.")
#         return None

#     conn = None
#     cur = None
#     user_data = None

#     try:
#         params_dict = get_db_connection_params()
#         conn = _connect_to_db(params_dict)
#         cur = conn.cursor()
#         logger.info("DB_STORER (get_user): Cursor created.")

#         # Using psycopg2.sql for safe dynamic column names
#         query = sql.SQL("SELECT name, dob, face_embedding, card_type, aadhaar_no, pan_no, license_no, voter_id_number FROM user_id_details WHERE {} = %s;").format(
#             sql.Identifier(id_type)
#         )
        
#         # Clean the id_value similarly to how it's stored for matching
#         cleaned_id_value = re.sub(r'\s+', '', str(id_value))
#         if id_type in ['voter_id_number', 'license_no', 'pan_no']:
#             cleaned_id_value = cleaned_id_value.upper()

#         logger.info(f"DB_STORER (get_user): Executing SELECT query for {id_type} = {cleaned_id_value}...")
#         cur.execute(query, (cleaned_id_value,))
#         row = cur.fetchone()

#         if row:
#             logger.info(f"DB_STORER (get_user): User found by {id_type} = {cleaned_id_value}")
#             name, dob, face_embedding_json, card_type_db, aadhaar_db, pan_db, license_db, voter_db = row
#             try:
#                 face_embedding_list = json.loads(face_embedding_json) if face_embedding_json else None
#             except json.JSONDecodeError:
#                 logger.error(f"DB_STORER (get_user): Error decoding face embedding JSON for ID {cleaned_id_value}", exc_info=True)
#                 face_embedding_list = None
            
#             user_data = {
#                 "name": name,
#                 "dob": dob,
#                 "face_embedding": face_embedding_list,
#                 "card_type": card_type_db,
#                 "aadhaar_no": aadhaar_db,
#                 "pan_no": pan_db,
#                 "license_no": license_db,
#                 "voter_id_number": voter_db,
#                 f"{id_type}_used_for_lookup": cleaned_id_value # Clarify which ID was used
#             }
#         else:
#             logger.info(f"DB_STORER (get_user): No user found with {id_type} = {cleaned_id_value}")

#     except ConnectionError as conn_err:
#         logger.error(f"DB_STORER (get_user): Connection error: {conn_err}")
#     except psycopg2.Error as db_err:
#         logger.error(f"DB_STORER (get_user): Psycopg2 database error: {db_err}", exc_info=True)
#     except Exception as e:
#         logger.error(f"DB_STORER (get_user): An unexpected error occurred: {e}", exc_info=True)
#     finally:
#         logger.debug("DB_STORER (get_user): Entering finally block.")
#         if cur:
#             try: cur.close()
#             except Exception as e_cur: logger.error(f"DB_STORER (get_user): Error closing cursor: {e_cur}", exc_info=True)
#         if conn:
#             try: conn.close()
#             except Exception as e_conn: logger.error(f"DB_STORER (get_user): Error closing connection: {e_conn}", exc_info=True)
#         logger.info("DB_STORER (get_user): Exiting get_user_by_id_number().")
    
#     return user_data