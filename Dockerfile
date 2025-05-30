# Votechain_ML/Dockerfile

# Use a Python version that matches your development and testing.
# Python 3.10 or 3.11 are good modern choices.
FROM python:3.11-slim-bullseye

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    # Gunicorn needs to know where your Flask app object is.
    # Assuming your Flask app file is app.py and the Flask instance is named 'app'.
    MODULE_NAME="app" \
    VARIABLE_NAME="app" \
    # Set a default PORT if not provided by Render (Render will provide $PORT)
    PORT="8080"

# Install system dependencies.
# - build-essential & cmake: For compiling 'dlib' (a dependency of deepface).
# - libgl1-mesa-glx, libglib2.0-0: For opencv-python-headless.
# Add other OS-level packages if your specific dependencies require them.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libgl1-mesa-glx \
    libglib2.0-0 \
    # If you were NOT using psycopg2-binary, you'd need: libpq-dev
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container.
WORKDIR /app

# Copy the cleaned requirements file.
COPY requirements_render.txt ./

# Install Python dependencies.
# --no-cache-dir is good practice for smaller image sizes.
# Increase timeout to 5 minutes (300 seconds) - adjust as needed
RUN pip install --default-timeout=300 --no-cache-dir -r requirements_render.txt

# Copy your application code into the container.
# This includes app.py, the ml_logic/ folder, dummy_face_for_liveness.jpg, etc.
COPY . .

# Ensure the 'uploads' directory (used by Flask for temporary file storage) exists.
# Your app.py also creates it, but this ensures it's there at build time.
RUN mkdir -p /app/uploads

# Expose the port that Gunicorn will run on inside the container.
# This should match the $PORT environment variable Gunicorn will use.
EXPOSE ${PORT}

# Command to run the application using Gunicorn.
# Gunicorn is a production-ready WSGI server for Python.
# Render will set the $PORT environment variable.
# --workers: Number of worker processes. Start with 2-4.
# --threads: Number of threads per worker (if your tasks are I/O bound or release GIL).
# --timeout: Worker timeout in seconds. ML can be slow.
CMD ["gunicorn", "--bind", "0.0.0.0:${PORT:-8080}", "--workers", "2", "--threads", "2", "--timeout", "120", "app:app"]