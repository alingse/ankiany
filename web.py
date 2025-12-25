import os
import glob
import uuid
import asyncio
import time
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


async def run_generation_task(
    websocket: WebSocket, prompt: str, session_dir: str, session_id: str
):
    """
    Helper to run the generator and handle its output.
    """
    try:
        # Track generated files in the SESSION directory
        existing_files = set(glob.glob(os.path.join(session_dir, "*.apkg")))

        start_time = time.perf_counter()
        async for log in run_anki_agent_generator(prompt, verbose=True):
            try:
                await websocket.send_json({"type": "log", "message": log})
            except (RuntimeError, WebSocketDisconnect):
                # Socket is closed, stop generating and exit loop to trigger cleanup
                print(
                    f"WebSocket closed for session {session_id}, stopping generation."
                )
                return
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time

        # Find new file in session directory
        current_files = set(glob.glob(os.path.join(session_dir, "*.apkg")))
        new_files = current_files - existing_files

        generated_file_path = None
        if new_files:
            generated_file_path = max(new_files, key=os.path.getctime)

        if generated_file_path:
            filename = os.path.basename(generated_file_path)
            yield_msg = f"✨ 成功生成 Anki 包: {filename}"
            try:
                await websocket.send_json({"type": "log", "message": yield_msg})
                print(f"File generated for {session_id}: {generated_file_path}")

                # Store in global session store
                session_files[session_id] = {
                    "filepath": generated_file_path,
                    "filename": filename,
                }
                # Send session_id and filename
                await websocket.send_json(
                    {
                        "type": "complete",
                        "session_id": session_id,
                        "filename": filename,
                        "elapsed_time": elapsed_time,
                    }
                )
            except (RuntimeError, WebSocketDisconnect):
                pass
        else:
            try:
                await websocket.send_json(
                    {"type": "error", "message": "No .apkg file was generated."}
                )
            except (RuntimeError, WebSocketDisconnect):
                pass
    except asyncio.CancelledError:
        print(f"Generation task for session {session_id} was cancelled.")
        # The 'async with' in core.py will handle the actual Claude process cleanup
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    session_dir = os.path.join(OUTPUTS_BASE, session_id)
    os.makedirs(session_dir, exist_ok=True)

    # Set the context var for this session
    token = output_dir_var.set(session_dir)
    print(f"New session started: {session_id}")

    generation_task = None

    try:
        while True:
            data = await websocket.receive_text()
            prompt = data.strip()
            print(f"User Query [{session_id}]: {prompt}")

            # Cancel previous task if still running
            if generation_task and not generation_task.done():
                generation_task.cancel()
                try:
                    await generation_task
                except asyncio.CancelledError:
                    pass

            # Send start signal
            await websocket.send_json({"type": "start"})

            # Start new generation task
            generation_task = asyncio.create_task(
                run_generation_task(websocket, prompt, session_dir, session_id)
            )

    except WebSocketDisconnect:
        print(f"Client {session_id} disconnected.")
    finally:
        if generation_task and not generation_task.done():
            print(f"Cancelling active generation task for {session_id}")
            generation_task.cancel()
            try:
                # IMPORTANT: We must await the cancelled task to allow its
                # finally blocks and async context managers to clean up.
                await generation_task
            except asyncio.CancelledError:
                print(
                    f"Active generation task for {session_id} successfully cancelled."
                )
            except Exception as e:
                print(f"Error during task cancellation for {session_id}: {e}")

        output_dir_var.reset(token)
        print(f"Session cleaned up: {session_id}")


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

    print(f"User triggered download for session {session_id}: {filename}")

    # Simple security: check file exists and has .apkg extension
    if not os.path.exists(filepath) or not filepath.endswith(".apkg"):
        raise HTTPException(status_code=404, detail="File not found")

    # Encode filename for safe HTTP header
    encoded_filename = quote(filename, safe="")

    return FileResponse(
        filepath,
        media_type="application/octet-stream",
        filename=encoded_filename,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        },
    )


if __name__ == "__main__":
    import uvicorn
    from uvicorn.config import LOGGING_CONFIG
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Run the Anki card generation web server"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port to run the server on (default: 8001)",
    )
    args = parser.parse_args()

    # 修改日志格式，加入时间戳
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = (
        "%(asctime)s %(levelprefix)s %(message)s"
    )
    LOGGING_CONFIG["formatters"]["access"]["fmt"] = (
        '%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'
    )
    LOGGING_CONFIG["formatters"]["default"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    LOGGING_CONFIG["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"

    print(f"Starting server on port {args.port}")
    uvicorn.run("web:app", host="0.0.0.0", port=args.port, reload=False)
