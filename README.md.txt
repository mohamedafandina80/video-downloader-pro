# 🚀 X-Downloader Pro: All-in-One Video & MP3 SaaS Solution
"Supports 1000+ platforms including YouTube, TikTok (No Watermark), Instagram, and more."

X-Downloader Pro is a high-performance, modern web application built with **FastAPI** and **yt-dlp**. It’s not just a downloader; it’s a complete solution for high-resolution video merging and automatic MP3 conversion.

## ✨ Key Features
- **Modern UI:** Sleek, mobile-responsive Dark Mode design using **Tailwind CSS**.
- **Automatic Merging (1080p/4K):** Unlike other scripts, this one uses **FFmpeg** to merge high-quality video and audio streams into a single file on the server.
- **Instant MP3 Conversion:** One-click extraction and conversion to high-quality audio (192kbps).
- **Auto-Cleanup Engine:** Temporary files are automatically deleted from the server after the user completes the download to save storage space.
- **FastAPI Backend:** Built on the fastest Python framework for low latency and high concurrency.
- **Massive Platform Support:** Powered by `yt-dlp`, supporting 1000+ sites including YouTube, TikTok (No Watermark), Facebook, Instagram, and Twitter.
- **Ad-Ready:** Includes strategic placeholders for your advertisement banners (AdSense, Adsterra, etc.).

## 🛠 Tech Stack
- **Language:** Python 3.8+
- **Framework:** FastAPI
- **Frontend:** HTML5 / Tailwind CSS / JavaScript
- **Core Engine:** yt-dlp
- **Processing:** FFmpeg (Required for Merging & MP3)

---

## 🚀 Installation & Setup

### 1. Install FFmpeg (Crucial)
To enable high-quality merging and MP3 features, FFmpeg must be installed on your server:
- **Ubuntu/Debian:** `sudo apt update && sudo apt install ffmpeg -y`
- **Windows:** Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add the `/bin` folder to your System PATH.
- **MacOS:** `brew install ffmpeg`

### 2. Setup the Environment
Clone the repository and install the required Python libraries:
```bash
pip install -r requirements.txt

3. Run the App
Launch the server using Uvicorn: uvicorn main:app --reload

Access the app at: http://localhost:8000

📂 Project Structure
main.py: Core backend logic and download manager.

templates/: Modern frontend template (index.html).

downloads/: Temporary storage for processed media (Managed by Auto-Cleanup).

requirements.txt: Python dependencies.

💡 Why Choose X-Downloader Pro?
Most downloaders only provide 360p links or separate video/audio files for 1080p. X-Downloader Pro provides a Seamless User Experience by handling the heavy lifting (Merging/Conversion) on the server, giving your users exactly what they want in one click.

Looking for a Demo or Support?
Feel free to contact me via DM on Reddit or Email. I can assist with server deployment and FFmpeg configuration.