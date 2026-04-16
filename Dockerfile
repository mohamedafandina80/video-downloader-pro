# استخدام نسخة بايثون خفيفة
FROM python:3.11-slim

# تحديث النظام وتسطيب وحش الدمج FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# تحديد مجلد العمل
WORKDIR /app

# نسخ ملف المكتبات وتسطيبها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع (main.py ومجلد templates)
COPY . .

# تشغيل الإمبراطورية
CMD ["python", "main.py"]
