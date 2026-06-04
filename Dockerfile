FROM python:3.12-slim

WORKDIR /app/Backend

# Install system deps for PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt ../requirements.txt
RUN pip install --no-cache-dir -r ../requirements.txt

# Copy project
COPY . ..

# Create storage dirs
RUN mkdir -p /app/Backend/storage/docs /app/Backend/storage/indexes /app/Backend/storage/texts

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
