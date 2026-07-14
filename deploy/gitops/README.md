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
4. ArgoCD creates/updates K8s resources on OpenShift (ConfigMap, ServiceAccount, RBAC)
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
