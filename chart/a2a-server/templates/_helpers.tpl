{{/*
Expand the name of the chart.
*/}}
{{- define "a2a-server.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "a2a-server.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "a2a-server.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "a2a-server.labels" -}}
helm.sh/chart: {{ include "a2a-server.chart" . }}
{{ include "a2a-server.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "a2a-server.selectorLabels" -}}
app.kubernetes.io/name: {{ include "a2a-server.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "a2a-server.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "a2a-server.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the Redis URL
*/}}
{{- define "a2a-server.redisUrl" -}}
{{- if .Values.redis.enabled }}
{{- printf "redis://%s-redis-master:6379" .Release.Name }}
{{- else }}
{{- if .Values.externalRedis.password }}
{{- printf "redis://:%s@%s:%d/%d" .Values.externalRedis.password .Values.externalRedis.host (.Values.externalRedis.port | int) (.Values.externalRedis.database | int) }}
{{- else }}
{{- printf "redis://%s:%d/%d" .Values.externalRedis.host (.Values.externalRedis.port | int) (.Values.externalRedis.database | int) }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create the image reference
*/}}
{{- define "a2a-server.image" -}}
{{- printf "%s:%s" .Values.image.repository (.Values.image.tag | default .Chart.AppVersion) }}
{{- end }}

{{/*
Common annotations
*/}}
{{- define "a2a-server.annotations" -}}
{{- with .Values.commonAnnotations }}
{{ toYaml . }}
{{- end }}
{{- end }}