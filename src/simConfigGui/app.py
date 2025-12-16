"""Flask admin GUI for pm6 simulation management."""

from pathlib import Path

from flask import Flask, render_template

from simConfigGui.config import config


def create_app(config_name: str = "development") -> Flask:
    """Application factory.

    Args:
        config_name: Configuration to use (development, testing, production).

    Returns:
        Configured Flask application.
    """
    app = Flask(__name__)
    app.config.from_object(config.get(config_name, config["default"]))

    # Initialize simulation storage
    app.simulations = {}  # name -> Simulation instance
    app.db_path = Path(app.config.get("DB_PATH", "./db"))
    app.db_path.mkdir(parents=True, exist_ok=True)

    # Auto-load existing simulations from disk
    _load_existing_simulations(app)

    # Register blueprints
    from simConfigGui.routes.simulation import simulation_bp
    from simConfigGui.routes.agents import agents_bp
    from simConfigGui.routes.events import events_bp
    from simConfigGui.routes.testing import testing_bp
    from simConfigGui.routes.api import api_bp

    app.register_blueprint(simulation_bp, url_prefix="/simulations")
    app.register_blueprint(agents_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(testing_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # Index route
    @app.route("/")
    def index():
        return render_template(
            "index.html",
            simulations=list(app.simulations.keys()),
            sim_count=len(app.simulations),
        )

    return app


def _load_existing_simulations(app: Flask) -> None:
    """Load existing simulations from disk on startup."""
    from pm6 import Simulation

    if not app.db_path.exists():
        return

    # Each subdirectory in db_path is a simulation
    for sim_dir in app.db_path.iterdir():
        if sim_dir.is_dir() and not sim_dir.name.startswith("."):
            try:
                # Check if it has agents folder (indicates valid simulation)
                agents_dir = sim_dir / "agents"
                if agents_dir.exists():
                    sim = Simulation(
                        name=sim_dir.name,
                        dbPath=app.db_path,
                        testMode=True,  # Default to test mode on reload
                        enableCache=False,
                    )
                    app.simulations[sim_dir.name] = sim
                    app.logger.info(f"Loaded simulation: {sim_dir.name}")
            except Exception as e:
                app.logger.warning(f"Failed to load simulation {sim_dir.name}: {e}")
