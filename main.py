import os
import uvicorn
import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
base_dir = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/analyze")
async def analyze_video(data: dict):
    url = data.get("url")
    if not url: 
        return {"success": False, "error": "الرابط فارغ"}
    
    # الجودات الثابتة اللي هنطلبها من السيرفرات العالمية
    formats = [
        {"id": "1080", "label": "فيديو 1080p - جودة عالية", "type": "video"},
        {"id": "720", "label": "فيديو 720p - جودة متوسطة", "type": "video"},
        {"id": "audio", "label": "ملف صوتي - نقي جداً", "type": "audio"}
    ]
    
    title = "فيديو جاهز للتحميل"
    thumb = "https://via.placeholder.com/600x400/000000/ffd700?text=U2+DOWNLOADER"
    
    try:
        if "youtu" in url:
            oembed = requests.get(f"https://www.youtube.com/oembed?url={url}&format=json", timeout=5).json()
            title = oembed.get("title", title)
            thumb = oembed.get("thumbnail_url", thumb)
    except: pass

    return {"success": True, "title": title, "thumbnail": thumb, "formats": formats}

@app.get("/get_link")
async def get_link(url: str, format_id: str):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {"url": url, "filenamePattern": "pretty"}
    
    if format_id == "audio":
        payload["isAudioOnly"] = True
    else:
        payload["videoQuality"] = format_id

    # سيرفرات اختراق الحجب
    SERVERS = [
        "https://api.cobalt.tools",
        "https://cobalt.api.un-lock.site",
        "https://cobalt.zephex.ca",
        "https://api.vxtwitter.com/cobalt"
    ]
    
    for api in SERVERS:
        try:
            res = requests.post(api, json=payload, headers=headers, timeout=12)
            if res.status_code == 200 and "url" in res.json():
                return {"success": True, "download_url": res.json()["url"]}
        except: continue
        
    return {"success": False, "error": "جميع السيرفرات العالمية مشغولة حالياً، جرب مرة أخرى."}

@app.get("/stream")
async def stream_video(url: str):
    headers_dict = {}
    try:
        # جلب حجم الملف عشان عداد الـ HUD يشتغل عند المستخدم
        head_res = requests.head(url, timeout=5)
        if 'Content-Length' in head_res.headers:
            headers_dict['Content-Length'] = head_res.headers['Content-Length']
    except: pass
    
    headers_dict["Content-Disposition"] = "attachment; filename=U2_Empire_Download.mp4"
    
    def iter_file():
        # تمرير البيانات كشلال من السيرفر للمتصفح
        with requests.get(url, stream=True) as r:
            for chunk in r.iter_content(chunk_size=1024*512):
                if chunk: yield chunk
                
    return StreamingResponse(iter_file(), media_type="application/octet-stream", headers=headers_dict)

if __name__ == "__main__":
    # تهيئة البورت ليتوافق مع منصة Railway أوتوماتيكياً
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)