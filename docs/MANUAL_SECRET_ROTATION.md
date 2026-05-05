# Manual Secret Rotation

## INTERNAL ATTESTATION

**Finding:** Credential provider APIs for automated secret rotation are not supported.

**Affected Secrets:**

**Tier 1 (OAuth Secrets) - Blocked by missing credential provider APIs:**
- `RED_HAT_SSO_CLIENT_SECRET` - Red Hat SSO OAuth client secret
- `GMA_CLIENT_SECRET` - Google Marketplace Agent (GMA) client secret

**Tiers 2 & 3 - Require human intervention (service restart/migration):**
- `DATABASE_URL` - Cloud SQL database credentials, requires coordinated service restart
- `DCR_ENCRYPTION_KEY` - Fernet encryption key requiring re-encryption migration

**Current Mitigation:** Manual rotation procedures documented in this file, executed annually by operations team.

**Recommended Action (CIAM team):** Investigate and build API support for:
1. Red Hat SSO Client API - OAuth client secret regeneration endpoint
2. Google Marketplace Agent API - Client secret regeneration endpoint

**Compensating Control:** Annual manual rotation procedures (detailed below) provide security equivalent to automated rotation at longer intervals.

**Review Date:** 2026-05-04

---

## Overview

This document provides manual rotation procedures for all secrets in the Red Hat Lightspeed Agent for Google Cloud that cannot be rotated automatically.

**Why Manual Rotation:**
- Required credential provider APIs do not exist (Red Hat SSO, GMA)
- Some secrets require coordinated service restarts or database migrations

**Rotation Policy:**
- **Frequency:** Annual rotation for all tiers
- **Rationale:** Manual processes have operational overhead; annual cadence balances security with operational capacity

**Three Tiers of Secrets:**

| Tier | Complexity | Secrets | Downtime |
|------|-----------|---------|----------|
| 1 | Low | OAuth client secrets (SSO, GMA) | None (auto-pickup) |
| 2 | Medium | Database credentials | 2-5 minutes (restart) |
| 3 | High | DCR encryption key | Marketplace only (migration required) |

**Emergency Rotation:** See Appendix B for expedited procedures.

---

## Prerequisites

### Access Requirements

**All Tiers (for Secret Manager updates and service restarts):**
- Google Cloud Run project access
- Gemini Enterprise Plus license
  - Provides necessary GCP admin roles: Secret Manager, Cloud SQL, Cloud Run

**Tier 1 Specific:**
- **`RED_HAT_SSO_CLIENT_SECRET`:** `ai5-marketplace` GitLab group membership
  - Required to create/update SSO clients and receive credentials
- **`GMA_CLIENT_SECRET`:** No access required (credentials provided by CIAM team)

**Tier 3 Specific:**
- **`DCR_ENCRYPTION_KEY`:** Database access via `DATABASE_URL` with password (for migration script)

### Tooling Requirements

**All Tiers:**
- `gcloud` CLI authenticated and configured

**Tier 2:**
- `jq` (for JSON parsing in log verification)

**Tier 3:**
- Python 3.12+ with project dependencies installed
- `scripts/rotate_dcr_encryption_key.py` from repository

### Coordination Requirements

**Tier 1:**
- No coordination needed (zero downtime)

**Tier 2:**
- Maintenance window approval (2-5 minute downtime)
- Stakeholder notification (service restart)

**Tier 3:**
- Maintenance window (1 hour including contingency)
- Database backup recommended

---

## Tier 1: OAuth Client Secrets

**Characteristics:**
- Zero service downtime (Cloud Run auto-picks up new secret versions)
- CIAM team coordination required (1-2 business days)
- Low technical complexity (Secret Manager version update)

---

### 1.1 RED_HAT_SSO_CLIENT_SECRET

**Duration:** 1-2 business days (CIAM processing time)

**Overview:** Rotate the Red Hat SSO OAuth client secret used for JWT validation. This secret authenticates the Lightspeed Agent with Red Hat SSO to validate user tokens.

#### Step 1: Request New Secret from CIAM

Follow the CIAM self-service client configuration management process:

**Documentation:** https://source.redhat.com/departments/strategy_and_operations/it/ciam/docs/draft_self_service_client_configuration_management~1

**Process:**

1. Connect to Red Hat VPN
2. Navigate to the `ai5-marketplace` GitLab namespace: https://gitlab.cee.redhat.com/ai5-marketplace
3. Navigate to the `client-enablements` repository fork
4. Create a merge request with client Service Account configuration changes
5. Submit for CIAM team review
6. Wait for approval and merge
7. Receive two emails from CIAM:
   - **Email 1:** Client ID and password-protected link
   - **Email 2:** Password to decrypt the link
