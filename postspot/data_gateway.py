from importlib.resources import contents
import logging
from abc import ABC, abstractmethod
from math import sin, cos, sqrt, atan2, radians

from google.cloud import firestore

from postspot.constants import AccountStatus


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------- #
#                                   Interface                                  #
# ---------------------------------------------------------------------------- #


class PostNotFoundError(Exception):
    def __init__(self, post_id: str):
        super().__init__(f"Post with post_id={post_id} not found")


class Post:
    def __init__(
        self,
        post_id: str = None,
        author_google_id: str = None,
        title: str = None,
        content: str = None,
        longitude: float = None,
        latitude: float = None,
    ):
        self.post_id = post_id
        self.author_google_id = author_google_id
        self.title = title
        self.content = content
        self.longitude = longitude
        self.latitude = latitude

    @staticmethod
    def from_dict(source):
        return Post(
            source.get("post_id"),
            source.get("author_google_id"),
            source.get("title"),
            source.get("content"),
            source.get("longitude"),
            source.get("latitude"),
        )

    def to_dict(self) -> dict:
        return {
            "post_id": self.post_id,
            "author_google_id": self.author_google_id,
            "title": self.title,
            "content": self.content,
            "longitude": self.longitude,
            "latitude": self.latitude,
        }

    def __repr__(self):
        return f"""Post(
    post_id={self.post_id}
    author_google_id={self.author_google_id},
    title={self.title},
    content={self.content},
    longitude={self.longitude},
    latitude={self.latitude},
)
"""


class DataGateway(ABC):
    @abstractmethod
    def add_post(self, post_id: str, author_google_id: str, title: str, content: str, longitude: float, latitude: float) -> str:
        pass

    @abstractmethod
    def read_post(self, post_id: str) -> dict:
        pass

    @abstractmethod
    def get_posts_within_radius(self, longitude: float, latitude: float, radius: float):
        pass

    @abstractmethod
    def user_exists(self, google_id: str) -> bool:
        pass

# ---------------------------------------------------------------------------- #
#                                   Firestore                                  #
# ---------------------------------------------------------------------------- #


class FirestoreGateway(DataGateway):
    def __init__(self):
        self._db = firestore.Client()

    def add_post(
        self, author_google_id: str, title: str, content: str, longitude: float, latitude: float
    ):
        logger.debug(f"User with {author_google_id=} created post titled {title=}")
        doc_ref = self._db.collection("posts").document()
        post_id = doc_ref.id
        doc_ref.set(Post(post_id, author_google_id, title, content, longitude, latitude).to_dict())

        return post_id

    def read_post(self, post_id: str) -> dict:
        logger.debug(f"Reading post {post_id}")
        doc_ref = self._db.collection("posts").document(post_id)
        doc = doc_ref.get()

        if doc.exists:
            logger.debug("Post found")
            return doc.to_dict()

        raise PostNotFoundError(post_id)

    def get_posts_within_radius(self, longitude: float, latitude: float, radius: float):
        logger.debug(f"Getting posts within {radius} km of ({longitude=}, {latitude=})")
        post_ids = []

        # Convert radius from km to degrees (approximate)
        radius_degrees = radius / 111.12

        # Calculate the bounds of the square area
        min_longitude = longitude - radius_degrees
        max_longitude = longitude + radius_degrees
        min_latitude = latitude - radius_degrees
        max_latitude = latitude + radius_degrees

        # Query posts within the square area
        query = (
            self._db.collection("posts")
            .where("longitude", ">=", min_longitude)
            .where("longitude", "<=", max_longitude)
            .where("latitude", ">=", min_latitude)
            .where("latitude", "<=", max_latitude)
        )

        docs = query.stream()

        for doc in docs:
            post_ids.append(doc.id)

        return post_ids

    def user_exists(self, google_id: str) -> bool:
        doc_ref = self._db.collection("users").document(google_id)
        doc = doc_ref.get()
        return doc.exists