FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose is documentation, but good practice
EXPOSE 5005

# Use -u to force unbuffered logs
CMD ["python", "-u", "bridge.py"]