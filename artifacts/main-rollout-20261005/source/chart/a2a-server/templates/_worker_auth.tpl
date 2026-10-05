{{/*
Zero-trust worker auth wiring for the server container.

a2a-server.workerAuthEnvFrom: envFrom entry exposing WORKER_AUTH_TOKEN from a
Secret (existing one preferred, chart-managed one otherwise). Never the
ConfigMap.

a2a-server.workerAuthEnv: A2A_ALLOW_UNAUTHENTICATED_WORKERS for local/dev.
*/}}
{{- define "a2a-server.workerAuthEnvFrom" -}}
{{- if .Values.workerAuth.existingSecret }}
- secretRef:
    name: {{ .Values.workerAuth.existingSecret }}
{{- else if .Values.workerAuthToken }}
- secretRef:
    name: {{ include "a2a-server.fullname" . }}-worker-auth
{{- end }}
{{- end }}

{{- define "a2a-server.workerAuthEnv" -}}
{{- if .Values.workerAuth.allowUnauthenticated }}
- name: A2A_ALLOW_UNAUTHENTICATED_WORKERS
  value: "true"
{{- end }}
{{- end }}
