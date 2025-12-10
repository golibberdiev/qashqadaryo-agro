# Backend uchun Python bazaviy imidj
FROM python:3.11-slim

# Ishchi katalog
WORKDIR /app

# Kerakli sistem paketlar (agar kerak bo‘lsa, hozircha minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Python kutubxonalarini o‘rnatamiz
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyihadagi barcha fayllarni konteyner ichiga nusxalash
COPY . .

# Railway odatda PORT muhit o‘zgaruvchisini beradi, shuni ishlatamiz
ENV PORT=8000

# Uvicorn orqali FastAPI ilovani ishga tushirish
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
