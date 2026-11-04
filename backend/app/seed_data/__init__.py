"""Synthetic data generation and seeding package for AI Library Management System."""
from app.seed_data.generator import SeederConfig, generate_all_datasets
from app.seed_data.safety import (
    CANONICAL_BACKEND_DIR,
    CANONICAL_TARGET_DB,
    CANONICAL_STAGING_DB,
    CANONICAL_LOCK_FILE,
    DemoDatabaseLock,
    validate_path_safety,
    safe_wal_shutdown,
    publish_staging_database,
)
from app.seed_data.seeder import populate_staging_database

__all__ = [
    "SeederConfig",
    "generate_all_datasets",
    "CANONICAL_BACKEND_DIR",
    "CANONICAL_TARGET_DB",
    "CANONICAL_STAGING_DB",
    "CANONICAL_LOCK_FILE",
    "DemoDatabaseLock",
    "validate_path_safety",
    "safe_wal_shutdown",
    "publish_staging_database",
    "populate_staging_database",
]
