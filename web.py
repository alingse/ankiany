import os
import glob
import uuid
from urllib.parse import quote
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from core import run_anki_agent_generator
from session_context import output_dir_var

app = FastAPI()

# Mount static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Ensure outputs directory exists
OUTPUTS_BASE = os.path.join(os.getcwd(), "static", "outputs")
os.makedirs(OUTPUTS_BASE, exist_ok=True)

# Global session store - maps session_id to generated file info
session_files = {}


@app.get("/")
async def get():
    return FileResponse("static/index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    session_dir = os.path.join(OUTPUTS_BASE, session_id)
    os.makedirs(session_dir, exist_ok=True)

    # Set the context var for this session
    token = output_dir_var.set(session_dir)

    try:
        while True:
            data = await websocket.receive_text()
            prompt = data.strip()[:25]  # 限制长度，取前25字符

            # Send start signal
            await websocket.send_json({"type": "start"})

            try:
                # Track generated files in the SESSION directory
                existing_files = set(glob.glob(os.path.join(session_dir, "*.apkg")))

                async for log in run_anki_agent_generator(prompt, verbose=True):
                    await websocket.send_json({"type": "log", "message": log})

                # Find new file in session directory
                current_files = set(glob.glob(os.path.join(session_dir, "*.apkg")))
                new_files = current_files - existing_files

                generated_file_path = None
                if new_files:
                    generated_file_path = max(new_files, key=os.path.getctime)

                if generated_file_path:
                    filename = os.path.basename(generated_file_path)
                    # Store in global session store
                    session_files[session_id] = {
                        "filepath": generated_file_path,
                        "filename": filename
                    }
                    # Send session_id and filename
                    await websocket.send_json(
                        {
                            "type": "complete",
                            "session_id": session_id,
                            "filename": filename,
                        }
                    )
                else:
                    await websocket.send_json(
                        {"type": "error", "message": "No .apkg file was generated."}
                    )

            except Exception as e:
                await websocket.send_json({"type": "error", "message": str(e)})

    except WebSocketDisconnect:
        # Optional: cleanup session directory on disconnect?
        # Maybe keep it for a while so they can download?
        # For now, we leave it. A cron job could clean it up.
        print(f"Client {session_id} disconnected")
    finally:
        output_dir_var.reset(token)


@app.get("/download/{session_id}")
async def download_file(session_id: str):
    """
    Simple secure download using global session store
    """
    # Check if session_id exists in our global store
    if session_id not in session_files:
        raise HTTPException(status_code=404, detail="File not found")

    file_info = session_files[session_id]
    filepath = file_info["filepath"]
    filename = file_info["filename"]

    # Simple security: check file exists and has .apkg extension
    if not os.path.exists(filepath) or not filepath.endswith('.apkg'):
        raise HTTPException(status_code=404, detail="File not found")

    # Encode filename for safe HTTP header
    encoded_filename = quote(filename, safe='')

    return FileResponse(
        filepath,
        media_type="application/octet-stream",
        filename=encoded_filename,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
    )


if __name__ == "__main__":
    import uvicorn
    from uvicorn.config import LOGGING_CONFIG

    # 修改日志格式，加入时间戳
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s %(levelprefix)s %(message)s"
    LOGGING_CONFIG["formatters"]["access"]["fmt"] = '%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'
    LOGGING_CONFIG["formatters"]["default"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    LOGGING_CONFIG["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"

    uvicorn.run("web:app", host="0.0.0.0", port=8001, reload=False)
