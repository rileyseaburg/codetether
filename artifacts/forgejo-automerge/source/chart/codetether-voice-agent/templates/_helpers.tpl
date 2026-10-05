{{- define "codetether-voice-agent.name" -}}
{{- printf "codetether-voice-agent" -}}
{{- end }}

{{- define "codetether-voice-agent.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "codetether-voice-agent.name" .) -}}
{{- end }}

{{- define "codetether-voice-agent.chart" -}}
{{- printf "%s-%s" (include "codetether-voice-agent.name" .) .Chart.Version -}}
{{- end }}

{{- define "codetether-voice-agent.labels" -}}
helm.sh/chart: {{ include "codetether-voice-agent.chart" . }}
{{ include "codetether-voice-agent.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "codetether-voice-agent.selectorLabels" -}}
app.kubernetes.io/name: {{ include "codetether-voice-agent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
