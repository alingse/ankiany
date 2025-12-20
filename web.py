import os
import glob
import uuid
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
            prompt = data

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


@app.get("/download/{session_id}/{filename}")
async def download_file(session_id: str, filename: str):
    # Security check: prevent directory traversal
    if ".." in session_id or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid path")

    file_path = os.path.join(OUTPUTS_BASE, session_id, filename)

    if os.path.exists(file_path) and filename.endswith(".apkg"):
        return FileResponse(
            file_path, media_type="application/octet-stream", filename=filename
        )
    return {"error": "File not found"}
