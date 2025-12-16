"""Entry point for running the admin GUI."""

import os

from simConfigGui.app import create_app

if __name__ == "__main__":
    config_name = os.environ.get("FLASK_ENV", "development")
    app = create_app(config_name)
    app.run(debug=True, port=5000, host="0.0.0.0")
