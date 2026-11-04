"""Deterministic orchestration and namespace seed derivation for synthetic data generation.

Implements HMAC-SHA256 namespace-derived pseudo-random generation to guarantee that
adding or modifying one generator has zero ripple effect on other generator streams.
"""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import hmac
import random
from typing import Any, Dict, Optional

# Default deterministic generation coordinates
DEFAULT_BASE_SEED: int = 20261031
DEFAULT_AS_OF: datetime = datetime(2026, 10, 31, 23, 59, 59)


def derive_namespace_seed(base_seed: int, namespace: str) -> int:
    """
    Derives an independent, deterministic 64-bit seed for a specific generator namespace
    using HMAC-SHA256 keyed on the base seed.
    """
    key = str(base_seed).encode("utf-8")
    mac = hmac.new(key, namespace.encode("utf-8"), hashlib.sha256).hexdigest()
    # Use first 16 hex characters (64 bits) as integer seed
    return int(mac[:16], 16)


def get_namespace_rng(base_seed: int, namespace: str) -> random.Random:
    """Returns an isolated, independent Python random.Random instance for the namespace."""
    seed_val = derive_namespace_seed(base_seed, namespace)
    return random.Random(seed_val)


@dataclass
class SeederConfig:
    """Configuration coordinates for deterministic synthetic generation."""
    base_seed: int = DEFAULT_BASE_SEED
    as_of: datetime = DEFAULT_AS_OF
    enable_embeddings: bool = True
    embedding_batch_size: int = 64
    bcrypt_rounds: int = 8


def generate_all_datasets(config: Optional[SeederConfig] = None) -> Dict[str, Any]:
    """
    Generates all in-memory datasets deterministically across all namespaces.
    Does NOT write to or create any database file.
    """
    cfg = config or SeederConfig()
    from app.seed_data.users_generator import generate_users
    from app.seed_data.spaces_generator import generate_spaces
    from app.seed_data.catalogue_generator import generate_catalogue
    from app.seed_data.circulation_generator import generate_circulation
    from app.seed_data.reservation_generator import generate_reservations
    from app.seed_data.telemetry_generator import generate_telemetry

    users = generate_users(cfg, bcrypt_rounds=cfg.bcrypt_rounds)
    spaces_dict = generate_spaces(cfg)
    zones = spaces_dict["zones"]
    seats = spaces_dict["seats"]
    rooms = spaces_dict["rooms"]

    catalogue_dict = generate_catalogue(cfg)
    books = catalogue_dict["books"]
    copies = catalogue_dict["copies"]

    loans = generate_circulation(cfg, users, books, copies)
    reservations = generate_reservations(cfg, users, seats, rooms)
    telemetry_dict = generate_telemetry(cfg, users, zones, copies)

    return {
        "users": users,
        "zones": zones,
        "seats": seats,
        "rooms": rooms,
        "books": books,
        "copies": copies,
        "loans": loans,
        "reservations": reservations,
        "occupancy_observations": telemetry_dict["occupancy_observations"],
        "search_events": telemetry_dict["search_events"],
        "inventory_events": telemetry_dict["inventory_events"],
    }
