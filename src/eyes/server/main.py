import uvicorn


def main():
    uvicorn.run("eyes.server.api.app:create_app", factory=True, host="127.0.0.1", port=8000)
