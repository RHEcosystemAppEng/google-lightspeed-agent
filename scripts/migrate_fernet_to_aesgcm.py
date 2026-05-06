#!/usr/bin/env python3
"""Batch migration: re-encrypt DCR client secrets from Fernet to AES-256-GCM.

This script decrypts all existing Fernet-encrypted secrets in the dcr_clients
table using the current Fernet key (DCR_ENCRYPTION_KEY) and re-encrypts them
with a new AES-256-GCM key (DCR_ENCRYPTION_KEY_NEW).

After running this script, update DCR_ENCRYPTION_KEY to the new key value
and deploy the updated application code.

Prerequisites:
    export DATABASE_URL="postgresql+asyncpg://user:pass@host/db"
    export DCR_ENCRYPTION_KEY="<current-fernet-key>"
    export DCR_ENCRYPTION_KEY_NEW="<new-base64url-encoded-32-byte-key>"

Usage:
    # Preview what would be migrated (no writes)
    python scripts/migrate_fernet_to_aesgcm.py --dry-run

    # Run the migration
    python scripts/migrate_fernet_to_aesgcm.py
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import os
import sys

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lightspeed_agent.db.base import Base
from lightspeed_agent.db.models import DCRClientModel


# ---------------------------------------------------------------------------
# Cipher setup
# ---------------------------------------------------------------------------


def get_old_fernet() -> Fernet:
    """Create a Fernet cipher from the current DCR_ENCRYPTION_KEY env var."""
    key = os.environ.get("DCR_ENCRYPTION_KEY", "")
    if not key:
        print(
            "ERROR: DCR_ENCRYPTION_KEY is required.\n"
            "Set it to the current Fernet key used to encrypt secrets.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        return Fernet(key.encode())
    except Exception as e:
        print(f"ERROR: Invalid DCR_ENCRYPTION_KEY (not a valid Fernet key): {e}", file=sys.stderr)
        sys.exit(1)


def get_new_aesgcm() -> AESGCM:
    """Create an AES-256-GCM cipher from DCR_ENCRYPTION_KEY_NEW env var."""
    key = os.environ.get("DCR_ENCRYPTION_KEY_NEW", "")
    if not key:
        print(
            "ERROR: DCR_ENCRYPTION_KEY_NEW is required.\n"
            "Generate one with:\n"
            '  python -c "import base64, os; '
            "print(base64.urlsafe_b64encode(os.urandom(32)).decode())\"",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        key_bytes = base64.urlsafe_b64decode(key)
        if len(key_bytes) != 32:
            raise ValueError(f"Key must be 32 bytes (got {len(key_bytes)})")
        return AESGCM(key_bytes)
    except Exception as e:
        print(f"ERROR: Invalid DCR_ENCRYPTION_KEY_NEW: {e}", file=sys.stderr)
        sys.exit(1)


def decrypt_fernet(fernet: Fernet, encrypted: str) -> str | None:
    """Decrypt a Fernet-encrypted value."""
    try:
        return fernet.decrypt(encrypted.encode()).decode()
    except InvalidToken:
        return None


def encrypt_aesgcm(aesgcm: AESGCM, plaintext: str) -> str:
    """Encrypt a value with AES-256-GCM."""
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def get_database_url() -> str:
    """Get DATABASE_URL from environment."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print(
            "ERROR: DATABASE_URL is required.\n"
            "Example: export DATABASE_URL='postgresql+asyncpg://user:pass@localhost:5432/dbname'",
            file=sys.stderr,
        )
        sys.exit(1)
    return url


async def create_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Create an async engine and session factory."""
    engine = create_async_engine(database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


async def migrate(dry_run: bool = False) -> None:
    """Migrate all Fernet-encrypted secrets to AES-256-GCM."""
    fernet = get_old_fernet()
    aesgcm = get_new_aesgcm()

    database_url = get_database_url()
    factory = await create_session_factory(database_url)

    migrated = 0
    failed = 0
    skipped = 0

    async with factory() as session:
        result = await session.execute(select(DCRClientModel))
        models = result.scalars().all()

        if not models:
            print("No DCR client entries found. Nothing to migrate.")
            return

        print(f"Found {len(models)} DCR client entries to migrate.\n")

        for model in models:
            client_id = model.client_id
            order_id = model.order_id

            # Migrate client_secret_encrypted
            if not model.client_secret_encrypted:
                print(f"  SKIP: {client_id} (order={order_id}) — no encrypted secret")
                skipped += 1
                continue

            plaintext = decrypt_fernet(fernet, model.client_secret_encrypted)
            if plaintext is None:
                print(
                    f"  FAIL: {client_id} (order={order_id}) — "
                    "could not decrypt client_secret with current Fernet key",
                    file=sys.stderr,
                )
                failed += 1
                continue

            new_encrypted = encrypt_aesgcm(aesgcm, plaintext)

            # Migrate registration_access_token_encrypted if present
            new_token_encrypted = None
            if model.registration_access_token_encrypted:
                token_plaintext = decrypt_fernet(
                    fernet, model.registration_access_token_encrypted
                )
                if token_plaintext is None:
                    print(
                        f"  FAIL: {client_id} (order={order_id}) — "
                        "could not decrypt registration_access_token with current Fernet key",
                        file=sys.stderr,
                    )
                    failed += 1
                    continue
                new_token_encrypted = encrypt_aesgcm(aesgcm, token_plaintext)

            if dry_run:
                token_status = (
                    " + registration_access_token"
                    if model.registration_access_token_encrypted
                    else ""
                )
                print(
                    f"  DRY RUN: would migrate {client_id} "
                    f"(order={order_id}){token_status}"
                )
                migrated += 1
                continue

            model.client_secret_encrypted = new_encrypted
            if new_token_encrypted is not None:
                model.registration_access_token_encrypted = new_token_encrypted

            session.add(model)
            migrated += 1
            print(f"  OK: migrated {client_id} (order={order_id})")

        if not dry_run:
            await session.commit()

    prefix = "DRY RUN " if dry_run else ""
    print(f"\n{prefix}Summary: {migrated} migrated, {skipped} skipped, {failed} failed")
    if failed > 0:
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate DCR client secrets from Fernet to AES-256-GCM encryption.",
        epilog=(
            "Environment variables:\n"
            "  DATABASE_URL            Database connection string (required)\n"
            "  DCR_ENCRYPTION_KEY      Current Fernet encryption key (required)\n"
            "  DCR_ENCRYPTION_KEY_NEW  New AES-256-GCM encryption key (required)\n"
            "\n"
            "After migration, update DCR_ENCRYPTION_KEY to the value of\n"
            "DCR_ENCRYPTION_KEY_NEW and deploy the updated application.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without writing changes",
    )

    args = parser.parse_args()
    asyncio.run(migrate(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