8. Access the link and extract new client secret value

#### Step 2: Update Secret Manager

Add a new version of the secret in Google Cloud Secret Manager. Cloud Run services will automatically use the latest ENABLED version.

```bash
# Set project
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"

# Add new secret version (paste secret value when prompted)
echo -n "<paste-new-secret-value-here>" | gcloud secrets versions add redhat-sso-client-secret \
  --data-file=- \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Verify new version created
gcloud secrets versions list redhat-sso-client-secret \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --limit=3
```

**Expected Output:**
```
NAME                      STATE    CREATED              DESTROYED
4                         ENABLED  2026-05-04T12:00:00  -
3                         ENABLED  2025-05-04T12:00:00  -
2                         ENABLED  2024-05-04T12:00:00  -
```

Version 4 is the new secret (latest).

#### Step 3: Verification

Cloud Run services automatically pick up new secret versions within minutes. Verify authentication works with the new secret.

**Obtain a test JWT token:**

```bash
# Install OCM CLI (if not already installed)
# https://console.redhat.com/openshift/token

# Authenticate
ocm login --use-auth-code

# Get JWT token
TOKEN=$(ocm token)
```

**Test authentication:**

```bash
# Get agent service URL
AGENT_URL=$(gcloud run services describe lightspeed-agent \
  --region=us-central1 \
  --format='value(status.url)' \
  --project="${GOOGLE_CLOUD_PROJECT}")

# Test authentication (should return agent card JSON)
curl -H "Authorization: Bearer $TOKEN" \
  "${AGENT_URL}/.well-known/agent.json"
```

**Expected Output:**
```json
{
  "name": "Red Hat Lightspeed for Google Cloud",
  "description": "Access Red Hat Insights...",
  ...
}
```

**If authentication fails**, the new secret is invalid. Proceed to rollback (Step 4).

#### Step 4: Rollback (if needed)

If verification fails, disable the new secret version to restore the previous version.

```bash
# List versions to identify the new version number
gcloud secrets versions list redhat-sso-client-secret \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Disable new version (replace <new-version-number> with version from Step 2)
gcloud secrets versions disable <new-version-number> \
  --secret=redhat-sso-client-secret \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Verify rollback (latest ENABLED version should be previous)
gcloud secrets versions list redhat-sso-client-secret \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --limit=3
```

**Expected Output:**
```
NAME                      STATE     CREATED              DESTROYED
4                         DISABLED  2026-05-04T12:00:00  -
3                         ENABLED   2025-05-04T12:00:00  -
```

Cloud Run will automatically use version 3 (previous secret). Re-run verification (Step 3) to confirm rollback succeeded.

**Investigate why the new secret failed** before attempting rotation again. Common causes:
- Wrong secret value copied (typo)
- CIAM provided staging credentials instead of production
- Client configuration not yet propagated to production SSO

---

### 1.2 GMA_CLIENT_SECRET

**Duration:** 1-5 business days (CIAM contact response time)

**Overview:** Rotate the Google Marketplace Agent (GMA) OAuth client secret used for Dynamic Client Registration (DCR). This secret authenticates the Marketplace Handler with the GMA API to create tenant-specific OAuth clients.

#### Step 1: Request New Secret from CIAM Contacts

Unlike Red Hat SSO (which has a self-service process), GMA client secrets must be requested directly from CIAM team contacts.

**Contact Information:**
- **Primary Contact:** [TBD - add contact name/email]
- **Secondary Contact:** [TBD - add contact name/email]
- **Escalation Path:** [TBD - add escalation contact for urgent requests]

**Request Template:**

```
Subject: GMA Client Annual Secret Rotation Request - Red Hat Lightspeed Agent

Hi [CIAM Team],

We need to rotate the GMA client secret for the Red Hat Lightspeed Agent for Google Cloud.

**Details:**
- Service: Red Hat Lightspeed Agent for Google Cloud
- Current client_id: <redacted - available in Secret Manager: gma-client-id>
- Environment: Production

Please generate a new client secret and provide it via a secure channel.

Thank you,
[Your Name]
[Your Team]
```

#### Step 2: Update Secret Manager

```bash
# Set project
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"

# Add new secret version
echo -n "<paste-new-gma-secret-here>" | gcloud secrets versions add gma-client-secret \
  --data-file=- \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Verify new version created
gcloud secrets versions list gma-client-secret \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --limit=3
```

