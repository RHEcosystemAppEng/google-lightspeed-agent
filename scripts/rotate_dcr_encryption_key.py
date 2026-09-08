"""DCR encryption key rotation script.

Re-encrypts all DCR OAuth client secrets from old Fernet key to new key.
"""
import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lightspeed_agent.db.models import DCRClientModel

logger = logging.getLogger(__name__)


class RotationError(Exception):
    """Raised when rotation fails pre-flight checks or during execution."""
    pass


@dataclass
class RotationResult:
    """Result of encryption key rotation."""
    success: bool
    clients_rotated: int
    dry_run: bool
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


class EncryptionKeyRotator:
    """Re-encrypts DCR client secrets from old Fernet key to new key."""

    def __init__(self, old_key: str, new_key: str, database_url: str):
        """Initialize rotator with old key, new key, and database URL.

        Args:
            old_key: Current Fernet encryption key (44-char base64)
            new_key: New Fernet encryption key (44-char base64)
            database_url: PostgreSQL or SQLite connection string
        """
        self.old_key = old_key
        self.new_key = new_key
        self.database_url = database_url

        try:
            self.old_fernet = Fernet(old_key.encode())
            self.new_fernet = Fernet(new_key.encode())
        except Exception as e:
            raise RotationError(f"Invalid Fernet key: {e}") from e

        self.engine = create_async_engine(database_url, echo=False)
        self.async_session = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def validate_keys(self) -> None:
        """Validate that keys are different and valid.

        Raises:
            RotationError: If keys are identical or invalid
        """
        if self.old_key == self.new_key:
            raise RotationError("Keys must be different (no-op rotation not allowed)")

    async def validate_database(self) -> None:
        """Validate database connection.

        Raises:
            RotationError: If database connection fails
        """
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as e:
            raise RotationError(f"Database connection failed: {e}") from e

    async def cleanup(self) -> None:
        """Dispose database engine."""
        await self.engine.dispose()

    def reencrypt_secret(self, encrypted_secret: str) -> str:
        """Re-encrypt a secret from old key to new key.

        Args:
            encrypted_secret: Base64-encoded ciphertext encrypted with old key

        Returns:
            Base64-encoded ciphertext encrypted with new key

        Raises:
            RotationError: If decryption with old key fails
        """
        try:
            plaintext = bytearray(self.old_fernet.decrypt(encrypted_secret.encode()))
            reencrypted = self.new_fernet.encrypt(bytes(plaintext))

            for i in range(len(plaintext)):
                plaintext[i] = 0

            return reencrypted.decode()

        except InvalidToken as e:
            raise RotationError(f"Failed to decrypt secret with old key: {e}") from e

    async def rotate(self, dry_run: bool = False) -> RotationResult:
        """Fetch all DCR clients and re-encrypt their secrets.

        Args:
            dry_run: If True, test decrypt/re-encrypt without database writes

        Returns:
            RotationResult with success status and counts
        """
        async with self.async_session() as session:
            result = await session.execute(select(DCRClientModel))
            clients = result.scalars().all()

            if len(clients) == 0:
                logger.warning("No DCR clients found - nothing to rotate")
                return RotationResult(success=True, clients_rotated=0, dry_run=dry_run)

            if dry_run:
                logger.info("Dry-run: testing decrypt/re-encrypt on %d clients", len(clients))
                errors = []
                for i, client in enumerate(clients, 1):
                    try:
                        self.reencrypt_secret(client.client_secret_encrypted)
                        if client.registration_access_token_encrypted:
                            self.reencrypt_secret(client.registration_access_token_encrypted)
                        logger.debug("Testing client %s (%d/%d)", client.client_id, i, len(clients))
                    except RotationError as e:
                        errors.append(f"{client.client_id}: {e}")

                return RotationResult(
                    success=len(errors) == 0,
                    clients_rotated=len(clients),
                    dry_run=True,
                    errors=errors
                )
            else:
                logger.info("Production mode: rotating %d clients", len(clients))
                for client in clients:
                    client.client_secret_encrypted = self.reencrypt_secret(
                        client.client_secret_encrypted
                    )
                    if client.registration_access_token_encrypted:
                        client.registration_access_token_encrypted = self.reencrypt_secret(
                            client.registration_access_token_encrypted
                        )
                await session.commit()

                return RotationResult(
                    success=True,
                    clients_rotated=len(clients),
                    dry_run=False
                )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Re-encrypt DCR OAuth client secrets from old Fernet key to new key",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
SECURITY: Use environment variables instead of CLI arguments for keys and
database URLs. CLI arguments are visible in process listings (ps aux),
shell history, and system audit logs.

Examples:
  # Set secrets via environment variables (recommended)
  export DCR_OLD_KEY="..."
  export DCR_NEW_KEY="..."
  export DATABASE_URL="postgresql+asyncpg://..."

  # Dry-run mode (test only, no database changes)
  python rotate_dcr_encryption_key.py --dry-run

  # Production mode (modifies database)
  python rotate_dcr_encryption_key.py
        """
    )

    parser.add_argument(
        "--old-key",
        type=str,
        default=os.getenv("DCR_OLD_KEY"),
        help="Current Fernet encryption key (44-char base64, or set DCR_OLD_KEY env)"
    )
    parser.add_argument(
        "--new-key",
        type=str,
        default=os.getenv("DCR_NEW_KEY"),
        help="New Fernet encryption key (44-char base64, or set DCR_NEW_KEY env)"
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=os.getenv("DATABASE_URL"),
        help="PostgreSQL connection string (or set DATABASE_URL env)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test mode: no database changes (default: False)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Detailed progress logging (default: False)"
    )

    args = parser.parse_args()

    if not args.old_key:
        parser.error("--old-key is required (or set DCR_OLD_KEY environment variable)")
    if not args.new_key:
        parser.error("--new-key is required (or set DCR_NEW_KEY environment variable)")
    if not args.database_url:
        parser.error("--database-url is required (or set DATABASE_URL environment variable)")

    return args


async def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0=success, 1=pre-flight failure, 2=rotation failure)
    """
    args = parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s"
    )

    mode = "PRODUCTION MODE" if not args.dry_run else "DRY-RUN MODE"
    logger.info(f"Starting DCR encryption key rotation ({mode})")

    try:
        rotator = EncryptionKeyRotator(
            old_key=args.old_key,
            new_key=args.new_key,
            database_url=args.database_url
        )

        try:
            logger.info("Pre-flight checks: validating keys")
            await rotator.validate_keys()

            logger.info("Pre-flight checks: validating database connection")
            await rotator.validate_database()

            result = await rotator.rotate(dry_run=args.dry_run)

            if result.success:
                if args.dry_run:
                    logger.info(
                        f"Dry-run complete: all {result.clients_rotated} records can be rotated"
                    )
                else:
                    logger.info(
                        f"Rotation complete: {result.clients_rotated} clients rotated successfully"
                    )
                return 0
            else:
                errors = result.errors or []
                logger.error(f"Rotation failed with {len(errors)} errors:")
                for error in errors:
                    logger.error(f"  {error}")
                return 2

        finally:
            await rotator.cleanup()

    except RotationError as e:
        logger.error(f"Pre-flight check failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
