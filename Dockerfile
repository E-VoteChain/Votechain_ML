# Votechain_ML/Dockerfile

# ---- Builder Stage ----
FROM python:3.11-slim-bullseye AS builder

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    # Add any other build-time OS deps for your packages
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements to leverage Docker cache
COPY requirements_final_cpu.txt ./

# Create a virtual environment in the builder stage
RUN python -m venv /opt/venv
# Activate venv and install packages
# Using venv helps isolate packages and makes it easier to copy to the final stage
RUN . /opt/venv/bin/activate && \
    pip install --default-timeout=300 --no-cache-dir -r requirements_final_cpu.txt

# ---- Final Stage ----
FROM python:3.11-slim-bullseye

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    MODULE_NAME="app" \
    VARIABLE_NAME="app" \
    PORT="8080" \
    # Important: Add the venv to PATH
    PATH="/opt/venv/bin:$PATH"

# Install runtime system dependencies
# libgl1-mesa-glx, libglib2.0-0: For opencv-python-headless.
# Add other OS-level runtime packages if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    # If you were NOT using psycopg2-binary, you'd need: libpq5
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy your application code
COPY . .

RUN mkdir -p /app/uploads

EXPOSE ${PORT}
CMD ["/bin/sh", "-c", "exec gunicorn --bind \"0.0.0.0:$PORT\" --workers 2 --threads 2 --timeout 120 app:app"]