**Expected Output:**
```
NAME                      STATE    CREATED              DESTROYED
3                         ENABLED  2026-05-04T14:00:00  -
2                         ENABLED  2025-05-04T14:00:00  -
1                         ENABLED  2024-05-04T14:00:00  -
```

#### Step 3: Verification

<TBD>

**If verification fails**, proceed to rollback (Step 4).

#### Step 4: Rollback (if needed)

```bash
# List versions to identify new version number
gcloud secrets versions list gma-client-secret \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Disable new version
gcloud secrets versions disable <new-version-number> \
  --secret=gma-client-secret \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Verify rollback
gcloud secrets versions list gma-client-secret \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --limit=3
```

Cloud Run will automatically use the previous ENABLED version.

**Investigate failure** before retrying:
- Verify secret value is correct (no copy/paste errors)
- Confirm CIAM provided production credentials (not staging)
- Check GMA API endpoint is accessible from Cloud Run
- Review Marketplace Handler logs for authentication errors

---

## Tier 2: Database Credentials

**Characteristics:**
- Service restart required (2-5 minute downtime)
- Maintenance window coordination needed
- Medium technical complexity (Cloud SQL + Secret Manager + service restarts)

**Duration:** 30-60 minutes (includes maintenance window)

**Overview:** Rotate PostgreSQL database password used by both Lightspeed Agent and Marketplace Handler services. Requires coordinated updates to Cloud SQL, Secret Manager, and service restarts.

---

### Step 1: Schedule Maintenance Window

**Coordinate service downtime:**

- **Affected Services:** Both `lightspeed-agent` and `marketplace-handler` Cloud Run services
- **Expected Downtime:** 2-5 minutes during service restart
- **Impact:**
  - Agent API requests will fail during restart (users see 503 errors)
  - Marketplace provisioning events buffered by Pub/Sub (processed after restart)

---

### Step 2: Generate New Password

Use a cryptographically secure random password generator:

```bash
# Generate 32-character random password
NEW_DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)

# Display password (save temporarily in password manager)
echo "Generated password: ${NEW_DB_PASSWORD}"
echo "Length: ${#NEW_DB_PASSWORD} characters"
```

**Expected Output:**
```
Generated password: Kj7mN9pQ2rT4vW6xZ8aB1cD3eF5gH0iJ
Length: 32 characters
```

---

### Step 3: Update Cloud SQL Password

Update the database user password in Cloud SQL:

```bash
# Set variables (replace with your actual values)
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
export DB_INSTANCE_NAME="your-db-instance-name"
export DB_USERNAME="your-db-username"

# Update Cloud SQL password
gcloud sql users set-password "${DB_USERNAME}" \
  --instance="${DB_INSTANCE_NAME}" \
  --password="${NEW_DB_PASSWORD}" \
  --project="${GOOGLE_CLOUD_PROJECT}"
```

---

### Step 4: Update Secret Manager

Both services use the same database. Update the `database-url` secret with the new password:

```bash
# Construct new connection string
# Format: postgresql+asyncpg://USERNAME:PASSWORD@/DATABASE?host=/cloudsql/PROJECT:REGION:INSTANCE
NEW_DATABASE_URL="postgresql+asyncpg://${DB_USERNAME}:${NEW_DB_PASSWORD}@/lightspeed_agent?host=/cloudsql/${GOOGLE_CLOUD_PROJECT}:us-central1:${DB_INSTANCE_NAME}"

# Add new secret version
echo -n "${NEW_DATABASE_URL}" | gcloud secrets versions add database-url \
  --data-file=- \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Verify new version created
gcloud secrets versions list database-url \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --limit=3
```

---

### Step 5: Restart Services

Force Cloud Run services to pick up the new secret version. **This triggers downtime.**

```bash
# Restart agent service
echo "Restarting lightspeed-agent..."
gcloud run services update lightspeed-agent \
  --region=us-central1 \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Restart marketplace handler
echo "Restarting marketplace-handler..."
gcloud run services update marketplace-handler \
  --region=us-central1 \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Monitor service health
echo "Waiting for services to become ready..."
sleep 10

# Check agent service status
gcloud run services describe lightspeed-agent \
  --region=us-central1 \
  --format='value(status.conditions[0].status)' \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Check marketplace handler status
gcloud run services describe marketplace-handler \
  --region=us-central1 \
  --format='value(status.conditions[0].status)' \
  --project="${GOOGLE_CLOUD_PROJECT}"
```

**Expected Output (for both services):**
```
True
```

This indicates services are ready and healthy.

---

### Step 6: Verification

Test that both services can connect to the database with the new password:

**Check service logs for database errors:**

