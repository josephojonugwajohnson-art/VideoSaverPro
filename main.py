from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import yt_dlp
import os
import uuid

app = FastAPI(title="Video Saver Pro API")

# CORS (allow frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Downloads folder
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Request models
class URLRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format_id: str


# Resolve URL (simple safe version)
def resolve_url(url: str) -> str:
    return url


# Extract video info
@app.post("/api/extract")
async def extract_video(request: URLRequest):
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "user_agent": "Mozilla/5.0"
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.url, download=False)

        formats = [
            {"format_id": "best", "quality": "Best", "note": "Auto best quality"},
            {"format_id": "best[height<=720]", "quality": "720p", "note": "HD"},
            {"format_id": "best[height<=480]", "quality": "480p", "note": "Medium"},
            {"format_id": "worst", "quality": "360p", "note": "Small size"}
        ]

        return {
            "success": True,
            "title": info.get("title", "Unknown"),
            "thumbnail": info.get("thumbnail", ""),
            "duration": info.get("duration", 0),
            "uploader": info.get("uploader", "Unknown"),
            "formats": formats
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# Download video
@app.post("/api/download")
async def download_video(request: DownloadRequest):
    try:
        video_id = str(uuid.uuid4())[:8]
        output_path = f"{DOWNLOAD_DIR}/{video_id}.%(ext)s"

        ydl_opts = {
            "format": request.format_id,
            "outtmpl": output_path,
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True,
            "user_agent": "Mozilla/5.0"
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.url, download=True)
            filename = ydl.prepare_filename(info)

        # find correct file
        if not os.path.exists(filename):
            base = os.path.splitext(filename)[0]
            for ext in ["mp4", "webm", "mkv"]:
                alt = base + "." + ext
                if os.path.exists(alt):
                    filename = alt
                    break

        if not os.path.exists(filename):
            return {"success": False, "error": "File not found"}

        return FileResponse(
            path=filename,
            media_type="video/mp4",
            filename="video.mp4"
        )

    except Exception as e:
        return {"success": False, "error": str(e)}


# Health check
@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Frontend UI
@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Video Saver Pro</title>
        <style>
            body { font-family: Arial; background:#1a1a2e; color:white; text-align:center; padding:20px; }
            input { width:90%; padding:10px; margin:10px; }
            button { padding:10px 20px; background:#e94560; color:white; border:none; cursor:pointer; }
            .box { margin-top:20px; }
        </style>
    </head>
    <body>
        <h1>Video Saver Pro</h1>
        <input id="url" placeholder="Paste video URL here">
        <br>
        <button onclick="extract()">Extract</button>

        <div class="box" id="result"></div>

        <script>
            async function extract() {
                const url = document.getElementById("url").value;

                const res = await fetch("/api/extract", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({url})
                });

                const data = await res.json();

                document.getElementById("result").innerHTML =
                    data.success ?
                    `<h3>${data.title}</h3>
                     <img src="${data.thumbnail}" width="200"><br><br>
                     <button onclick="downloadVideo('${url}', 'best')">Download</button>`
                    :
                    "Error: " + data.error;
            }

            async function downloadVideo(url, format_id) {
                const res = await fetch("/api/download", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({url, format_id})
                });

                const blob = await res.blob();
                const link = document.createElement("a");
                link.href = window.URL.createObjectURL(blob);
                link.download = "video.mp4";
                link.click();
            }
        </script>
    </body>
    </html>
    """
