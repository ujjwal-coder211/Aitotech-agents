# ===========================================================
#  FastAPI backend (orchestrator + API) के लिए Docker image
#  Railway / Render / किसी भी container host पर deploy होता है।
#  Python 3.12 इसलिए ताकि सभी deps के prebuilt wheels मिलें
#  (3.14 पर pydantic-core/pyiceberg source-build की दिक्कत आती है)।
# ===========================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# पहले सिर्फ requirements copy करें ताकि Docker layer cache काम करे
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# app code
COPY src ./src

# Railway $PORT env देता है; local पर 8000 default
EXPOSE 8000
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
