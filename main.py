import os
import uuid
from fastapi import FastAPI, Form, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Project Folders
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def cleanup(file_path: str):
    """Delete the file after the user downloads it to save server space"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Cleanup error: {e}")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/get_info")
async def get_video_info(url: str = Form(...)):
    ydl_opts = {'quiet': True, 'no_warnings': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats_list = []
            
            seen_heights = set()
            for f in info.get('formats', []):
                h = f.get('height')
                # Filter for clean UI: 360p, 720p, 1080p etc.
                if h and h not in seen_heights and f.get('vcodec') != 'none':
                    seen_heights.add(h)
                    formats_list.append({
                        "id": f.get('format_id'),
                        "resolution": f"{h}p",
                        "ext": "mp4"
                    })
            
            formats_list.sort(key=lambda x: int(x['resolution'].replace('p','')), reverse=True)
            formats_list.append({"id": "bestaudio", "resolution": "MP3/Audio", "ext": "mp3"})

            return {
                "title": info.get('title'),
                "thumbnail": info.get('thumbnail'),
                "url": url,
                "formats": formats_list
            }
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL or Private Video.")

@app.get("/download")
async def download_media(url: str, format_id: str, background_tasks: BackgroundTasks):
    file_id = str(uuid.uuid4())
    is_audio = format_id == "bestaudio"
    ext = "mp3" if is_audio else "mp4"
    output_filename = f"{file_id}.{ext}"
    output_path = os.path.join(DOWNLOAD_DIR, output_filename)

    ydl_opts = {
        'outtmpl': output_path.replace(f'.{ext}', ''), 
        'quiet': True,
        'no_warnings': True,
    }

    if is_audio:
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        # Crucial: Merges Video + Audio using FFmpeg automatically
        res = format_id.replace('p','')
        ydl_opts.update({
            'format': f'bestvideo[height<={res}]+bestaudio/best',
            'merge_output_format': 'mp4',
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        final_path = output_path if os.path.exists(output_path) else output_path + f".{ext}"
        response = FileResponse(path=final_path, filename=f"X-Downloader_{ext}.{ext}")
        background_tasks.add_task(cleanup, final_path)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail="FFmpeg Error: Download failed.")