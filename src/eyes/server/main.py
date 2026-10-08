import uvicorn

from eyes.server.api.app import create_app
from eyes.server.config import Settings


def main():
    settings = Settings()
    if "local_observation" not in settings.model_fields_set:
        settings.local_observation = True
    uvicorn.run(create_app(settings), host="127.0.0.1", port=8000, proxy_headers=False)
