"""Entry point for the Paper Management application.

Starts the uvicorn ASGI server with the FastAPI app.
"""

import logging

import uvicorn

from src.config.settings import load_settings

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 12000


def main() -> None:
    """Load settings and start the web server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    settings = load_settings()
    host = settings.get("server", {}).get("host", DEFAULT_HOST)
    port = settings.get("server", {}).get("port", DEFAULT_PORT)

    uvicorn.run(
        "src.web.app:app",
        host=host,
        port=port,
        reload=True,
    )


if __name__ == "__main__":
    main()