```bash
# Check agent logs (last 5 minutes)
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=lightspeed-agent AND \
  severity>=ERROR AND \
  timestamp>=\"$(date -u -d '5 minutes ago' --iso-8601=seconds)\"" \
  --limit=20 \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --format=json | jq '.[].jsonPayload.message'

# Check marketplace handler logs
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=marketplace-handler AND \
  severity>=ERROR AND \
  timestamp>=\"$(date -u -d '5 minutes ago' --iso-8601=seconds)\"" \
  --limit=20 \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --format=json | jq '.[].jsonPayload.message'
```

**Expected:** No database connection errors in recent logs.

**If database connection errors appear**, proceed to rollback (Step 7).

---

### Step 7: Rollback (if needed)

If services cannot connect to the database, roll back to the previous password:

```bash
# Step 1: Disable new Secret Manager version
gcloud secrets versions list database-url \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Disable new version (replace <new-version> with number from Step 4)
gcloud secrets versions disable <new-version> \
  --secret=database-url \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Step 2: Restore old password in Cloud SQL
# (You must retrieve old password from Secret Manager first)
OLD_DATABASE_URL=$(gcloud secrets versions access <previous-version> \
  --secret=database-url \
  --project="${GOOGLE_CLOUD_PROJECT}")

# Extract password from connection string (between : and @)
OLD_DB_PASSWORD=$(echo "${OLD_DATABASE_URL}" | sed -n 's/.*:\([^@]*\)@.*/\1/p')

# Restore old password in Cloud SQL
gcloud sql users set-password "${DB_USERNAME}" \
  --instance="${DB_INSTANCE_NAME}" \
  --password="${OLD_DB_PASSWORD}" \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Step 3: Restart services to pick up rollback
gcloud run services update lightspeed-agent \
  --region=us-central1 \
  --project="${GOOGLE_CLOUD_PROJECT}"

gcloud run services update marketplace-handler \
  --region=us-central1 \
  --project="${GOOGLE_CLOUD_PROJECT}"

```

**Re-run verification (Step 6)** to confirm rollback succeeded.

**Investigate failure** before retrying:
- Verify password in Secret Manager matches Cloud SQL
- Check database connection string format (typos in hostname, database name)
- Verify Cloud SQL instance is running and accessible
- Review service logs for specific connection errors

---

## Tier 3: DCR Encryption Key

**Characteristics:**
- Marketplace provisioning downtime during migration (30 minutes)
- Agent API remains fully available (does not use `DCR_ENCRYPTION_KEY`)
- Database migration required (re-encrypt all DCR client secrets)
- Database backup recommended as last-resort safety net

**Duration:** 30 minutes (includes backup verification, migration, and verification)

**Overview:** Rotate the Fernet encryption key used to encrypt DCR OAuth client secrets at rest. Requires re-encrypting all secrets in the database using a migration script.

**Risk:** The migration script uses transactional updates, so a failure mid-migration leaves the database unchanged. If verification fails after migration, the migration can be reversed by re-running the script with keys swapped. If the new key is lost after migration commits, a database backup is the only recovery path.

---

### Step 1: Schedule Maintenance Window

**Requirements:**

- **Downtime:** Marketplace provisioning unavailable during migration (30 minutes)
  - Agent API remains fully available (does not use `DCR_ENCRYPTION_KEY`)
- **Backup:** Database backup verified within last 24 hours (recommended)
- **Window Size:** Minimum 1 hour (migration + contingency + rollback if needed)

---

### Step 2: Verify Database Backup

Verify a recent backup exists as a last-resort safety net in case of key loss.

```bash
# Set variables
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
export DB_INSTANCE_NAME="your-db-instance-name"

# List recent backups
gcloud sql backups list \
  --instance="${DB_INSTANCE_NAME}" \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --limit=5

# Check most recent backup timestamp
LATEST_BACKUP=$(gcloud sql backups list \
  --instance="${DB_INSTANCE_NAME}" \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --limit=1 \
  --format='value(id)')

echo "Latest backup ID: ${LATEST_BACKUP}"
```

**Expected Output:**
```
ID                    WINDOW_START_TIME            TYPE       STATUS
1620000000000         2026-05-04T06:00:00.000+00:00 AUTOMATED  SUCCESSFUL
```

**If no backup within 24 hours**, trigger manual backup:

```bash
# Create manual backup
gcloud sql backups create \
  --instance="${DB_INSTANCE_NAME}" \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Wait for backup to complete (2-10 minutes depending on database size)
echo "Waiting for backup to complete..."
sleep 60

# Verify backup created
gcloud sql backups list \
  --instance="${DB_INSTANCE_NAME}" \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --limit=1
```

