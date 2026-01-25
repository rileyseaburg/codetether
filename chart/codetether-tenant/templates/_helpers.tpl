{{/*
Expand the name of the chart.
*/}}
{{- define "codetether-tenant.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "codetether-tenant.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "a2a-%s" .Values.tenant.orgSlug | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "codetether-tenant.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "codetether-tenant.labels" -}}
helm.sh/chart: {{ include "codetether-tenant.chart" . }}
{{ include "codetether-tenant.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
codetether.run/tenant-id: {{ .Values.tenant.id | quote }}
codetether.run/org-slug: {{ .Values.tenant.orgSlug | quote }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "codetether-tenant.selectorLabels" -}}
app.kubernetes.io/name: {{ include "codetether-tenant.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app: {{ include "codetether-tenant.fullname" . }}
{{- end }}

{{/*
Get resources for the current tier
*/}}
{{- define "codetether-tenant.resources" -}}
{{- $tier := .Values.tier | default "free" }}
{{- $resources := index .Values.resources $tier }}
requests:
  cpu: {{ $resources.requests.cpu }}
  memory: {{ $resources.requests.memory }}
limits:
  cpu: {{ $resources.limits.cpu }}
  memory: {{ $resources.limits.memory }}
{{- end }}

{{/*
Get replicas for the current tier
*/}}
{{- define "codetether-tenant.replicas" -}}
{{- $tier := .Values.tier | default "free" }}
{{- index .Values.replicas $tier }}
{{- end }}

{{/*
Get the hostname for the tenant
*/}}
{{- define "codetether-tenant.hostname" -}}
{{- printf "%s.%s" .Values.tenant.orgSlug .Values.ingress.baseDomain }}
{{- end }}

{{/*
Get the namespace for the tenant
*/}}
{{- define "codetether-tenant.namespace" -}}
{{- printf "tenant-%s" .Values.tenant.orgSlug }}
{{- end }}
