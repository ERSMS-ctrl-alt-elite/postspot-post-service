from http import client
import os
import logging
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify
from flask_swagger_ui import get_swaggerui_blueprint
from google.auth import exceptions

from postspot.data_gateway import FirestoreGateway, NoPostNearbyError, Post, PostNotFoundError
from postspot.config import Config
from postspot.auth import decode_openid_token, get_token
from postspot.constants import Environment, AccountStatus, AUTH_HEADER_NAME

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
        if AUTH_HEADER_NAME not in request.headers:
            return jsonify({"message": "Token not provided"}), 401
        
        token = get_token(request)
        if not token:
            return jsonify({"message": "Invalid token"}), 401

        try:
            (
                google_id,
                name,
                email,
                token_issued_t,
                token_expired_t,
            ) = decode_openid_token(token)
        except exceptions.GoogleAuthError as e:
            logger.error(f"Invalid token - issuer invalid: {e}")
            return jsonify({"message": "Invalid token or user not signed up"}), 401
        except ValueError as e:
            logger.error(f"Invalid token: {e}")
            return jsonify({"message": "Invalid token or user not signed up"}), 401

        token_issued_at_datetime = datetime.fromtimestamp(token_issued_t)
        token_exp_datetime = datetime.fromtimestamp(token_expired_t)
        logger.debug(
            f"Token issued at {token_issued_at_datetime} ({token_issued_t})"
        )
        logger.debug(f"Token expires at {token_exp_datetime} ({token_expired_t})")

        if not data_gateway.user_exists(google_id):
            logger.error(f"User not signed up")
            return jsonify({"message": "Invalid token or user not signed up"}), 401
        
        return function(google_id, *args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------- #
#                                   Endpoints                                  #
# ---------------------------------------------------------------------------- #


@app.route("/v1")
def index():
    return "Hello from PostSpot's post service"

@app.route("/v1/posts", methods=["POST"])
@user_signed_up
def add_post(google_id):
    title = request.json.get('title')
    content = request.json.get('content')
    longitude = float(request.json.get('longitude'))
    latitude = float(request.json.get('latitude'))

    post_id = data_gateway.add_post(
        author_google_id = google_id,
        title = title,
        content = content,
        longitude = longitude,
        latitude = latitude,
    )

    return jsonify({"message": f"Post {post_id=} added by user {google_id=}"}), 201

@app.route("/v1/posts/<post_id>", methods=["GET"])
def read_post(post_id: str):
    try:
        return data_gateway.read_post(post_id)
    except PostNotFoundError:
        return jsonify({"message": f"No post with {post_id=} found"}), 404

@app.route('/v1/posts/<float:longitude>/<float:latitude>', methods=['GET'])
def get_posts_nearby(longitude: float, latitude: float, radius_in_kilometers: float = 0.07):
    try:
        return data_gateway.get_posts_within_radius(longitude, latitude, radius_in_kilometers)
    except NoPostNearbyError:
        return jsonify({"message": f"No posts within {radius_in_kilometers} km of ({longitude=}, {latitude=})"}), 404


@app.route('/v1/posts', methods=['GET'])
def get_posts_from_author():
    author_google_id = request.args.get('author')
    return data_gateway.get_post_from_author(author_google_id)
    

if __name__ == "__main__":
    debug = env != Environment.PRODUCTION
    app.run(debug=debug, port=8081)