If backup fails, consider whether to proceed without this safety net.

---

### Step 3: Generate New Fernet Key

```bash
# Generate new encryption key (44-character base64-encoded Fernet key)
NEW_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

echo "New encryption key (save in password manager): ${NEW_ENCRYPTION_KEY}"
echo "Length: ${#NEW_ENCRYPTION_KEY} characters (should be 44)"
```

**Expected Output:**
```
New encryption key: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2=
Length: 44 characters
```

---

### Step 4: Retrieve Old Key from Secret Manager

```bash
# Get current encryption key
OLD_ENCRYPTION_KEY=$(gcloud secrets versions access latest \
  --secret=dcr-encryption-key \
  --project="${GOOGLE_CLOUD_PROJECT}")

echo "Old key retrieved"
echo "Length: ${#OLD_ENCRYPTION_KEY} characters (should be 44)"
```

**Verify both keys are 44 characters** and different:

```bash
# Verify keys are different
if [ "${OLD_ENCRYPTION_KEY}" == "${NEW_ENCRYPTION_KEY}" ]; then
  echo "ERROR: Keys are identical! Generate a new key."
  exit 1
else
  echo "✓ Keys are different"
fi

# Verify lengths
if [ ${#OLD_ENCRYPTION_KEY} -ne 44 ] || [ ${#NEW_ENCRYPTION_KEY} -ne 44 ]; then
  echo "ERROR: Invalid key length!"
  exit 1
else
  echo "✓ Keys are valid Fernet keys"
fi
```

---

### Step 5: Run Migration Script (Dry-Run)

**CRITICAL:** Always run dry-run first to validate keys work before touching the database.

```bash
# Navigate to repository
cd /path/to/google-lightspeed-agent

# Activate virtual environment
source .venv/bin/activate

# Get database URL
DATABASE_URL=$(gcloud secrets versions access latest \
  --secret=database-url \
  --project="${GOOGLE_CLOUD_PROJECT}")

# Run dry-run migration
python scripts/rotate_dcr_encryption_key.py \
  --old-key="${OLD_ENCRYPTION_KEY}" \
  --new-key="${NEW_ENCRYPTION_KEY}" \
  --database-url="${DATABASE_URL}" \
  --dry-run \
  --verbose
```

**Expected Output (successful dry-run):**

```
INFO: Starting DCR encryption key rotation (DRY-RUN MODE)
INFO: Pre-flight checks: validating keys
INFO: Pre-flight checks: validating database connection
INFO: Pre-flight checks: found 12 DCR clients
INFO: Dry-run mode: testing decrypt/re-encrypt on 12 clients
DEBUG: Testing client gemini-order-abc123 (1/12)
DEBUG: Testing client gemini-order-def456 (2/12)
...
INFO: Dry-run complete: all 12 records can be rotated
```

**If dry-run fails**, STOP:

```
ERROR: Failed to decrypt client_id=gemini-order-abc123 with old key
ERROR: Pre-flight check failed: Failed to decrypt secret with old key: ...
```

**Common causes:**
- Old key is incorrect (not the current production key)
- Database contains secrets encrypted with a different key (previous rotation incomplete)
- Secret corruption in database

**Resolution:** Verify `OLD_ENCRYPTION_KEY` matches the current production key in Secret Manager. If mismatch, do NOT proceed. Investigate database state.

---

### Step 6: Run Migration Script (Production)

**WARNING:** This step modifies the database. Ensure dry-run passed in Step 5.

```bash
# Production migration (no --dry-run flag)
python scripts/rotate_dcr_encryption_key.py \
  --old-key="${OLD_ENCRYPTION_KEY}" \
  --new-key="${NEW_ENCRYPTION_KEY}" \
  --database-url="${DATABASE_URL}" \
  --verbose
```

**Expected Output (successful rotation):**

```
INFO: Starting DCR encryption key rotation (PRODUCTION MODE)
INFO: Pre-flight checks: validating keys
INFO: Pre-flight checks: validating database connection
INFO: Pre-flight checks: found 12 DCR clients
INFO: Production mode: rotating 12 clients
INFO: Rotation complete: 12 clients rotated successfully
```

**If migration fails mid-rotation:**

```
ERROR: Failed to decrypt client_id=gemini-order-xyz789 with old key
ERROR: Transaction rolled back
```

The database is **unchanged** (transaction rollback). Safe to retry or investigate.

**Do NOT proceed to Step 7** if migration fails. Database still uses old key.

---

### Step 7: Update Secret Manager

Only update Secret Manager **after migration succeeds** (Step 6).

