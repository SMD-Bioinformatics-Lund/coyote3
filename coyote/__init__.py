"""Initialize Flask app."""

from flask import Flask
from flask_cors import CORS
import config
from . import extensions


def init_app(testing: bool = False) -> Flask:
    """Create Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    # Allows cross-origin requests for CDM/api
    # /trends needs this to work.
    CORS(app)

    if testing:
        app.logger.info("Testing mode ON.")
        app.logger.info("Loading config.TestConfig")
        app.config.from_object(config.TestConfig())

    elif app.debug:
        app.logger.warning(
            "Debug mode ON. "
            "(Jag ropar ut mitt innersta hav, jag ropar ut all min skit och allt mitt skav!)"
        )
        app.logger.info("Loading config.DevelopmentConfig")
        app.config.from_object(config.DevelopmentConfig())

    else:
        app.logger.info("Loading config.ProductionConfig")
        app.config.from_object(config.ProductionConfig())  # Note initialization of Config

    app.logger.info("Initializing app extensions + blueprints:")
    with app.app_context():
        init_login_manager(app)
        init_db(app)
        init_store(app)
        register_blueprints(app)
        init_ldap(app)
        init_utility(app)

    app.logger.info("App initialization finished. Returning app.")
    return app


def init_db(app) -> None:
    app.logger.info("Initializing MongoDB")
    # TODO: Add connection checks
    app.logger.info("Initializing mongodb at: " f"{app.config['MONGO_URI']}")
    extensions.mongo.init_app(app)


def init_store(app) -> None:
    app.logger.info("Initializing MongoAdapter at: " f"{app.config['MONGO_URI']}")
    extensions.store.init_from_app(app)


def init_utility(app) -> None:
    app.logger.info("Initializing Utility")
    extensions.util.init_util()


def register_blueprints(app) -> None:
    app.logger.info("Initializing blueprints")

    def bp_debug_msg(msg):
        app.logger.debug(f"Blueprint registered: {msg}")

    # Coyote main:
    bp_debug_msg("home_bp")
    from coyote.blueprints.home import home_bp

    app.register_blueprint(home_bp, url_prefix="/samples")

    # Login stuff
    bp_debug_msg("login_bp")
    from coyote.blueprints.login import login_bp

    app.register_blueprint(login_bp, url_prefix="/login")

    # User Profile Stuff
    bp_debug_msg("profile_bp")
    from coyote.blueprints.userprofile import profile_bp

    app.register_blueprint(profile_bp, url_prefix="/profile")

    # Show Case Variants
    bp_debug_msg("dna_bp")
    from coyote.blueprints.dna import dna_bp

    app.register_blueprint(dna_bp, url_prefix="/dna")

    # Show Case fusions
    bp_debug_msg("rna_bp")
    from coyote.blueprints.rna import rna_bp

    app.register_blueprint(rna_bp, url_prefix="/rna")

    # register common bp
    bp_debug_msg("common_bp")
    from coyote.blueprints.common import common_bp

    app.register_blueprint(common_bp, url_prefix="/common")

    # register dashboard bp
    bp_debug_msg("dashboard_bp")
    from coyote.blueprints.dashboard import dashboard_bp

    app.register_blueprint(dashboard_bp, url_prefix="/")

    # register genepanels bp
    bp_debug_msg("genepanels_bp")
    from coyote.blueprints.genepanels import genepanels_bp

    app.register_blueprint(genepanels_bp, url_prefix="/genepanels")


def init_login_manager(app) -> None:
    app.logger.debug("Initializing login_manager")
    extensions.login_manager.init_app(app)
    extensions.login_manager.login_view = "login_bp.login"


def init_ldap(app):
    app.logger.debug("Initializing ldap login_manager")
    extensions.ldap_manager.init_app(app)
