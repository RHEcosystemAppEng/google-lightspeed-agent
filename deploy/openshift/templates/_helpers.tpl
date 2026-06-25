{{/*
Expand the name of the chart.
*/}}
{{- define "lightspeed-agent.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "lightspeed-agent.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "lightspeed-agent.labels" -}}
app.kubernetes.io/name: {{ include "lightspeed-agent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.agent.image.tag | default .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: lightspeed-agent
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Selector labels for the agent
*/}}
{{- define "lightspeed-agent.agentSelectorLabels" -}}
app.kubernetes.io/name: {{ include "lightspeed-agent.fullname" . }}
app.kubernetes.io/component: agent
{{- end }}

{{/*
Selector labels for PostgreSQL
*/}}
{{- define "lightspeed-agent.postgresqlSelectorLabels" -}}
app.kubernetes.io/name: {{ include "lightspeed-agent.fullname" . }}-postgresql
app.kubernetes.io/component: database
{{- end }}

{{/*
Selector labels for Redis
*/}}
{{- define "lightspeed-agent.redisSelectorLabels" -}}
app.kubernetes.io/name: {{ include "lightspeed-agent.fullname" . }}-redis
app.kubernetes.io/component: ratelimit
{{- end }}

{{/*
PostgreSQL service name
*/}}
{{- define "lightspeed-agent.postgresqlServiceName" -}}
{{- include "lightspeed-agent.fullname" . }}-postgresql
{{- end }}

{{/*
Redis service name
*/}}
{{- define "lightspeed-agent.redisServiceName" -}}
{{- include "lightspeed-agent.fullname" . }}-redis
{{- end }}

{{/*
Marketplace PostgreSQL service name
*/}}
{{- define "lightspeed-agent.marketplacePostgresqlServiceName" -}}
{{- include "lightspeed-agent.fullname" . }}-marketplace-postgresql
{{- end }}

{{/*
Selector labels for marketplace PostgreSQL
*/}}
{{- define "lightspeed-agent.marketplacePostgresqlSelectorLabels" -}}
app.kubernetes.io/name: {{ include "lightspeed-agent.fullname" . }}-marketplace-postgresql
app.kubernetes.io/component: marketplace-database
{{- end }}

{{/*
Selector labels for the marketplace handler
*/}}
{{- define "lightspeed-agent.handlerSelectorLabels" -}}
app.kubernetes.io/name: {{ include "lightspeed-agent.fullname" . }}-handler
app.kubernetes.io/component: handler
{{- end }}

{{/*
Handler service name
*/}}
{{- define "lightspeed-agent.handlerServiceName" -}}
{{- include "lightspeed-agent.fullname" . }}-handler
{{- end }}

{{/*
Selector labels for the standalone UI
*/}}
{{- define "lightspeed-agent.uiSelectorLabels" -}}
app.kubernetes.io/name: {{ include "lightspeed-agent.fullname" . }}-ui
app.kubernetes.io/component: ui
{{- end }}

{{/*
UI service name
*/}}
{{- define "lightspeed-agent.uiServiceName" -}}
{{- include "lightspeed-agent.fullname" . }}-ui
{{- end }}

{{/*
MLflow service name
*/}}
{{- define "lightspeed-agent.mlflowServiceName" -}}
{{- include "lightspeed-agent.fullname" . }}-mlflow
{{- end }}

{{/*
Selector labels for MLflow
*/}}
{{- define "lightspeed-agent.mlflowSelectorLabels" -}}
app.kubernetes.io/name: {{ include "lightspeed-agent.fullname" . }}-mlflow
app.kubernetes.io/component: mlflow
{{- end }}

{{/*
MLflow PostgreSQL service name
*/}}
{{- define "lightspeed-agent.mlflowPostgresqlServiceName" -}}
{{- include "lightspeed-agent.fullname" . }}-mlflow-postgresql
{{- end }}

{{/*
Selector labels for MLflow PostgreSQL
*/}}
{{- define "lightspeed-agent.mlflowPostgresqlSelectorLabels" -}}
app.kubernetes.io/name: {{ include "lightspeed-agent.fullname" . }}-mlflow-postgresql
app.kubernetes.io/component: mlflow-database
{{- end }}

{{/*
Whether the handler should be deployed on OCP.
Only deployed in standalone mode — in hybrid the handler stays on GCP.
*/}}
{{- define "lightspeed-agent.handlerEnabled" -}}
{{- eq .Values.deploymentMode "standalone" -}}
{{- end }}

{{/*
Whether the standalone UI should be deployed.
Only deployed in standalone mode.
*/}}
{{- define "lightspeed-agent.uiEnabled" -}}
{{- eq .Values.deploymentMode "standalone" -}}
{{- end }}