```bash
# Add new encryption key version
echo -n "${NEW_ENCRYPTION_KEY}" | gcloud secrets versions add dcr-encryption-key \
  --data-file=- \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Verify new version created
gcloud secrets versions list dcr-encryption-key \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --limit=3
```

**Expected Output:**
```
NAME  STATE    CREATED              DESTROYED
3     ENABLED  2026-05-04T15:00:00  -
2     ENABLED  2025-05-04T15:00:00  -
1     ENABLED  2024-05-04T15:00:00  -
```

---

### Step 8: Restart Marketplace Handler

Marketplace Handler service must pick up the new encryption key from Secret Manager.

```bash
# Restart marketplace handler
gcloud run services update marketplace-handler \
  --region=us-central1 \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Wait for service to become ready
sleep 15

# Check service status
gcloud run services describe marketplace-handler \
  --region=us-central1 \
  --format='value(status.conditions[0].status)' \
  --project="${GOOGLE_CLOUD_PROJECT}"
```

**Expected Output:**
```
True
```

---

### Step 9: Verification

<TBD>

**If verification fails**, proceed to rollback (Step 10).

---

### Step 10: Rollback (if verification fails)

**Option A: Reverse migration (preferred)** — re-run the script with keys swapped:

```bash
# Re-run migration with keys swapped to restore old encryption
python scripts/rotate_dcr_encryption_key.py \
  --old-key="${NEW_ENCRYPTION_KEY}" \
  --new-key="${OLD_ENCRYPTION_KEY}" \
  --database-url="${DATABASE_URL}" \
  --verbose
```

Then disable the new key in Secret Manager and restart the marketplace handler:

```bash
# Disable new encryption key version
gcloud secrets versions disable <new-version> \
  --secret=dcr-encryption-key \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Restart marketplace handler with old key
gcloud run services update marketplace-handler \
  --region=us-central1 \
  --project="${GOOGLE_CLOUD_PROJECT}"
```

**Option B: Database backup restore (last resort)** — only if the new key has been lost and reverse migration is not possible:

```bash
BACKUP_ID="<backup-id-from-step-2>"

gcloud sql backups restore "${BACKUP_ID}" \
  --backup-instance="${DB_INSTANCE_NAME}" \
  --backup-project="${GOOGLE_CLOUD_PROJECT}" \
  --instance="${DB_INSTANCE_NAME}" \
  --project="${GOOGLE_CLOUD_PROJECT}"

# This operation takes 5-15 minutes

# Disable new encryption key in Secret Manager
gcloud secrets versions disable <new-version> \
  --secret=dcr-encryption-key \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Restart marketplace handler with old key
gcloud run services update marketplace-handler \
  --region=us-central1 \
  --project="${GOOGLE_CLOUD_PROJECT}"
```

**WARNING:** Backup restore loses any DCR clients created after the backup.

**Re-run verification** to confirm DCR functionality restored with old key.

---

### Step 11: Cleanup

Zero encryption keys from environment and shell history after confirming rotation succeeded (or rollback completed):

```bash
unset OLD_ENCRYPTION_KEY
unset NEW_ENCRYPTION_KEY
unset DATABASE_URL

history -c
```

---

## Appendix A: Migration Script Reference

**Script:** `scripts/rotate_dcr_encryption_key.py`

**Purpose:** Re-encrypt DCR OAuth client secrets from old Fernet encryption key to new key.

---

### Usage

**Dry-Run Mode (recommended first):**

```bash
python scripts/rotate_dcr_encryption_key.py \
  --old-key="<current-key>" \
  --new-key="<new-key>" \
  --database-url="postgresql+asyncpg://user:pass@host/db" \
  --dry-run
```

**Production Mode:**

```bash
python scripts/rotate_dcr_encryption_key.py \
  --old-key="<current-key>" \
  --new-key="<new-key>" \
  --database-url="postgresql+asyncpg://user:pass@host/db"
```

**Verbose Output:**

```bash
python scripts/rotate_dcr_encryption_key.py ... --verbose
```

**Environment Variables (alternative to CLI args):**

```bash
export DCR_OLD_KEY="<current-key>"
export DCR_NEW_KEY="<new-key>"
export DATABASE_URL="postgresql+asyncpg://..."
python scripts/rotate_dcr_encryption_key.py --dry-run
```

---

### Arguments

| Argument | Required | Description | Environment Variable |
|----------|----------|-------------|---------------------|
| `--old-key` | Yes | Current Fernet encryption key (44-char base64) | `DCR_OLD_KEY` |
| `--new-key` | Yes | New Fernet encryption key (44-char base64) | `DCR_NEW_KEY` |
| `--database-url` | Yes | PostgreSQL connection string | `DATABASE_URL` |
| `--dry-run` | No | Test mode (no database writes) | N/A |
| `--verbose` | No | Detailed progress logging | N/A |

