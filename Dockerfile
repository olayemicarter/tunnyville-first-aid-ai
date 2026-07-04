# Use official lightweight Python image.
FROM python:3.11-slim

# Allow statements and log messages to immediately appear in the logs
ENV PYTHONUNBUFFERED=True

# Set working directory
WORKDIR /app

# Copy local code to the container image.
COPY . .

# Install production dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Run the web service on container startup. Use gunicorn with 1 worker and 8 threads.
# --bind :$PORT binds to the port provided by Cloud Run.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app