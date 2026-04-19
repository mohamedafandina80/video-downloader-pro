# استخدام نسخة بايثون خفيفة ومستقرة
FROM python:3.11-slim

# الخطوة السحرية: تسطيب FFmpeg جوه نظام السيرفر (Linux)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# تحديد مكان الشغل
WORKDIR /app

# نسخ ملف المكتبات وتسطيبها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع (main.py, templates, etc.)
COPY . .

# تشغيل السيرفر على البورت اللي Railway بيحدده
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]