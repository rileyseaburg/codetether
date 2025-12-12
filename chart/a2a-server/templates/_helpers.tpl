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
Blue/Green selector labels

IMPORTANT: These MUST NOT overlap with the legacy Deployment selector labels,
otherwise multiple Deployments/ReplicaSets will match the same Pods.

We achieve this by using a different app.kubernetes.io/name value.
*/}}
{{- define "a2a-server.blueGreenName" -}}
{{- printf "%s-bg" (include "a2a-server.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "a2a-server.blueGreenSelectorLabels" -}}
app.kubernetes.io/name: {{ include "a2a-server.blueGreenName" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Blue/Green common labels
*/}}
{{- define "a2a-server.blueGreenLabels" -}}
helm.sh/chart: {{ include "a2a-server.chart" . }}
{{ include "a2a-server.blueGreenSelectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
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
{{- printf "redis://%s-redis-master:6379" (include "a2a-server.fullname" .) }}
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
Resolve the legacy workload image in blue/green mode.
*/}}
{{- define "a2a-server.legacyImage" -}}
{{- if and .Values.blueGreen.enabled .Values.blueGreen.legacyImage.image }}
{{- .Values.blueGreen.legacyImage.image -}}
{{- else -}}
{{- include "a2a-server.image" . -}}
{{- end -}}
{{- end }}

{{/*
Resolve a per-color image override.

Usage: {{ include "a2a-server.blueGreenImage" (dict "root" . "color" "blue") }}
*/}}
{{- define "a2a-server.blueGreenImage" -}}
{{- $root := .root -}}
{{- $color := .color -}}
{{- $images := ($root.Values.blueGreen.images | default dict) -}}
{{- $cfg := (index $images $color | default dict) -}}
{{- if $cfg.image -}}
{{- $cfg.image -}}
{{- else -}}
{{- include "a2a-server.image" $root -}}
{{- end -}}
{{- end }}

{{/*
Common annotations
*/}}
{{- define "a2a-server.annotations" -}}
{{- with .Values.commonAnnotations }}
{{ toYaml . }}
{{- end }}
{{- end }}
