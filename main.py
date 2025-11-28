"""Entry point for the USB receipt printer service."""
from config.settings import SERVICE
from server.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host=SERVICE.get("host", "0.0.0.0"), port=SERVICE.get("port", 5000), debug=SERVICE.get("debug", False))
