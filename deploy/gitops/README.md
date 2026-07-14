# GitOps Deployment

ArgoCD-managed deployments for the Red Hat Lightspeed Agent. This directory contains the **Helm charts and setup scripts**. The ArgoCD Application CRs and environment-specific overrides live in a separate [GitOps repo](https://github.com/RHEcosystemAppEng/google-lightspeed-agent-gitops) to allow independent review workflows (devs own charts, SRE owns deployment config).

Two deployment targets:

- **OpenShift** — ArgoCD Application syncs the existing `deploy/openshift/` Helm chart
- **Google Cloud** — Helm chart (`google-cloud/`) where ArgoCD sync hooks trigger Cloud Build to deploy Cloud Run services

## Directory Structure

```
deploy/gitops/                   # This repo (app repo)
├── README.md
├── setup/                       # Prerequisite installation scripts
│   ├── README.md
│   ├── install-gitops-operator.sh
│   └── setup-gcp-sa.sh
└── google-cloud/
    ├── Chart.yaml
    ├── values.yaml              # All parameters with defaults
    ├── secrets.yaml.example     # Bootstrap secret setup instructions
    └── templates/
        ├── _helpers.tpl
        ├── deployment-config.yaml
        ├── serviceaccount.yaml
        ├── deploy-job.yaml
        └── NOTES.txt

google-lightspeed-agent-gitops/  # Separate GitOps repo
├── README.md
├── openshift/
│   ├── application.yaml         # ArgoCD Application CR (multi-source)
│   └── values-override.yaml     # Environment-specific overrides
└── google-cloud/
    ├── application.yaml         # ArgoCD Application CR (multi-source)
    └── values-override.yaml     # Environment-specific overrides
```

## Prerequisites

- OpenShift cluster with ArgoCD (OpenShift GitOps operator) installed
- For Google Cloud target: a GCP service account key with Cloud Build and Cloud Run permissions

Setup scripts are provided in `setup/` to automate these prerequisites. See [`setup/README.md`](setup/README.md) for details, environment variables, and manual alternatives.

## OpenShift Target

The OpenShift target uses ArgoCD to sync the existing Helm chart at `deploy/openshift/` with GitOps-managed overrides.

### Setup

1. Edit `openshift/values-override.yaml` in the [GitOps repo](https://github.com/RHEcosystemAppEng/google-lightspeed-agent-gitops) with your environment values (image tags, deployment mode, provider URL).

2. Apply the ArgoCD Application from the GitOps repo:
   ```bash
   oc apply -f openshift/application.yaml
   ```

3. ArgoCD will automatically sync the chart. The Application uses multi-source to reference the override file from the GitOps repo and the Helm chart from this repo, and is configured with:
   - **Automated sync** with self-heal and pruning
   - **Server-side apply** for conflict-free updates
   - **Retry** (3 attempts with exponential backoff)

### Updating

Change image tags or configuration in `openshift/values-override.yaml` in the GitOps repo, open a PR, and merge. ArgoCD syncs automatically on merge.

## Google Cloud Target

The Google Cloud target deploys Cloud Run services through Cloud Build. ArgoCD manages Kubernetes resources on OpenShift (ConfigMap, Secret, Jobs), and the PostSync hook Job calls out to GCP.

### How It Works

1. A PR changes image tags or config in `google-cloud/values-override.yaml` in the GitOps repo
2. PR merges to `main` in the GitOps repo
3. ArgoCD detects the change and begins sync
4. ArgoCD creates/updates K8s resources on OpenShift (ConfigMap, ServiceAccount)
5. **PostSync** — `deploy-job` clones the repo and runs `gcloud builds submit` with substitutions from the ConfigMap
6. Cloud Build pulls images from Quay.io, scans them, pushes to GCR, and deploys Cloud Run services

### Setup

1. Run `setup.sh` once to create all GCP resources (APIs, service accounts, secrets in GCP Secret Manager, Cloud SQL, Redis, Pub/Sub):
   ```bash
   ./deploy/cloudrun/setup.sh
   ```

2. Create the GCP service account and K8s secret for the deploy Job:
   ```bash
   export GOOGLE_CLOUD_PROJECT=my-project-id
   bash deploy/gitops/setup/setup-gcp-sa.sh
   ```
   Or manually create the secret (see [`setup/README.md`](setup/README.md) for details):
   ```bash
   oc create secret generic gcp-sa-bootstrap \
     --from-file=gcp-service-account-key=sa-key.json \
     -n rh-lightspeed-agent
   ```

3. Edit `google-cloud/values-override.yaml` in the [GitOps repo](https://github.com/RHEcosystemAppEng/google-lightspeed-agent-gitops) with your GCP project ID and image tags.

4. Apply the ArgoCD Application from the GitOps repo:
   ```bash
   oc apply -f google-cloud/application.yaml
   ```

5. (Optional) For private git repositories, create a token secret:
   ```bash
   oc create secret generic git-credentials \
     --from-literal=token=<GITHUB_PAT> \
     -n rh-lightspeed-agent
   ```
   Then set `deploy.gitTokenSecret: git-credentials` in your values override.

### Updating

To deploy new image versions, update the tags in the values override file in the GitOps repo:

```yaml
images:
  agent:
    tag: v1.2.3
  handler:
    tag: v1.2.3
```

Commit and push. ArgoCD syncs the ConfigMap change, then the PostSync Job triggers Cloud Build with the new substitutions.

### Secrets Management

Application secrets (SSO credentials, database URLs, etc.) are stored in **GCP Secret Manager** and read directly by Cloud Run services at runtime. The only secret on the OpenShift cluster is the GCP SA key (`gcp-sa-bootstrap`), used by the deploy Job to authenticate with `gcloud`.

### Load Balancer and DNS Setup

When load balancers are enabled (`loadBalancer.agent.enabled: "true"` or `loadBalancer.handler.enabled: "true"`), Cloud Build runs `setup-lb.sh` to create the full GCLB stack: static IP, Google-managed SSL certificate, serverless NEG, backend service, optional Cloud Armor WAF, URL map, HTTPS proxy, and forwarding rule.

This is **not** a chicken-and-egg problem — the deployment succeeds without DNS being configured:

1. **First deployment**: set `loadBalancer.agent.domain` and/or `loadBalancer.handler.domain` in your `values-override.yaml` and deploy. Cloud Build creates the static IPs and SSL certs in `PROVISIONING` state.
2. **Get the static IPs**: after the first deployment completes, look up the reserved IPs:
   ```bash
   # Replace lightspeed-lb with your loadBalancer.name value
   gcloud compute addresses describe lightspeed-lb-agent-ip --global --format='value(address)'
   gcloud compute addresses describe lightspeed-lb-handler-ip --global --format='value(address)'
   ```
3. **Create DNS A records**: point your domains to the static IPs in your DNS provider.
4. **Wait for SSL provisioning**: Google validates domain ownership via DNS and provisions the certificate (15–60 minutes after DNS propagates). Check status:
   ```bash
   gcloud compute ssl-certificates describe lightspeed-lb-agent-cert --global --format='value(managed.status)'
   ```
5. **No redeployment needed** — once the cert status changes from `PROVISIONING` to `ACTIVE`, HTTPS traffic flows automatically.

Subsequent deployments (image tag bumps, config changes) reuse the existing static IPs and certs. All `setup-lb.sh` commands are idempotent.

### Cloud Build Substitutions

The ConfigMap maps `values.yaml` fields to Cloud Build `_VARIABLE` names. All substitutions match `cloudbuild.yaml` in the repository root. Key mappings:

| values.yaml | Cloud Build Variable |
|---|---|
| `project.id` | `GOOGLE_CLOUD_PROJECT` |
| `project.region` | `_REGION` |
| `images.agent.tag` | `_IMAGE_TAG` |
| `images.agent.source` | `_AGENT_SOURCE_IMAGE` |
| `services.agent.name` | `_SERVICE_NAME` |
| `loadBalancer.agent.enabled` | `_ENABLE_LB_AGENT` |
| `security.scanSeverity` | `_SCAN_SEVERITY` |

See `templates/deployment-config.yaml` for the complete mapping.

### GCP Service Account Roles

The GCP service account used for the deploy Job needs the following IAM roles:

| Role | Scope | Purpose |
|---|---|---|
| `roles/cloudbuild.builds.editor` | Project | Submit Cloud Build pipelines |
| `roles/run.admin` | Project | Deploy Cloud Run services (via Cloud Build) |
| `roles/serviceusage.serviceUsageConsumer` | Project | `gcloud builds submit` API access |
| `roles/iam.serviceAccountUser` | Cloud Run runtime SA | Impersonate the Cloud Run runtime SA |

### Cloud Build Service Account Roles

The Cloud Build default SA (`<project-number>@cloudbuild.gserviceaccount.com`) runs the deployment pipeline. It needs the following IAM roles, which `setup.sh` and `deploy-cloudbuild.sh` grant automatically:

| Role | Scope | Purpose |
|---|---|---|
| `roles/run.admin` | Project | Deploy Cloud Run services |
| `roles/iam.serviceAccountUser` | Project | Act as the Cloud Run runtime SA |
| `roles/pubsub.editor` | Project | Create/update Pub/Sub push subscriptions |
| `roles/monitoring.dashboardEditor` | Project | Create/update Cloud Monitoring dashboards |
| `roles/compute.admin` | Project | Create GCLB resources (only when LB is enabled) |
| `roles/iam.serviceAccountTokenCreator` | Pub/Sub invoker SA | Impersonate the invoker SA for cross-project Pub/Sub subscriptions |

> **Note:** `setup.sh` grants `roles/iam.serviceAccountTokenCreator` on the Pub/Sub invoker SA automatically. If deploying without `setup.sh` (e.g., adopting an existing environment), grant it manually — see `deploy-cloudbuild.sh` for the full list.

## Cross-Cluster Deployment

By default, both Application CRs deploy to the same cluster where ArgoCD runs (`destination.server: https://kubernetes.default.svc`). In production, the two targets typically use different topologies:

- **OpenShift target** — ArgoCD on Cluster 1 (hub), agent deployed to Cluster 2 (spoke). Two independent OpenShift installations.
- **Google Cloud target** — ArgoCD on the same OpenShift cluster, triggers Cloud Build to deploy Cloud Run services on GCP. No second OpenShift cluster involved.

### Registering a Remote Cluster (OpenShift Target)

To deploy the agent to Cluster 2 from ArgoCD on Cluster 1:

**On Cluster 2** (spoke), create a ServiceAccount for ArgoCD:

```bash
oc create namespace admin-argocd
oc create sa admin-argocd-sa -n admin-argocd
oc adm policy add-cluster-role-to-user cluster-admin \
  system:serviceaccount:admin-argocd:admin-argocd-sa
```

Create a long-lived token for the SA:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: argocd-admin-sa-secret
  namespace: admin-argocd
  annotations:
    kubernetes.io/service-account.name: admin-argocd-sa
type: kubernetes.io/service-account-token
```

**On Cluster 1** (hub), create a cluster connection Secret in the ArgoCD namespace:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: spoke-cluster
  namespace: openshift-gitops
  labels:
    argocd.argoproj.io/secret-type: cluster
type: Opaque
stringData:
  name: spoke-cluster
  server: https://api.cluster2.example.com:6443
  config: |
    {
      "bearerToken": "<token-from-spoke-sa>",
      "tlsClientConfig": {
        "insecure": false,
        "caData": "<base64-CA-cert>"
      }
    }
```

Alternatively, use the ArgoCD CLI: `argocd cluster add <context-name>`.

### Updating the Application CR

Change `destination.server` in `openshift/application.yaml` to the remote cluster's API URL:

```yaml
destination:
  server: https://api.cluster2.example.com:6443
  namespace: lightspeed-agent
```

The server URL must match the `server` field in the cluster connection Secret exactly.

### Prerequisites on Cluster 2

The OpenShift target does not require any operators on Cluster 2. ArgoCD pushes the Helm chart resources remotely via the K8s API. The only requirements:

- **App secrets** (SSO, DB, Redis, etc.) must exist on Cluster 2 in the target namespace — managed via SealedSecrets, Vault, or manually (the chart has `secrets.create: false` by default)
- **Network access** — Cluster 1 must reach Cluster 2's API server (port 6443)

### Credential Rotation

| Credential | Rotation method |
|---|---|
| ArgoCD cluster token | Re-register via `argocd cluster add` or update the cluster Secret |
| GCP SA key | Re-run `setup-gcp-sa.sh` (every 90 days recommended) |

For production, consider **Workload Identity Federation** to eliminate GCP SA key rotation, or the **ArgoCD Agent model** (pull-based sync, eliminates long-lived tokens to spoke clusters).

## Multiple Instances on the Same GCP Project

The chart supports deploying multiple agent instances to the same GCP project (e.g., staging + production, or multi-tenant). All GCP resource names are configurable via `values.yaml`, so each instance needs unique names to avoid collisions.

### What Collides with Default Values

If two instances use the same `project.id` without overriding resource names, these GCP resources collide:

| Resource | Default Name | Override Key |
|----------|-------------|-------------|
| Cloud Run agent service | `lightspeed-agent` | `services.agent.name` |
| Cloud Run handler service | `marketplace-handler` | `services.handler.name` |
| GCP runtime service account | `lightspeed-agent` | `services.serviceAccountName` |
| Cloud SQL instance | `lightspeed-agent-db` | `infrastructure.dbInstanceName` |
| VPC connector | `lightspeed-redis-conn` | `infrastructure.vpcConnectorName` |
| Pub/Sub subscription | `<topic-short-name>-sub` (auto-generated) | `pubsub.subscription` |
| Pub/Sub invoker service account | `pubsub-invoker` | `pubsub.invokerName` |
| Load balancer (name prefix) | `lightspeed-lb` | `loadBalancer.name` |
| GitOps deploy service account | `lightspeed-gitops` | `SA_NAME` env var to `setup-gcp-sa.sh` |

The `loadBalancer.name` value is a **prefix** for all GCLB sub-resources created per service (agent and handler): static IP, SSL certificate, serverless NEG, backend service, Cloud Armor policy, URL map, HTTPS proxy, and forwarding rule. Each follows the pattern `{name}-{service}-{type}` (e.g., `lightspeed-lb-agent-ip`, `lightspeed-lb-handler-backend`). Overriding `loadBalancer.name` is sufficient to avoid collisions for all of them.

On the OpenShift side, K8s resources are scoped by Helm release name and namespace, so they don't collide as long as each instance uses a different release name or namespace.

### GCP Resource Name Length Limits

When adding prefixes (e.g., `staging-`) to the override keys above, keep GCP naming constraints in mind:

| Resource | Override Key | Max Length |
|----------|-------------|------------|
| VPC connector | `infrastructure.vpcConnectorName` | **<21 effective chars** (hyphens count as 2) |
| GCP Service Account | `services.serviceAccountName` | **30 chars** |
| Cloud Run service | `services.agent.name`, `services.handler.name` | 63 chars |
| Cloud SQL instance | `infrastructure.dbInstanceName` | 84 chars |
| Pub/Sub topic | `pubsub.topic` | 255 chars |

The **VPC connector name** is the tightest constraint. Per [GCP docs](https://docs.cloud.google.com/vpc/docs/configure-serverless-vpc-access), the name must be less than 21 characters with hyphens counting as 2. The default `lightspeed-redis-conn` (23 effective chars) exceeds this documented limit but is accepted by GCP in practice — however, adding any prefix to it will likely fail. Use shorter base names for multi-instance deployments (e.g., `ls-redis-stg`, `ls-redis-prd`). For SA names (30 chars), `staging-lightspeed-agent` (24 chars) fits, but `my-company-staging-lightspeed-agent` (35 chars) does not. Names that exceed limits are rejected by `gcloud` at `setup.sh` time.

### What Is Shared by Design

These resources are shared across instances on the same project and generally don't need to be separated:

- **GCR images** — Cloud Build pushes scanned images to `gcr.io/<project>/`. All instances on the same project reuse the same GCR images (tagged by `_IMAGE_TAG`), which is typically desired.
- **GCP Secret Manager secrets** — Runtime secrets (`database-url`, `redhat-sso-client-id`, etc.) are referenced by fixed names in the Cloud Run service templates (`deploy/cloudrun/service.yaml`). If instances need different credentials, the service templates must be modified to parameterize secret names.

### Shared vs Separate Infrastructure

| Component | Shared | Separate |
|-----------|--------|----------|
| Cloud SQL | Same instance, different databases (configure via `DATABASE_URL` secret) | Different `infrastructure.dbInstanceName` per instance + separate `setup.sh` run |
| Redis / VPC connector | Same connector and Redis instance | Different `infrastructure.vpcConnectorName` per instance |
| Pub/Sub topic | **Always shared** — Google Cloud Marketplace publishes to one topic per GCP project. All instances use the same `pubsub.topic`. | N/A |
| Pub/Sub subscription | Each instance needs its own subscription pointing to its handler URL | Different `pubsub.subscription` per instance |

Since all instances share the same Pub/Sub topic, every handler receives every marketplace event. The handler filters events by **product ID**: it compares the event's `entitlement.product` field against `pubsub.serviceControlServiceName` (e.g., `stage-lightspeed-agent.endpoints.my-project.cloud.goog`) and silently skips events for other products. Each instance must set `pubsub.serviceControlServiceName` to its own product endpoint — see the values-override examples below.

### Step-by-Step: Deploy Two Instances (staging + prod)

#### 1. Run `setup.sh` for Each Instance

`setup.sh` is a **one-time infrastructure provisioning** script that creates the GCP resources the agent needs to run: enables APIs, creates the runtime service account + IAM bindings, Secret Manager secrets, Cloud SQL instance, Pub/Sub topic, and VPC connector. It is **not** part of the Cloud Build pipeline — `cloudbuild.yaml` (triggered by ArgoCD on every config change) is the repeatable deployment pipeline that assumes all infrastructure from `setup.sh` already exists.

Each instance needs its own `setup.sh` run because it creates instance-specific GCP resources. Run it with different service names:

```bash
# Instance A (staging)
export GOOGLE_CLOUD_PROJECT=my-project-id
export GOOGLE_CLOUD_LOCATION=us-central1
export SERVICE_NAME=lightspeed-agent-staging
export SERVICE_ACCOUNT_NAME=lightspeed-staging
export HANDLER_SERVICE_NAME=marketplace-handler-staging
export DB_INSTANCE_NAME=lightspeed-db-staging
export PUBSUB_INVOKER_NAME=pubsub-invoker-staging
export PUBSUB_TOPIC=projects/cloudcommerceproc-prod/topics/my-project-id
export REDIS_INSTANCE_NAME=lightspeed-redis-staging
export VPC_CONNECTOR_NAME=ls-redis-staging
export VPC_CONNECTOR_RANGE=10.9.0.0/28
export DATABASE_URL_SECRET=database-url-staging
export SESSION_DATABASE_URL_SECRET=session-database-url-staging
export DCR_ENCRYPTION_KEY_SECRET=dcr-encryption-key-staging
export REDIS_URL_SECRET=rate-limit-redis-url-staging
export REDIS_CA_CERT_SECRET=redis-ca-cert-staging
export LB_NAME=lightspeed-lb-staging
export ENABLE_LB_AGENT=true
export AGENT_DOMAIN_NAME=staging-agent.example.com
export ENABLE_LB_HANDLER=true
export HANDLER_DOMAIN_NAME=staging-handler.example.com
./deploy/cloudrun/setup.sh

# Instance B (prod)
export GOOGLE_CLOUD_PROJECT=my-project-id
export GOOGLE_CLOUD_LOCATION=us-central1
export SERVICE_NAME=lightspeed-agent-prod
export SERVICE_ACCOUNT_NAME=lightspeed-prod
export HANDLER_SERVICE_NAME=marketplace-handler-prod
export DB_INSTANCE_NAME=lightspeed-db-prod
export PUBSUB_INVOKER_NAME=pubsub-invoker-prod
export PUBSUB_TOPIC=projects/cloudcommerceproc-prod/topics/my-project-id
export REDIS_INSTANCE_NAME=lightspeed-redis-prod
export VPC_CONNECTOR_NAME=ls-redis-prod
export VPC_CONNECTOR_RANGE=10.10.0.0/28
export DATABASE_URL_SECRET=database-url-prod
export SESSION_DATABASE_URL_SECRET=session-database-url-prod
export DCR_ENCRYPTION_KEY_SECRET=dcr-encryption-key-prod
export REDIS_URL_SECRET=rate-limit-redis-url-prod
export REDIS_CA_CERT_SECRET=redis-ca-cert-prod
export LB_NAME=lightspeed-lb-prod
export ENABLE_LB_AGENT=true
export AGENT_DOMAIN_NAME=agent.example.com
export ENABLE_LB_HANDLER=true
export HANDLER_DOMAIN_NAME=handler.example.com
./deploy/cloudrun/setup.sh
```

> **Note:** `setup.sh` now automatically creates Cloud SQL, Redis/Memorystore, and VPC connector instances, and populates the corresponding Secret Manager secrets. `PUBSUB_TOPIC` is the same for both instances — Google Cloud Marketplace publishes to one topic per GCP project. Each instance must use a different `VPC_CONNECTOR_RANGE` to avoid IP conflicts. To deploy without load balancers, set `ENABLE_LB_AGENT=false` and `ENABLE_LB_HANDLER=false` and omit the domain names.
>
> `PUBSUB_SUBSCRIPTION` and `SERVICE_CONTROL_SERVICE_NAME` are set in the Helm `values-override.yaml` (step 5), not in `setup.sh` — these are deployment-time settings handled by Cloud Build.

Many `setup.sh` env vars must match the corresponding `values-override.yaml` fields in step 5. Use the same values in both:

| `setup.sh` env var | `values-override.yaml` field |
|---|---|
| `SERVICE_NAME` | `services.agent.name` |
| `HANDLER_SERVICE_NAME` | `services.handler.name` |
| `SERVICE_ACCOUNT_NAME` | `services.serviceAccountName` |
| `DB_INSTANCE_NAME` | `infrastructure.dbInstanceName` |
| `VPC_CONNECTOR_NAME` | `infrastructure.vpcConnectorName` |
| `PUBSUB_INVOKER_NAME` | `pubsub.invokerName` |
| `LB_NAME` | `loadBalancer.name` |
| `DATABASE_URL_SECRET` | `secrets.databaseUrl` |
| `SESSION_DATABASE_URL_SECRET` | `secrets.sessionDatabaseUrl` |
| `DCR_ENCRYPTION_KEY_SECRET` | `secrets.dcrEncryptionKey` |
| `REDIS_URL_SECRET` | `rateLimit.redisUrlSecret` |
| `REDIS_CA_CERT_SECRET` | `rateLimit.redisCaCertSecret` |

#### 2. Register Service Accounts in the Google Cloud Marketplace Producer Portal

Each instance's service accounts must be registered in the [Producer Portal](https://console.cloud.google.com/producer-portal) under the **Technical Integration** section of your product:

- **Partner Procurement API integration** — add the runtime SA (e.g., `sa-lightspeed-agent-staging@<project>.iam.gserviceaccount.com`). This authorizes the SA to call the Procurement API for entitlement management.
- **Cloud Pub/Sub integration** — add the Pub/Sub invoker SA (e.g., `pubsub-invoker-staging@<project>.iam.gserviceaccount.com`). This authorizes the SA to create push subscriptions on the Marketplace entitlements topic.

Without this step, the deployment will fail at the `configure-pubsub` Cloud Build step with `"User not authorized to perform this action"`.

#### 3. Create Per-Instance GCP Deploy Service Accounts

```bash
# Staging deploy SA
export GOOGLE_CLOUD_PROJECT=my-project-id
SA_NAME=lightspeed-gitops-staging CLOUD_RUN_SA=lightspeed-staging \
  SECRET_NAME=gcp-sa-staging NAMESPACE=rh-lightspeed-staging \
  bash deploy/gitops/setup/setup-gcp-sa.sh

# Prod deploy SA
SA_NAME=lightspeed-gitops-prod CLOUD_RUN_SA=lightspeed-prod \
  SECRET_NAME=gcp-sa-prod NAMESPACE=rh-lightspeed-prod \
  bash deploy/gitops/setup/setup-gcp-sa.sh
```

`CLOUD_RUN_SA` and `SECRET_NAME` must match the corresponding `values-override.yaml` fields:

| `setup-gcp-sa.sh` env var | `values-override.yaml` field |
|---|---|
| `CLOUD_RUN_SA` | `services.serviceAccountName` |
| `SECRET_NAME` | `deploy.gcpSecretName` |

#### 4. Structure the GitOps Repo

Create per-instance directories in the GitOps repo:

```
google-lightspeed-agent-gitops/
├── google-cloud/
│   ├── staging/
│   │   ├── application.yaml
│   │   └── values-override.yaml
│   └── prod/
│       ├── application.yaml
│       └── values-override.yaml
└── openshift/
    └── ...
```

#### 5. Configure Instance-Specific Values

Each `values-override.yaml` must override all resource names to avoid collisions:

**`staging/values-override.yaml`:**
```yaml
project:
  id: my-project-id
  region: us-central1
  # vertexaiLocation: global

images:
  agent:
    tag: v1.2.3-rc1
  handler:
    tag: v1.2.3-rc1
  # mcp:
  #   tag: latest

agent:
  geminiModel: "gemini-3.5-flash"
  # loggingDetail: "basic"

# mcp:
#   debug: "false"

services:
  agent:
    name: lightspeed-agent-staging
  handler:
    name: marketplace-handler-staging
  serviceAccountName: lightspeed-staging

infrastructure:
  dbInstanceName: lightspeed-db-staging
  vpcConnectorName: lightspeed-redis-staging

pubsub:
  topic: projects/cloudcommerceproc-prod/topics/YOUR_TOPIC
  subscription: marketplace-sub-staging
  invokerName: pubsub-invoker-staging
  serviceControlServiceName: staging-agent.endpoints.my-project-id.cloud.goog

secrets:
  databaseUrl: "database-url-staging"
  sessionDatabaseUrl: "session-database-url-staging"
  dcrEncryptionKey: "dcr-encryption-key-staging"

rateLimit:
  keyPrefix: "lightspeed-staging:ratelimit"
  redisUrlSecret: "rate-limit-redis-url-staging"
  redisCaCertSecret: "redis-ca-cert-staging"

loadBalancer:
  name: lightspeed-lb-staging
  agent:
    enabled: "true"
    domain: staging-agent.example.com
    cloudArmor:
      enabled: "true"
      sensitivity: "1"
  handler:
    enabled: "true"
    domain: staging-handler.example.com
    cloudArmor:
      enabled: "true"
      sensitivity: "2"

security:
  allowUnauthenticated: "false"
  scanSeverity: CRITICAL,HIGH

deploy:
  gcpSecretName: gcp-sa-staging
  serviceAccount:
    name: lightspeed-deploy-staging
```

**`prod/values-override.yaml`:**
```yaml
project:
  id: my-project-id
  region: us-central1
  # vertexaiLocation: global

images:
  agent:
    tag: v1.2.3
  handler:
    tag: v1.2.3
  # mcp:
  #   tag: latest

agent:
  geminiModel: "gemini-3.5-flash"
  # loggingDetail: "basic"

# mcp:
#   debug: "false"

services:
  agent:
    name: lightspeed-agent-prod
  handler:
    name: marketplace-handler-prod
  serviceAccountName: lightspeed-prod

infrastructure:
  dbInstanceName: lightspeed-db-prod
  vpcConnectorName: lightspeed-redis-prod

pubsub:
  topic: projects/cloudcommerceproc-prod/topics/YOUR_TOPIC
  subscription: marketplace-sub-prod
  invokerName: pubsub-invoker-prod
  serviceControlServiceName: prod-agent.endpoints.my-project-id.cloud.goog

secrets:
  databaseUrl: "database-url-prod"
  sessionDatabaseUrl: "session-database-url-prod"
  dcrEncryptionKey: "dcr-encryption-key-prod"

rateLimit:
  keyPrefix: "lightspeed-prod:ratelimit"
  redisUrlSecret: "rate-limit-redis-url-prod"
  redisCaCertSecret: "redis-ca-cert-prod"

loadBalancer:
  name: lightspeed-lb-prod
  agent:
    enabled: "true"
    domain: agent.example.com
    cloudArmor:
      enabled: "true"
      sensitivity: "1"
  handler:
    enabled: "true"
    domain: handler.example.com
    cloudArmor:
      enabled: "true"
      sensitivity: "2"

security:
  allowUnauthenticated: "false"
  scanSeverity: CRITICAL,HIGH

deploy:
  gcpSecretName: gcp-sa-prod
  serviceAccount:
    name: lightspeed-deploy-prod
```

#### 6. Create ArgoCD Applications

Each `application.yaml` should use:
- A unique Application name (e.g., `lightspeed-staging`, `lightspeed-prod`)
- The corresponding `values-override.yaml` path in the multi-source configuration

**Namespace options:**

- **Separate namespaces** (recommended): use a unique namespace per instance (e.g., `rh-lightspeed-staging`, `rh-lightspeed-prod`). Simplest isolation — no extra overrides needed.
- **Same namespace**: possible if each instance uses a different Helm release name **and** overrides `deploy.gcpSecretName` and `deploy.serviceAccount.name`, since both have fixed defaults (`gcp-sa-bootstrap` and `lightspeed-deploy`) that would collide. All other K8s resources are scoped by `chart.fullname` (which includes the release name) and won't conflict.

  When using a shared namespace, run `setup-gcp-sa.sh` with per-instance secret and SA names but the **same** `NAMESPACE`:

  ```bash
  # Staging — shared namespace
  SA_NAME=lightspeed-gitops-staging CLOUD_RUN_SA=lightspeed-staging \
    SECRET_NAME=gcp-sa-staging NAMESPACE=rh-lightspeed-agent \
    bash deploy/gitops/setup/setup-gcp-sa.sh

  # Prod — shared namespace
  SA_NAME=lightspeed-gitops-prod CLOUD_RUN_SA=lightspeed-prod \
    SECRET_NAME=gcp-sa-prod NAMESPACE=rh-lightspeed-agent \
    bash deploy/gitops/setup/setup-gcp-sa.sh
  ```

  Then in each `values-override.yaml`, set the matching overrides:

  ```yaml
  deploy:
    gcpSecretName: gcp-sa-staging        # matches SECRET_NAME above
    serviceAccount:
      name: lightspeed-deploy-staging    # unique per instance
  ```

#### 7. Apply Both Applications

```bash
oc apply -f staging/application.yaml
oc apply -f prod/application.yaml
```

ArgoCD manages each instance independently. Updating staging's `values-override.yaml` only triggers a staging deployment.