---

### Exit Codes

| Code | Meaning | Resolution |
|------|---------|------------|
| 0 | Success (all records rotated) | Rotation complete |
| 1 | Pre-flight check failed | Verify keys and database connection |
| 2 | Migration failed | Check error message, restore from backup if needed |

---

### Output Interpretation

**Dry-Run Success:**

```
INFO: Dry-run complete: all 12 records can be rotated
INFO: Rotation summary: 12 clients tested, 0 errors
```

All secrets can be decrypted with old key and re-encrypted with new key. Safe to proceed with production mode.

**Production Success:**

```
INFO: Rotation complete: 12 clients rotated successfully
```

All secrets re-encrypted and database updated. Proceed to Secret Manager update (Tier 3 Step 7).

**Error: Invalid Old Key:**

```
ERROR: Failed to decrypt client_id=gemini-order-abc123 with old key
ERROR: Decryption failed. Verify OLD_KEY is correct. Transaction rolled back.
```

Old key is incorrect or database contains secrets encrypted with a different key. Verify old key matches production Secret Manager value.

**Error: Keys Identical:**

```
ERROR: Pre-flight check failed: Keys must be different (no-op rotation not allowed)
```

Old and new keys are the same. Generate a new key with `Fernet.generate_key()`.

**Error: Database Connection:**

```
ERROR: Pre-flight check failed: Database connection failed: ...
```

Cannot connect to database. Verify `DATABASE_URL` is correct and database is accessible.

---

### Safety Features

1. **Dry-Run Mode:** Test decrypt/re-encrypt without database writes
2. **Transactional Updates:** All-or-nothing database updates (rollback on any error)
3. **Memory Safety:** Zeros plaintext secrets after re-encryption
4. **Pre-Flight Checks:** Validates keys and database before migration
5. **Progress Logging:** Shows each `client_id` rotated (never logs secret values)

---

### Architecture

**Migration Flow (per DCR client):**

```
1. Read encrypted_secret from database
   └─> "gAAAAABh..." (ciphertext, encrypted with OLD key)

2. Decrypt with OLD Fernet key
   └─> "my-oauth-secret-12345" ← PLAINTEXT (sensitive!)

3. Re-encrypt with NEW Fernet key
   └─> "gAAAAABi..." ← NEW ciphertext (encrypted with NEW key)

4. Update database record
   └─> UPDATE dcr_clients SET encrypted_secret = "gAAAAABi..." WHERE client_id = ...

5. Zero plaintext from memory
   └─> Overwrite plaintext bytes with zeros
```

**Transaction Boundary:**

All database updates happen in a single SQLAlchemy transaction:
- If any client fails to decrypt: rollback, exit with code 2
- If database error: rollback, exit with code 2
- If all succeed: commit, exit with code 0

**No partial updates possible** due to transactional safety.

---

## Appendix B: Emergency Rotation

**When to Use:**

- Credential leaked in logs, source control, or error messages
- Security incident or suspected breach
- Compliance requirement (audit finding, regulatory mandate)
- Suspected credential compromise (anomalous API usage, unauthorized access)

---

### Expedited Process

#### Phase 1: Assess Impact

**Questions to answer:**

1. **Which secret is compromised?**
   - Tier 1: `RED_HAT_SSO_CLIENT_SECRET` or `GMA_CLIENT_SECRET`
   - Tier 2: Database credentials
   - Tier 3: `DCR_ENCRYPTION_KEY`

2. **What is the exposure scope?**
   - Public (e.g., committed to GitHub, posted in public Slack channel)
   - Internal (e.g., internal logs, internal documentation)
   - Suspected (e.g., unusual API activity, failed auth attempts)

3. **Are there signs of unauthorized access?**
   - Check Cloud Logging for unusual API calls using compromised credentials
   - Review Service Control metrics for anomalous usage patterns
   - Check database audit logs (if enabled) for unauthorized queries

---

#### Phase 2: Containment (Immediate)

**Tier 1 (OAuth Secrets):**

1. **Disable compromised secret immediately:**

```bash
# Identify current secret version
gcloud secrets versions list redhat-sso-client-secret \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Disable current version (blocks all authentication with this secret)
# WARNING: This breaks authentication until new secret is added
gcloud secrets versions disable <current-version> \
  --secret=redhat-sso-client-secret \
  --project="${GOOGLE_CLOUD_PROJECT}"
```

