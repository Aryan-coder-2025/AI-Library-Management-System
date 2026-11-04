"""
Embedding provider service for semantic search and content-based recommendations.
Manages pretrained sentence-transformer model loading, vector serialization, and cosine similarity.
"""
from datetime import datetime
from typing import Callable, List, Optional, Union
import numpy as np

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Module-level model cache to avoid reloading weights on every request
_model_instance = None
_mock_encoder: Optional[Callable[[str], np.ndarray]] = None


class ModelUnavailableException(Exception):
    """Raised when the sentence-transformer model is not installed or fails to load."""
    pass


def set_mock_encoder(encoder: Optional[Callable[[str], np.ndarray]]) -> None:
    """Sets a mock encoder for testing, bypassing sentence-transformers downloads."""
    global _mock_encoder
    _mock_encoder = encoder


def reset_mock_encoder() -> None:
    """Resets the mock encoder back to None."""
    global _mock_encoder
    _mock_encoder = None


def is_model_available() -> bool:
    """Checks whether the embedding model can be loaded in the current runtime."""
    if _mock_encoder is not None:
        return True
    try:
        import sentence_transformers  # noqa: F401
        return True
    except (ImportError, Exception):
        return False


def get_embedding_model():
    """
    Lazily loads the SentenceTransformer model singleton.
    Raises ModelUnavailableException if sentence-transformers is missing or fails to load.
    """
    global _model_instance
    if _mock_encoder is not None:
        return None

    if _model_instance is not None:
        return _model_instance

    try:
        from sentence_transformers import SentenceTransformer
        _model_instance = SentenceTransformer(MODEL_NAME)
        return _model_instance
    except ImportError as e:
        raise ModelUnavailableException(
            f"Package 'sentence-transformers' is not installed: {str(e)}. "
            "Please install sentence-transformers and PyTorch to generate embeddings."
        ) from e
    except Exception as e:
        raise ModelUnavailableException(
            f"Failed to load embedding model '{MODEL_NAME}': {str(e)}. "
            "Please ensure weights are downloaded or network is available."
        ) from e


def build_book_document(
    title: str,
    author: str,
    category: str,
    description: Optional[str] = None,
) -> str:
    """
    Constructs a uniform document representation for book embedding generation.
    Incorporates title, author, category, and description systematically.
    """
    parts = [
        f"Title: {title.strip()}",
        f"Author: {author.strip()}",
        f"Category: {category.strip()}",
    ]
    if description and description.strip():
        parts.append(f"Description: {description.strip()}")
    return " | ".join(parts)


def encode_text(text: str) -> np.ndarray:
    """
    Generates a 1D float32 normalized embedding vector for the supplied text.
    Uses mock encoder if configured, else delegates to SentenceTransformer.
    """
    if _mock_encoder is not None:
        raw_vec = _mock_encoder(text)
        vec = np.asarray(raw_vec, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    model = get_embedding_model()
    # SentenceTransformer encode with normalize_embeddings=True for unit-length vectors
    embedding = model.encode(text, normalize_embeddings=True, convert_to_numpy=True)
    return np.asarray(embedding, dtype=np.float32)


def serialize_vector(vector: Union[List[float], np.ndarray]) -> bytes:
    """Serializes a 1D float32 vector to raw bytes for database LargeBinary storage."""
    arr = np.asarray(vector, dtype=np.float32)
    return arr.tobytes()


def deserialize_vector(raw_bytes: bytes) -> np.ndarray:
    """Deserializes raw bytes from database LargeBinary storage to a 1D float32 numpy array."""
    if not raw_bytes:
        raise ValueError("Cannot deserialize empty embedding bytes.")
    return np.frombuffer(raw_bytes, dtype=np.float32)


def compute_cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Computes cosine similarity between two 1D float vectors.
    Returns a float in range [-1.0, 1.0].
    """
    if vec_a.shape != vec_b.shape:
        raise ValueError(
            f"Vector dimension mismatch for cosine similarity: {vec_a.shape} vs {vec_b.shape}"
        )
    norm_a = float(np.linalg.norm(vec_a))
    norm_b = float(np.linalg.norm(vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    dot = float(np.dot(vec_a, vec_b))
    similarity = dot / (norm_a * norm_b)
    # Clamp to avoid floating point precision edge cases slightly outside [-1.0, 1.0]
    return max(-1.0, min(1.0, similarity))
