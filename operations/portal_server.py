"""Same-origin application server backed exclusively by configured PostgreSQL."""
from pathlib import Path
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from operations.api_v1.app import create_app


def application():
    app = create_app()
    root = Path(__file__).resolve().parents[1] / "goob-dispatch" / "dist"

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path in {"terms", "privacy"}:
            title = "Demo terms of use" if path == "terms" else "Demo privacy notice"
            detail = ("Do not rely on this fictional demonstration for navigation or emergency dispatch."
                      if path == "terms" else
                      "Workspace records and sessions are stored in Tiger Cloud PostgreSQL. Google route results remain in active browser memory. Microphone audio is sent to ElevenLabs only after you start transcription; Goob does not persist the transcript. View preferences stay on your device.")
            return HTMLResponse('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+title+'</title><style>body{max-width:700px;margin:60px auto;padding:24px;background:#faf8f2;color:#342434;font:17px/1.7 system-ui}h1{font-family:Georgia}</style><a href="/">Return to Goob</a><h1>'+title+'</h1><p>'+detail+'</p><p>Provider features are subject to <a href="https://maps.google.com/help/terms_maps/">Google Maps terms</a>, <a href="https://policies.google.com/privacy">Google privacy policy</a> and <a href="https://elevenlabs.io/privacy-policy">ElevenLabs privacy policy</a>.</p></html>')
        if path.startswith(("api/", "health/")):
            return JSONResponse({"error": "Endpoint not found."}, status_code=404)
        candidate = (root / path).resolve()
        if candidate.is_relative_to(root.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        if root.joinpath("index.html").is_file():
            return FileResponse(root / "index.html")
        return JSONResponse({"error": "Build the frontend before starting the portal."}, status_code=503)

    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(application(), host="127.0.0.1", port=8090)