2. **Escalate to CIAM team** (mark as urgent security incident):

```
Subject: URGENT - Security Incident - Compromised SSO Client Secret

SECURITY INCIDENT - URGENT

Compromised Secret: RED_HAT_SSO_CLIENT_SECRET
Exposure: [Public/Internal/Suspected]
Impact: [Describe exposure - where secret was leaked]

Current Status: Old secret disabled (authentication blocked)

Request: Expedited new client secret generation (emergency rotation)
Timeline: ASAP (production service impacted)

Security team notified: [Yes/No]
Incident ticket: [Link if available]
```

**Tier 2 (Database Credentials):**

1. **Follow Tier 2 procedure** (Steps 2-6) immediately — skip the maintenance window scheduling

**Tier 3 (DCR Encryption Key):**

1. **Assess blast radius:**
   - If encryption key leaked, all DCR OAuth client secrets are compromised
   - Tenant OAuth clients may be at risk

2. **Immediate actions:**
   - Disable DCR functionality (stop Marketplace Handler service)
   - Notify security team and stakeholders
   - Prepare for emergency Tier 3 rotation (requires database backup + 1-2 hour downtime)

```bash
# Stop marketplace handler (blocks new provisioning)
gcloud run services update marketplace-handler \
  --no-traffic \
  --region=us-central1 \
  --project="${GOOGLE_CLOUD_PROJECT}"
```

---

#### Phase 3: Communication (Parallel with Rotation)

**Internal Stakeholders:**

```
Subject: SECURITY INCIDENT - Credential Rotation in Progress

Security incident requiring emergency credential rotation:

**Status:** Containment complete, rotation in progress
**Affected Systems:** [List]
**Current Impact:** [Describe downtime or service degradation]
**Estimated Resolution:** [Timeline]

**Actions Taken:**
- Compromised credentials disabled
- Rotation procedures initiated
- Unauthorized access logs under review

**Next Steps:**
- Complete rotation (ETA: [time])
- Post-incident review
- Update incident response procedures

Updates will be provided every 30 minutes.
```

**External Stakeholders (if customer impact):**

```
Subject: Service Advisory - Maintenance in Progress

We are performing emergency maintenance on the Red Hat Lightspeed Agent for Google Cloud due to a security event.

**Impact:** [Describe customer-facing impact]
**Expected Resolution:** [Timeline]
**Actions Required:** None (service will auto-recover)

We will provide updates as the situation develops.
```

---

#### Phase 4: Post-Incident (Within 48 hours)

1. **Document Incident Timeline:**
   - When was credential compromised?
   - When was compromise detected?
   - Time to containment (disable old credential)
   - Time to rotation (new credential active)
   - Total incident duration

2. **Update Incident Response Procedures:**
   - What worked well?
   - What could be faster?
   - Were escalation paths clear?
   - Did communication templates help?

3. **Consider Policy Changes:**
   - Should rotation frequency increase for this secret tier?
   - Are additional monitoring/alerting needed?
   - Should secret access be restricted further?

---

### Compressed Timeline Example

**Hour 0: Detection and Containment**
- 00:00 - Credential compromise detected (leaked in logs)
- 00:05 - Old secret disabled (authentication blocked)
- 00:10 - CIAM escalation for new secret (Tier 1)
- 00:15 - Security team notified, incident opened

**Hour 0-1: Tier 1 Rotation**
- 00:30 - New SSO secret received from CIAM
- 00:35 - Secret Manager updated
- 00:40 - Verification complete (authentication restored)

**Hour 1-2: Tier 3 Rotation (if needed)**
- 01:00 - Database backup verified
- 01:10 - New encryption key generated
- 01:15 - Migration script dry-run passed
- 01:20 - Production migration complete
- 01:25 - Secret Manager updated, services restarted
- 01:30 - Verification complete

**Hour 2-3: Monitoring and Communication**
- 02:00 - Log analysis for unauthorized access
- 02:30 - Stakeholder update (rotation complete)
- 03:00 - Service fully operational, incident closed

**Day 1-7: Post-Incident**
- Day 1 - Post-incident review meeting
- Day 3 - Incident report published
- Day 7 - Policy updates implemented

---

### Emergency Contacts

**CIAM Team Escalation:**
- Primary: [TBD - add name/email/Slack]
- Secondary: [TBD - add name/email/Slack]
- Emergency (24/7): [TBD - add on-call rotation or pager]

**Security Team:**
- Primary: [TBD - add security contact]
- Incident Response: [TBD - add IR team contact]

**Engineering On-Call:**
- PagerDuty: [TBD - add PD integration or on-call schedule]

---
