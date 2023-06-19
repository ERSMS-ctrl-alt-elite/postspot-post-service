from http import client
import os
import logging
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify
from flask_swagger_ui import get_swaggerui_blueprint

from postspot.data_gateway import FirestoreGateway, Post
from postspot.config import Config
from postspot.auth import decode_openid_token
from postspot.constants import Environment, AccountStatus

# ---------------------------------------------------------------------------- #
#                                   App init                                   #
# ---------------------------------------------------------------------------- #

env = Environment(os.environ["ENV"]) if "ENV" in os.environ else Environment.PRODUCTION

config = Config(env)

# ----------------------------- Configure logging ---------------------------- #
logging.basicConfig(
    level=config.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ------------------------------- Create an app ------------------------------ #
logger.info(f"Running application in {env.value} environment")
app = Flask("PostSpot Post Service")
app.secret_key = "PostSpot123"

# -------------------------- Create database gateway ------------------------- #
data_gateway = FirestoreGateway()

# --------------------------- Configure Swagger UI --------------------------- #
SWAGGER_URL = "/swagger"
API_URL = "/static/swagger.json"
SWAGGERUI_BLUEPRINT = get_swaggerui_blueprint(
    SWAGGER_URL, API_URL, config={"app_name": "Seans-Python-Flask-REST-Boilerplate"}
)
app.register_blueprint(SWAGGERUI_BLUEPRINT, url_prefix=SWAGGER_URL)


def user_signed_up(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        token = None

        if "Authorization" in request.headers:
            bearer = request.headers.get("Authorization")
            token = bearer.split()[1]

        if not token:
            return jsonify({"message": "Token not provided"}), 401

        try:
            (
                google_id,
                name,
                email,
                token_issued_t,
                token_expired_t,
            ) = decode_openid_token(token)

            token_issued_at_datetime = datetime.fromtimestamp(token_issued_t)
            token_exp_datetime = datetime.fromtimestamp(token_expired_t)
            logger.debug(
                f"Token issued at {token_issued_at_datetime} ({token_issued_t})"
            )
            logger.debug(f"Token expires at {token_exp_datetime} ({token_expired_t})")

            if not data_gateway.user_exists(google_id):
                return jsonify({"message": "Invalid token or user not signed up"}), 401
        except Exception as e:
            logger.error(f"Invalid token: {e}")
            return jsonify({"message": "Invalid token or user not signed up"}), 401

        return function(google_id, *args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------- #
#                                   Endpoints                                  #
# ---------------------------------------------------------------------------- #


@app.route("/")
def index():
    return "Hello from PostSpot's post service"

@user_signed_up
@app.route("/posts", methods=["POST"])
def add_post(google_id: str):
    if not google_id:
        return "Request body does not contain google_id of author"

    title = request.json.get('title')
    content = request.json.get('content')
    longitude = request.json.get('longitude')
    latitude = request.json.get('latitude')

    post_id = data_gateway.add_post(
        author_google_id = google_id,
        title = title,
        content = content,
        longitude = longitude,
        latitude = latitude,
    )

    return f"Post {post_id=} added by user {google_id=}", 201

@app.route("/posts/<post_id>", methods=["GET"])
def read_post(post_id: str):
    return data_gateway.read_post(post_id)


if __name__ == "__main__":
    debug = env != Environment.PRODUCTION
    app.run(debug=debug, port=8080)
