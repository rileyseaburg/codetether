{{/* Runtime coordinates for persona workload-identity provisioning. */}}
{{- define "a2a-server.agentIdentityEnv" -}}
{{- if .Values.agentIdentity.enabled }}
- name: AGENT_IDENTITY_NAMESPACE
  value: {{ .Release.Namespace | quote }}
{{- end }}
{{- end }}
