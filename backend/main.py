from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import yt_dlp
import os
import uuid
import requests

app = FastAPI(title="Video Saver Pro API")

# Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class URLRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format_id: str

def resolve_url(url: str) -> str:
    if "/share/" in url or "/reel/" in url:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 10)'}
            response = requests.head(url, allow_redirects=True, timeout=15, headers=headers)
            return response.url
        except:
            pass
    return url

@app.post("/api/extract")
async def extract_video(request: URLRequest):
    real_url = resolve_url(request.url)
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(real_url, download=False)
            formats = []
            formats.append({
                "format_id": "best",
                "quality": "Best (Auto)",
                "size_mb": "Auto",
                "has_audio": True,
                "note": "Best available quality"
            })
            formats.append({
                "format_id": "best[height<=720]",
                "quality": "720p",
                "size_mb": "Auto",
                "has_audio": True,
                "note": "HD quality"
            })
            formats.append({
                "format_id": "best[height<=480]",
                "quality": "480p",
                "size_mb": "Auto",
                "has_audio": True,
                "note": "Good quality"
            })
            formats.append({
                "format_id": "worst",
                "quality": "360p",
                "size_mb": "Auto",
                "has_audio": True,
                "note": "Small file"
            })
            return {
                "success": True,
                "title": info.get('title', 'Unknown'),
                "duration": info.get('duration', 0),
                "thumbnail": info.get('thumbnail', ''),
                "uploader": info.get('uploader', 'Unknown'),
                "formats": formats
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/download")
async def download_video(request: DownloadRequest):
    """Download video and save to file"""
    real_url = resolve_url(request.url)
    video_id = str(uuid.uuid4())[:8]
    outtmpl = f"{DOWNLOAD_DIR}/{video_id}.%(ext)s"
    
    ydl_opts = {
        'format': request.format_id,
        'outtmpl': outtmpl,
        'merge_output_format': 'mp4',
        'user_agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(real_url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Fix extension
            if not filename.endswith('.mp4'):
                filename = filename.rsplit('.', 1)[0] + '.mp4'
            
            # Check if file exists
            if not os.path.exists(filename):
                # Find actual file in downloads folder
                files = os.listdir(DOWNLOAD_DIR)
                for f in files:
                    if video_id in f:
                        filename = os.path.join(DOWNLOAD_DIR, f)
                        break
            
            if not os.path.exists(filename):
                return {"success": False, "error": "File not found after download"}
            
            file_size = os.path.getsize(filename)
            size_mb = round(file_size / (1024*1024), 1)
            
            return {
    "success": True,
    "video_id": video_id,
    "file_path": filename,
    "size_mb":  size_mb,
    "download_url": f"/downloads/{os.path.basename(filename)}"
} 
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
# Serve downloaded files
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")

# Serve frontend HTML
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_content = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Video Saver Pro</title>

<style>
body{
    font-family:sans-serif;
    background:#1a1a2e;
    color:white;
    text-align:center;
    padding:20px;
}

.header{
    background:#e94560;
    padding:20px;
    border-radius:10px;
    margin-bottom:20px;
}

.input{
    width:100%;
    padding:15px;
    border-radius:10px;
    border:none;
    margin:10px 0;
}

.btn{
    width:100%;
    padding:15px;
    background:#e94560;
    border:none;
    color:white;
    border-radius:10px;
    cursor:pointer;
    margin:10px 0;
}

.result{
    display:none;
    margin-top:20px;
}

.thumb{
    width:100%;
    border-radius:10px;
}

.quality{
    padding:10px;
    margin:5px;
    background:#0f3460;
    border-radius:8px;
    cursor:pointer;
}

.quality.selected{
    border:2px solid #e94560;
}

.ad{
    margin:10px 0;
    background:#0f3460;
    padding:10px;
    border-radius:8px;
}
</style>
</head>

<body>

<div class="header">
<h1>Video Saver Pro</h1>
<p>Download Videos Easily</p>
</div>

<div class="ad">Ad Space (Top)</div>

<input id="url" class="input" placeholder="Paste video link here">

<button class="btn" onclick="extract()">Extract Video</button>

<div id="loading" style="display:none;">Loading...</div>

<div class="result" id="result">
    <img id="thumb" class="thumb">
    <h3 id="title"></h3>
    <div id="formats"></div>
    <button class="btn" onclick="downloadVideo()">Download</button>
</div>

<div class="ad">Ad Space (Bottom)</div>

<script>
let videoData = null;
let selectedFormat = "best";

async function extract(){
    let url = document.getElementById("url").value;
    if(!url) return alert("Paste URL");

    document.getElementById("loading").style.display="block";

    let res = await fetch("/api/extract", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({url})
    });

    let data = await res.json();
    document.getElementById("loading").style.display="none";

    if(data.success){
        videoData = data;
        document.getElementById("result").style.display="block";
        document.getElementById("thumb").src = data.thumbnail;
        document.getElementById("title").innerText = data.title;

        let html = "";
        data.formats.forEach(f=>{
            html += `<div class="quality" onclick="selectFormat('${f.format_id}', this)">
                        ${f.quality}
                     </div>`;
        });

        document.getElementById("formats").innerHTML = html;
    } else {
        alert(data.error);
    }
}

function selectFormat(fmt, el){
    selectedFormat = fmt;
    document.querySelectorAll(".quality").forEach(e=>e.classList.remove("selected"));
    el.classList.add("selected");
}

async function downloadVideo(){
    let res = await fetch("/api/download", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
            url: videoData.originalUrl,
            format_id: selectedFormat
        })
    });

    let data = await res.json();

    if(data.success){
        window.open(data.download_url, "_blank");
    } else {
        alert(data.error);
    }
}
</script>

<div style="margin-top:20px;">
    <a href="/privacy" style="color:#e94560;">Privacy</a> |
    <a href="/terms" style="color:#e94560;">Terms</a> |
    <a href="/about" style="color:#e94560;">About</a>
</div>

</body>
</html>
"""
    return html_content
