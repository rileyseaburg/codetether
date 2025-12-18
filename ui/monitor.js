// A2A Agent Monitor - Real-time monitoring and intervention
class AgentMonitor {
    constructor() {
        this.messages = [];
        this.agents = new Map();
        this.tasks = [];
        this.codebases = [];  // OpenCode registered codebases
        this.models = [];     // Available AI models
        this.defaultModel = '';
        this.currentTaskFilter = 'all';
        this.eventSource = null;
        this.isPaused = false;
        this.currentFilter = 'all';
        this.totalStoredMessages = 0;
        this.stats = {
            totalMessages: 0,
            interventions: 0,
            toolCalls: 0,
            errors: 0,
            tokens: 0,
            responseTimes: []
        };

        // Agent output tracking
        this.agentOutputStreams = new Map();  // codebase_id -> EventSource
        this.agentOutputs = new Map();        // codebase_id -> output entries array
        this.currentOutputAgent = null;       // Currently selected agent for output view
        this.autoScroll = true;               // Auto-scroll output
        this.streamingParts = new Map();      // part_id -> element for streaming updates

        this.init();
    }

    init() {
        this.connectToServer();
        this.setupEventListeners();
        this.startStatsUpdate();
        this.pollTaskQueue();
        this.fetchTotalMessageCount();
        this.loadModels();       // Load available models
        this.initOpenCode();     // Initialize OpenCode integration
        this.initAgentOutput();  // Initialize agent output panel
    }

    async loadModels() {
        try {
            const serverUrl = this.getServerUrl();
            const response = await fetch(`${serverUrl}/v1/opencode/models`);
            if (response.ok) {
                const data = await response.json();
                this.models = data.models || [];
                this.defaultModel = data.default || '';
                // Re-render codebases to update selectors if they are already shown
                if (this.codebases.length > 0) {
                    this.displayCodebases();
                }
            }
        } catch (error) {
            console.error('Failed to load models:', error);
        }
    }

    renderModelOptions() {
        if (!this.models || this.models.length === 0) {
            return '';
        }

        // Group models by provider
        const byProvider = {};
        this.models.forEach(m => {
            const provider = m.provider || 'Other';
            if (!byProvider[provider]) byProvider[provider] = [];
            byProvider[provider].push(m);
        });

        let html = '';

        // Custom models first
        const customModels = this.models.filter(m => m.custom);
        if (customModels.length > 0) {
            html += '<optgroup label="⭐ Custom (from config)">';
            customModels.forEach(m => {
                const selected = m.id === this.defaultModel ? 'selected' : '';
                const badge = m.capabilities?.reasoning ? ' 🧠' : '';
                html += `<option value="${m.id}" ${selected}>${m.name}${badge}</option>`;
            });
            html += '</optgroup>';
        }

        // Standard providers
        const standardProviders = ['Anthropic', 'OpenAI', 'Google', 'DeepSeek', 'xAI', 'Z.AI Coding Plan', 'Azure AI Foundry'];
        standardProviders.forEach(provider => {
            const models = (byProvider[provider] || []).filter(m => !m.custom);
            if (models.length > 0) {
                html += `<optgroup label="${provider}">`;
                models.forEach(m => {
                    const selected = m.id === this.defaultModel ? 'selected' : '';
                    html += `<option value="${m.id}" ${selected}>${m.name}</option>`;
                });
                html += '</optgroup>';
            }
        });

        // Other providers
        Object.keys(byProvider).forEach(provider => {
            if (!standardProviders.includes(provider) && provider !== 'Other') {
                const models = byProvider[provider].filter(m => !m.custom);
                if (models.length > 0) {
                    html += `<optgroup label="${provider}">`;
                    models.forEach(m => {
                        const selected = m.id === this.defaultModel ? 'selected' : '';
                        html += `<option value="${m.id}" ${selected}>${m.name}</option>`;
                    });
                    html += '</optgroup>';
                }
            }
        });

        return html;
    }

    // ========================================
    // Agent Output Panel
    // ========================================

    initAgentOutput() {
        // Update agent selector when codebases change
        this.updateAgentOutputSelector();
    }

    updateAgentOutputSelector() {
        const select = document.getElementById('outputAgentSelect');
        if (!select) return;

        const currentValue = select.value;
        select.innerHTML = '<option value="">Select an agent to view output...</option>';

        this.codebases.forEach(cb => {
            const option = document.createElement('option');
            option.value = cb.id;
            option.textContent = `${cb.name} (${cb.status})`;
            if (cb.status === 'busy' || cb.status === 'running') {
                option.textContent += ' 🟢';
            }
            select.appendChild(option);
        });

        // Restore selection if still valid
        if (currentValue && this.codebases.find(cb => cb.id === currentValue)) {
            select.value = currentValue;
        }
    }

    switchAgentOutput() {
        const select = document.getElementById('outputAgentSelect');
        const codebaseId = select.value;

        if (!codebaseId) {
            this.currentOutputAgent = null;
            this.displayAgentOutput(null);
            return;
        }

        this.currentOutputAgent = codebaseId;

        // Initialize output array if needed
        if (!this.agentOutputs.has(codebaseId)) {
            this.agentOutputs.set(codebaseId, []);
        }

        // Connect to event stream if not already connected
        if (!this.agentOutputStreams.has(codebaseId)) {
            this.connectAgentEventStream(codebaseId);
        }

        // Display existing output
        this.displayAgentOutput(codebaseId);

        // Load existing messages
        this.loadAgentMessages(codebaseId);
    }

    async connectAgentEventStream(codebaseId) {
        const serverUrl = this.getServerUrl();
        const eventSource = new EventSource(`${serverUrl}/v1/opencode/codebases/${codebaseId}/events`);

        this.agentOutputStreams.set(codebaseId, eventSource);

        eventSource.onopen = () => {
            console.log(`Connected to event stream for ${codebaseId}`);
            this.addOutputEntry(codebaseId, {
                type: 'status',
                content: 'Connected to agent event stream',
                timestamp: new Date().toISOString()
            });
        };

        eventSource.onerror = (error) => {
            console.error(`Event stream error for ${codebaseId}:`, error);
            if (eventSource.readyState === EventSource.CLOSED) {
                this.agentOutputStreams.delete(codebaseId);
                this.addOutputEntry(codebaseId, {
                    type: 'status',
                    content: 'Disconnected from agent event stream',
                    timestamp: new Date().toISOString()
                });
            }
        };

        // Handle different event types
        eventSource.addEventListener('connected', (e) => {
            const data = JSON.parse(e.data);
            this.addOutputEntry(codebaseId, {
                type: 'status',
                content: `Connected to agent (${data.codebase_id})`,
                timestamp: new Date().toISOString()
            });
        });

        eventSource.addEventListener('part.text', (e) => {
            this.handleTextPart(codebaseId, JSON.parse(e.data));
        });

        eventSource.addEventListener('part.reasoning', (e) => {
            this.handleReasoningPart(codebaseId, JSON.parse(e.data));
        });

        eventSource.addEventListener('part.tool', (e) => {
            this.handleToolPart(codebaseId, JSON.parse(e.data));
        });

        eventSource.addEventListener('part.step-start', (e) => {
            const data = JSON.parse(e.data);
            this.addOutputEntry(codebaseId, {
                type: 'step-start',
                content: 'Step started',
                timestamp: new Date().toISOString()
            });
        });

        eventSource.addEventListener('part.step-finish', (e) => {
            const data = JSON.parse(e.data);
            this.addOutputEntry(codebaseId, {
                type: 'step-finish',
                content: `Step finished: ${data.reason || 'complete'}`,
                tokens: data.tokens,
                cost: data.cost,
                timestamp: new Date().toISOString()
            });
        });

        eventSource.addEventListener('status', (e) => {
            const data = JSON.parse(e.data);
            this.addOutputEntry(codebaseId, {
                type: 'status',
                content: `Status: ${data.status}${data.agent ? ` (${data.agent})` : ''}${data.message ? ` - ${data.message}` : ''}`,
                timestamp: new Date().toISOString()
            });
            // Update codebase status
            this.loadCodebases();
        });

        // Handle message events from remote workers (task results)
        eventSource.addEventListener('message', (e) => {
            const data = JSON.parse(e.data);
            // Parse nested JSON if content is a string containing JSON events
            if (data.type === 'text' && data.content) {
                try {
                    // Content may be newline-separated JSON events from OpenCode
                    const lines = data.content.split('\n').filter(l => l.trim());
                    for (const line of lines) {
                        const event = JSON.parse(line);
                        this.processOpenCodeEvent(codebaseId, event);
                    }
                } catch {
                    // Not JSON, show as plain text
                    this.addOutputEntry(codebaseId, {
                        type: 'text',
                        content: data.content,
                        timestamp: new Date().toISOString()
                    });
                }
            } else if (data.type) {
                this.processOpenCodeEvent(codebaseId, data);
            }
        });

        eventSource.addEventListener('idle', (e) => {
            this.addOutputEntry(codebaseId, {
                type: 'status',
                content: 'Agent is now idle',
                timestamp: new Date().toISOString()
            });
            this.loadCodebases();
        });

        eventSource.addEventListener('file_edit', (e) => {
            const data = JSON.parse(e.data);
            this.addOutputEntry(codebaseId, {
                type: 'file-edit',
                content: `File edited: ${data.path}`,
                timestamp: new Date().toISOString()
            });
        });

        eventSource.addEventListener('command', (e) => {
            const data = JSON.parse(e.data);
            this.addOutputEntry(codebaseId, {
                type: 'command',
                content: `Command: ${data.command}`,
                output: data.output,
                exitCode: data.exit_code,
                timestamp: new Date().toISOString()
            });
        });

        eventSource.addEventListener('diagnostics', (e) => {
            const data = JSON.parse(e.data);
            if (data.diagnostics && data.diagnostics.length > 0) {
                this.addOutputEntry(codebaseId, {
                    type: 'diagnostics',
                    content: `Diagnostics for ${data.path}: ${data.diagnostics.length} issues`,
                    diagnostics: data.diagnostics,
                    timestamp: new Date().toISOString()
                });
            }
        });

        eventSource.addEventListener('message', (e) => {
            const data = JSON.parse(e.data);
            // Message metadata update
            if (data.tokens) {
                this.stats.tokens += (data.tokens.input || 0) + (data.tokens.output || 0);
                this.updateStatsDisplay();
            }
        });

        eventSource.addEventListener('error', (e) => {
            // Only parse if we have data (SSE error event vs connection error)
            if (e.data) {
                try {
                    const data = JSON.parse(e.data);
                    this.addOutputEntry(codebaseId, {
                        type: 'error',
                        content: `Error: ${data.error}`,
                        timestamp: new Date().toISOString()
                    });
                } catch (parseErr) {
                    console.warn('Could not parse error data:', e.data);
                }
            }
        });
    }

    processOpenCodeEvent(codebaseId, event) {
        // Process OpenCode event format from task results
        const type = event.type;
        const part = event.part || {};

        switch (type) {
            case 'text':
                if (part.text) {
                    this.addOutputEntry(codebaseId, {
                        type: 'text',
                        content: part.text,
                        timestamp: new Date().toISOString()
                    });
                }
                break;
            case 'tool_use':
                if (part.tool) {
                    const state = part.state || {};
                    this.addOutputEntry(codebaseId, {
                        type: 'tool',
                        tool: part.tool,
                        status: state.status || 'completed',
                        title: state.title || state.input?.description || part.tool,
                        input: state.input,
                        output: state.output || state.metadata?.output,
                        timestamp: new Date().toISOString()
                    });
                }
                break;
            case 'step_start':
                this.addOutputEntry(codebaseId, {
                    type: 'step-start',
                    content: 'Step started',
                    timestamp: new Date().toISOString()
                });
                break;
            case 'step_finish':
                this.addOutputEntry(codebaseId, {
                    type: 'step-finish',
                    content: `Step finished: ${part.reason || 'complete'}`,
                    tokens: part.tokens,
                    cost: part.cost,
                    timestamp: new Date().toISOString()
                });
                break;
            default:
                // Unknown event type, show raw if it has content
                if (part.text || event.content) {
                    this.addOutputEntry(codebaseId, {
                        type: 'info',
                        content: part.text || event.content,
                        timestamp: new Date().toISOString()
                    });
                }
        }
    }

    handleTextPart(codebaseId, data) {
        const partId = data.part_id;

        if (data.delta) {
            // Streaming update - append to existing entry
            let entry = this.getStreamingEntry(codebaseId, partId);
            if (entry) {
                entry.content += data.delta;
                this.updateStreamingElement(partId, entry.content);
            } else {
                // First chunk
                entry = {
                    id: partId,
                    type: 'text',
                    content: data.delta,
                    streaming: true,
                    timestamp: new Date().toISOString()
                };
                this.addOutputEntry(codebaseId, entry, true);
            }
        } else if (data.text) {
            // Complete text
            const existingEntry = this.getStreamingEntry(codebaseId, partId);
            if (existingEntry) {
                existingEntry.content = data.text;
                existingEntry.streaming = false;
                this.updateStreamingElement(partId, data.text, false);
            } else {
                this.addOutputEntry(codebaseId, {
                    id: partId,
                    type: 'text',
                    content: data.text,
                    timestamp: new Date().toISOString()
                });
            }
        }
    }

    handleReasoningPart(codebaseId, data) {
        const partId = data.part_id;

        if (data.delta) {
            let entry = this.getStreamingEntry(codebaseId, partId);
            if (entry) {
                entry.content += data.delta;
                this.updateStreamingElement(partId, entry.content);
            } else {
                entry = {
                    id: partId,
                    type: 'reasoning',
                    content: data.delta,
                    streaming: true,
                    timestamp: new Date().toISOString()
                };
                this.addOutputEntry(codebaseId, entry, true);
            }
        } else if (data.text) {
            const existingEntry = this.getStreamingEntry(codebaseId, partId);
            if (existingEntry) {
                existingEntry.content = data.text;
                existingEntry.streaming = false;
                this.updateStreamingElement(partId, data.text, false);
            } else {
                this.addOutputEntry(codebaseId, {
                    id: partId,
                    type: 'reasoning',
                    content: data.text,
                    timestamp: new Date().toISOString()
                });
            }
        }
    }

    handleToolPart(codebaseId, data) {
        const partId = data.part_id;
        const status = data.status;

        // Find or create tool entry
        let outputs = this.agentOutputs.get(codebaseId) || [];
        let entry = outputs.find(e => e.id === partId);

        if (!entry) {
            entry = {
                id: partId,
                type: `tool-${status}`,
                toolName: data.tool_name,
                callId: data.call_id,
                input: data.input,
                output: null,
                error: null,
                title: data.title,
                status: status,
                timestamp: new Date().toISOString()
            };
            this.addOutputEntry(codebaseId, entry);
        } else {
            // Update existing entry
            entry.type = `tool-${status}`;
            entry.status = status;
            entry.title = data.title || entry.title;
            if (data.output) entry.output = data.output;
            if (data.error) entry.error = data.error;
            if (data.metadata) entry.metadata = data.metadata;

            // Update display
            this.updateToolElement(partId, entry);
        }

        // Update stats
        if (status === 'completed' || status === 'error') {
            this.stats.toolCalls++;
            if (status === 'error') this.stats.errors++;
            this.updateStatsDisplay();
        }
    }

    getStreamingEntry(codebaseId, partId) {
        const outputs = this.agentOutputs.get(codebaseId);
        if (!outputs) return null;
        return outputs.find(e => e.id === partId && e.streaming);
    }

    addOutputEntry(codebaseId, entry, isStreaming = false) {
        if (!this.agentOutputs.has(codebaseId)) {
            this.agentOutputs.set(codebaseId, []);
        }

        const outputs = this.agentOutputs.get(codebaseId);

        // Avoid duplicates
        if (entry.id && outputs.find(e => e.id === entry.id)) {
            return;
        }

        outputs.push(entry);

        // Limit stored entries
        if (outputs.length > 500) {
            outputs.shift();
        }

        // Display if this is the current agent
        if (codebaseId === this.currentOutputAgent) {
            this.renderOutputEntry(entry, isStreaming);
        }
    }

    displayAgentOutput(codebaseId) {
        const container = document.getElementById('agentOutputContainer');
        const noOutputMsg = document.getElementById('noOutputMessage');

        if (!codebaseId) {
            container.innerHTML = '';
            container.appendChild(noOutputMsg);
            noOutputMsg.style.display = 'block';
            return;
        }

        const outputs = this.agentOutputs.get(codebaseId) || [];

        if (outputs.length === 0) {
            container.innerHTML = '';
            const emptyMsg = noOutputMsg.cloneNode(true);
            emptyMsg.style.display = 'block';
            container.appendChild(emptyMsg);
            return;
        }

        noOutputMsg.style.display = 'none';
        container.innerHTML = '';
        this.streamingParts.clear();

        outputs.forEach(entry => this.renderOutputEntry(entry, entry.streaming));
    }

    renderOutputEntry(entry, isStreaming = false) {
        const container = document.getElementById('agentOutputContainer');
        const noOutputMsg = document.getElementById('noOutputMessage');
        if (noOutputMsg) noOutputMsg.style.display = 'none';

        const el = document.createElement('div');
        el.className = `output-entry ${entry.type}`;
        el.dataset.entryId = entry.id || Date.now();

        const timeStr = entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : '';

        let html = `<div class="output-meta"><span>${this.getEntryTypeLabel(entry.type)}</span><span>${timeStr}</span></div>`;

        if (entry.type.startsWith('tool-')) {
            html += this.renderToolEntry(entry);
        } else if (entry.type === 'step-finish') {
            html += `<div class="output-content">${this.escapeHtml(entry.content)}</div>`;
            if (entry.tokens) {
                html += `<div class="tokens-badge">Tokens: ${entry.tokens.input || 0} in / ${entry.tokens.output || 0} out</div>`;
            }
            if (entry.cost) {
                html += `<span class="tokens-badge cost-badge">Cost: $${entry.cost.toFixed(4)}</span>`;
            }
        } else if (entry.type === 'command') {
            html += `<div class="output-content">${this.escapeHtml(entry.content)}</div>`;
            if (entry.output) {
                html += `<div class="tool-output"><pre>${this.escapeHtml(entry.output)}</pre></div>`;
            }
            if (entry.exitCode !== undefined) {
                html += `<div class="tokens-badge">Exit code: ${entry.exitCode}</div>`;
            }
        } else {
            const contentClass = isStreaming ? 'output-content streaming' : 'output-content';
            html += `<div class="${contentClass}" data-part-id="${entry.id || ''}">${this.escapeHtml(entry.content || '')}</div>`;
        }

        el.innerHTML = html;
        container.appendChild(el);

        // Track streaming elements
        if (isStreaming && entry.id) {
            this.streamingParts.set(entry.id, el);
        }

        // Auto-scroll
        if (this.autoScroll) {
            container.scrollTop = container.scrollHeight;
        }
    }

    renderToolEntry(entry) {
        let html = `<div class="tool-title">🔧 ${entry.toolName || 'Unknown Tool'}</div>`;
        html += `<div class="output-content">${entry.title || entry.status}</div>`;

        if (entry.input && Object.keys(entry.input).length > 0) {
            html += `<div class="tool-input"><strong>Input:</strong><pre>${this.formatJson(entry.input)}</pre></div>`;
        }

        if (entry.output) {
            html += `<div class="tool-output"><strong>Output:</strong><pre>${this.escapeHtml(this.truncateString(entry.output, 2000))}</pre></div>`;
        }

        if (entry.error) {
            html += `<div class="tool-output error"><strong>Error:</strong><pre>${this.escapeHtml(entry.error)}</pre></div>`;
        }

        return html;
    }

    updateStreamingElement(partId, content, isStreaming = true) {
        const el = this.streamingParts.get(partId);
        if (!el) return;

        const contentEl = el.querySelector(`[data-part-id="${partId}"]`);
        if (contentEl) {
            contentEl.textContent = content;
            if (!isStreaming) {
                contentEl.classList.remove('streaming');
            }
        }

        // Auto-scroll
        if (this.autoScroll) {
            const container = document.getElementById('agentOutputContainer');
            container.scrollTop = container.scrollHeight;
        }
    }

    updateToolElement(partId, entry) {
        const container = document.getElementById('agentOutputContainer');
        const el = container.querySelector(`[data-entry-id="${partId}"]`);
        if (!el) return;

        el.className = `output-entry ${entry.type}`;

        const timeStr = entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : '';
        let html = `<div class="output-meta"><span>${this.getEntryTypeLabel(entry.type)}</span><span>${timeStr}</span></div>`;
        html += this.renderToolEntry(entry);

        el.innerHTML = html;
    }

    getEntryTypeLabel(type) {
        const labels = {
            'text': '💬 Text',
            'reasoning': '🧠 Reasoning',
            'tool-pending': '⏳ Tool Pending',
            'tool-running': '🔄 Tool Running',
            'tool-completed': '✅ Tool Completed',
            'tool-error': '❌ Tool Error',
            'step-start': '▶️ Step Start',
            'step-finish': '⏹️ Step Finish',
            'file-edit': '📝 File Edit',
            'command': '💻 Command',
            'status': 'ℹ️ Status',
            'diagnostics': '🔍 Diagnostics',
            'error': '❌ Error'
        };
        return labels[type] || type;
    }

    async loadAgentMessages(codebaseId) {
        try {
            const serverUrl = this.getServerUrl();
            const response = await fetch(`${serverUrl}/v1/opencode/codebases/${codebaseId}/messages?limit=50`);
            if (response.ok) {
                const data = await response.json();
                // Process historical messages
                if (data.messages && data.messages.length > 0) {
                    this.processHistoricalMessages(codebaseId, data.messages);
                }
            }
        } catch (error) {
            console.error('Failed to load agent messages:', error);
        }
    }

    processHistoricalMessages(codebaseId, messages) {
        // Process messages and their parts
        messages.forEach(msg => {
            if (msg.parts) {
                msg.parts.forEach(part => {
                    if (part.type === 'text') {
                        this.addOutputEntry(codebaseId, {
                            id: part.id,
                            type: 'text',
                            content: part.text,
                            timestamp: msg.info?.time?.created ? new Date(msg.info.time.created * 1000).toISOString() : new Date().toISOString()
                        });
                    } else if (part.type === 'tool') {
                        const status = part.state?.status || 'pending';
                        this.addOutputEntry(codebaseId, {
                            id: part.id,
                            type: `tool-${status}`,
                            toolName: part.tool,
                            callId: part.callID,
                            input: part.state?.input,
                            output: part.state?.output,
                            error: part.state?.error,
                            title: part.state?.title,
                            status: status,
                            timestamp: new Date().toISOString()
                        });
                    }
                });
            }
        });

        // Re-display if current agent
        if (codebaseId === this.currentOutputAgent) {
            this.displayAgentOutput(codebaseId);
        }
    }

    truncateString(str, maxLen) {
        if (!str) return '';
        if (str.length <= maxLen) return str;
        return str.substring(0, maxLen) + '\n... (truncated)';
    }

    formatJson(obj) {
        try {
            return JSON.stringify(obj, null, 2);
        } catch {
            return String(obj);
        }
    }

    toggleAutoScroll() {
        this.autoScroll = !this.autoScroll;
        const btn = document.getElementById('btnAutoScroll');
        if (btn) {
            btn.classList.toggle('active', this.autoScroll);
        }
    }

    clearAgentOutput() {
        if (this.currentOutputAgent) {
            this.agentOutputs.set(this.currentOutputAgent, []);
            this.displayAgentOutput(this.currentOutputAgent);
        }
    }

    downloadAgentOutput() {
        if (!this.currentOutputAgent) return;

        const outputs = this.agentOutputs.get(this.currentOutputAgent) || [];
        const codebase = this.codebases.find(cb => cb.id === this.currentOutputAgent);
        const filename = `agent-output-${codebase?.name || this.currentOutputAgent}-${new Date().toISOString().slice(0, 10)}.json`;

        const blob = new Blob([JSON.stringify(outputs, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }

    disconnectAgentEventStream(codebaseId) {
        const eventSource = this.agentOutputStreams.get(codebaseId);
        if (eventSource) {
            eventSource.close();
            this.agentOutputStreams.delete(codebaseId);
        }
    }

    // ========================================
    // OpenCode Integration
    // ========================================

    async initOpenCode() {
        await this.checkOpenCodeStatus();
        await this.loadCodebases();
        this.setupOpenCodeEventListeners();
        // Poll codebases every 10 seconds
        setInterval(() => this.loadCodebases(), 10000);
    }

    async checkOpenCodeStatus() {
        try {
            const serverUrl = this.getServerUrl();
            const response = await fetch(`${serverUrl}/v1/opencode/status`);
            const status = await response.json();

            const statusEl = document.getElementById('opencodeStatus');
            if (status.available) {
                statusEl.innerHTML = `✅ OpenCode ready | Binary: <code>${status.opencode_binary}</code>`;
                statusEl.style.background = '#d4edda';
            } else {
                statusEl.innerHTML = `⚠️ ${status.message}`;
                statusEl.style.background = '#fff3cd';
            }
        } catch (error) {
            console.error('Failed to check OpenCode status:', error);
            const statusEl = document.getElementById('opencodeStatus');
            statusEl.innerHTML = '❌ OpenCode integration unavailable';
            statusEl.style.background = '#f8d7da';
        }
    }

    async loadCodebases() {
        try {
            const serverUrl = this.getServerUrl();
            const response = await fetch(`${serverUrl}/v1/opencode/codebases`);
            if (response.ok) {
                this.codebases = await response.json();
                this.displayCodebases();
                this.updateAgentOutputSelector();  // Update agent output selector
            }
        } catch (error) {
            console.error('Failed to load codebases:', error);
        }
    }

    displayCodebases() {
        const container = document.getElementById('codebasesContainer');
        const noCodebasesMsg = document.getElementById('noCodebasesMessage');

        if (this.codebases.length === 0) {
            noCodebasesMsg.style.display = 'block';
            return;
        }

        noCodebasesMsg.style.display = 'none';

        // Keep existing codebases, update or add new ones
        const existingIds = new Set();
        this.codebases.forEach(cb => {
            existingIds.add(cb.id);
            let el = container.querySelector(`[data-codebase-id="${cb.id}"]`);

            if (!el) {
                el = this.createCodebaseElement(cb);
                container.appendChild(el);
            } else {
                this.updateCodebaseElement(el, cb);
            }
        });

        // Remove codebases that no longer exist
        container.querySelectorAll('.codebase-item').forEach(el => {
            if (!existingIds.has(el.dataset.codebaseId)) {
                el.remove();
            }
        });
    }

    createCodebaseElement(codebase) {
        const el = document.createElement('div');
        const isWatching = codebase.status === 'watching';
        el.className = `codebase-item ${codebase.status}${isWatching ? ' watching' : ''}`;
        el.dataset.codebaseId = codebase.id;

        // Get pending tasks for this codebase
        const pendingTasks = this.tasks.filter(t => t.codebase_id === codebase.id && t.status === 'pending').length;
        const workingTasks = this.tasks.filter(t => t.codebase_id === codebase.id && t.status === 'working').length;

        el.innerHTML = `
            <div class="codebase-header">
                <div>
                    <div class="codebase-name">${this.escapeHtml(codebase.name)}</div>
                    <div class="codebase-path">${this.escapeHtml(codebase.path)}</div>
                    ${codebase.description ? `<div style="font-size: 0.9em; color: #6c757d; margin-top: 5px;">${this.escapeHtml(codebase.description)}</div>` : ''}
                </div>
                <span class="codebase-status ${codebase.status}${isWatching ? ' watching' : ''}">${isWatching ? '👁️ watching' : codebase.status}</span>
            </div>

            <div class="codebase-tasks">
                ${pendingTasks > 0 ? `<span class="task-badge pending">⏳ ${pendingTasks} pending</span>` : ''}
                ${workingTasks > 0 ? `<span class="task-badge working">🔄 ${workingTasks} working</span>` : ''}
            </div>

            <div class="watch-controls">
                ${isWatching ? `
                    <div class="watch-indicator active">
                        <span class="watch-dot"></span>
                        <span>Watching for tasks...</span>
                    </div>
                    <button class="btn-secondary btn-small" onclick="stopWatchMode('${codebase.id}')">⏹️ Stop Watch</button>
                ` : `
                    <button class="btn-secondary btn-small" onclick="startWatchMode('${codebase.id}')" title="Start watch mode to auto-process queued tasks">👁️ Start Watch Mode</button>
                `}
            </div>

            <div class="codebase-actions">
                <button class="btn-primary" onclick="monitor.showTriggerForm('${codebase.id}')">🎯 Trigger Agent</button>
                <button class="btn-secondary" onclick="openTaskModal('${codebase.id}')">📋 Add Task</button>
                <button class="btn-secondary" onclick="openAgentOutputModal('${codebase.id}')">👁️ Output</button>
                <button class="btn-secondary" onclick="monitor.viewCodebaseStatus('${codebase.id}')">📊 Status</button>
                <button class="btn-secondary" onclick="monitor.unregisterCodebase('${codebase.id}')" style="color: #dc3545;">🗑️</button>
            </div>

            <div class="trigger-form" id="trigger-form-${codebase.id}">
                <textarea id="trigger-prompt-${codebase.id}" placeholder="Enter your prompt for the AI agent..."></textarea>
                <select id="trigger-agent-${codebase.id}">
                    <option value="build">🔧 Build (Full access agent)</option>
                    <option value="plan">📋 Plan (Read-only analysis)</option>
                    <option value="general">🔄 General (Multi-step tasks)</option>
                    <option value="explore">🔍 Explore (Codebase search)</option>
                </select>
                <select id="trigger-model-${codebase.id}" class="model-selector">
                    <option value="">🤖 Default Model</option>
                    ${this.renderModelOptions()}
                </select>
                <div style="display: flex; gap: 10px;">
                    <button class="btn-primary" onclick="monitor.triggerAgent('${codebase.id}')" style="flex: 1;">🚀 Start Agent</button>
                    <button class="btn-secondary" onclick="monitor.hideTriggerForm('${codebase.id}')" style="flex: 1;">Cancel</button>
                </div>
            </div>
        `;

        return el;
    }

    updateCodebaseElement(el, codebase) {
        // Update status badge
        const statusEl = el.querySelector('.codebase-status');
        statusEl.textContent = codebase.status;
        statusEl.className = `codebase-status ${codebase.status}`;

        // Update item class for styling
        el.className = `codebase-item ${codebase.status}`;
    }

    showTriggerForm(codebaseId) {
        const form = document.getElementById(`trigger-form-${codebaseId}`);
        if (form) {
            form.classList.add('show');
            document.getElementById(`trigger-prompt-${codebaseId}`).focus();
        }
    }

    hideTriggerForm(codebaseId) {
        const form = document.getElementById(`trigger-form-${codebaseId}`);
        if (form) {
            form.classList.remove('show');
        }
    }

    async triggerAgent(codebaseId) {
        const prompt = document.getElementById(`trigger-prompt-${codebaseId}`).value;
        const agent = document.getElementById(`trigger-agent-${codebaseId}`).value;
        const model = document.getElementById(`trigger-model-${codebaseId}`).value;

        if (!prompt.trim()) {
            this.showToast('Please enter a prompt', 'error');
            return;
        }

        try {
            const serverUrl = this.getServerUrl();
            const payload = {
                prompt: prompt,
                agent: agent,
            };
            if (model) {
                payload.model = model;
            }
            const response = await fetch(`${serverUrl}/v1/opencode/codebases/${codebaseId}/trigger`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const result = await response.json();

            if (result.success) {
                this.showToast(`Agent '${agent}' triggered successfully!`, 'success');
                this.hideTriggerForm(codebaseId);
                document.getElementById(`trigger-prompt-${codebaseId}`).value = '';
                await this.loadCodebases();
            } else {
                this.showToast(`Failed: ${result.error}`, 'error');
            }
        } catch (error) {
            console.error('Failed to trigger agent:', error);
            this.showToast('Failed to trigger agent', 'error');
        }
    }

    async viewCodebaseStatus(codebaseId) {
        try {
            const serverUrl = this.getServerUrl();
            const response = await fetch(`${serverUrl}/v1/opencode/codebases/${codebaseId}/status`);
            const status = await response.json();

            const modal = document.createElement('div');
            modal.className = 'task-detail-modal show';
            modal.innerHTML = `
                <div class="modal-content">
                    <div class="modal-header">
                        <h2>${this.escapeHtml(status.name)}</h2>
                        <button class="close-modal" onclick="this.closest('.task-detail-modal').remove()">×</button>
                    </div>
                    <div class="codebase-status ${status.status}" style="margin-bottom: 15px;">${status.status}</div>

                    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                        <div><strong>Path:</strong> <code>${this.escapeHtml(status.path)}</code></div>
                        <div><strong>Registered:</strong> ${new Date(status.registered_at).toLocaleString()}</div>
                        ${status.last_triggered ? `<div><strong>Last Triggered:</strong> ${new Date(status.last_triggered).toLocaleString()}</div>` : ''}
                        ${status.session_id ? `<div><strong>Session ID:</strong> <code>${status.session_id}</code></div>` : ''}
                        ${status.opencode_port ? `<div><strong>OpenCode Port:</strong> ${status.opencode_port}</div>` : ''}
                    </div>

                    ${status.recent_messages ? `
                        <h3>Recent Messages</h3>
                        <div style="max-height: 300px; overflow-y: auto;">
                            ${status.recent_messages.map(msg => `
                                <div style="padding: 10px; margin: 5px 0; background: #e9ecef; border-radius: 8px;">
                                    ${this.escapeHtml(msg.content || JSON.stringify(msg))}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}

                    <div style="display: flex; gap: 10px; margin-top: 20px;">
                        ${status.status === 'busy' ? `
                            <button class="btn-secondary" onclick="monitor.interruptAgent('${codebaseId}'); this.closest('.task-detail-modal').remove();">
                                ⏹️ Interrupt
                            </button>
                        ` : ''}
                        ${status.status === 'running' || status.status === 'busy' ? `
                            <button class="btn-secondary" onclick="monitor.stopAgent('${codebaseId}'); this.closest('.task-detail-modal').remove();">
                                🛑 Stop Agent
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
        } catch (error) {
            console.error('Failed to get codebase status:', error);
            this.showToast('Failed to get status', 'error');
        }
    }

    async interruptAgent(codebaseId) {
        try {
            const serverUrl = this.getServerUrl();
            const response = await fetch(`${serverUrl}/v1/opencode/codebases/${codebaseId}/interrupt`, {
                method: 'POST'
            });
            const result = await response.json();

            if (result.success) {
                this.showToast('Agent interrupted', 'success');
                await this.loadCodebases();
            } else {
                this.showToast('Failed to interrupt agent', 'error');
            }
        } catch (error) {
            console.error('Failed to interrupt agent:', error);
            this.showToast('Failed to interrupt agent', 'error');
        }
    }

    async stopAgent(codebaseId) {
        try {
            const serverUrl = this.getServerUrl();
            const response = await fetch(`${serverUrl}/v1/opencode/codebases/${codebaseId}/stop`, {
                method: 'POST'
            });
            const result = await response.json();

            if (result.success) {
                this.showToast('Agent stopped', 'success');
                await this.loadCodebases();
            } else {
                this.showToast('Failed to stop agent', 'error');
            }
        } catch (error) {
            console.error('Failed to stop agent:', error);
            this.showToast('Failed to stop agent', 'error');
        }
    }

    async unregisterCodebase(codebaseId) {
        if (!confirm('Are you sure you want to unregister this codebase?')) {
            return;
        }

        try {
            const serverUrl = this.getServerUrl();
            const response = await fetch(`${serverUrl}/v1/opencode/codebases/${codebaseId}`, {
                method: 'DELETE'
            });
            const result = await response.json();

            if (result.success) {
                this.showToast('Codebase unregistered', 'success');
                await this.loadCodebases();
            } else {
                this.showToast('Failed to unregister', 'error');
            }
        } catch (error) {
            console.error('Failed to unregister codebase:', error);
            this.showToast('Failed to unregister', 'error');
        }
    }

    setupOpenCodeEventListeners() {
        // Register codebase modal
        window.openRegisterModal = () => {
            document.getElementById('registerCodebaseModal').classList.add('show');
            document.getElementById('codebaseName').focus();
        };

        window.closeRegisterModal = () => {
            document.getElementById('registerCodebaseModal').classList.remove('show');
        };

        window.registerCodebase = async (event) => {
            event.preventDefault();

            const name = document.getElementById('codebaseName').value;
            const path = document.getElementById('codebasePath').value;
            const description = document.getElementById('codebaseDescription').value;

            try {
                const serverUrl = this.getServerUrl();
                const response = await fetch(`${serverUrl}/v1/opencode/codebases`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, path, description })
                });

                const result = await response.json();

                if (result.success) {
                    this.showToast('Codebase registered!', 'success');
                    closeRegisterModal();
                    document.getElementById('codebaseName').value = '';
                    document.getElementById('codebasePath').value = '';
                    document.getElementById('codebaseDescription').value = '';
                    await this.loadCodebases();
                } else {
                    this.showToast(`Failed: ${result.detail || 'Unknown error'}`, 'error');
                }
            } catch (error) {
                console.error('Failed to register codebase:', error);
                this.showToast('Failed to register codebase', 'error');
            }
        };

        // Close modal on outside click
        document.getElementById('registerCodebaseModal').onclick = (e) => {
            if (e.target.id === 'registerCodebaseModal') {
                closeRegisterModal();
            }
        };
    }

    // ========================================
    // End OpenCode Integration
    // ========================================

    async fetchTotalMessageCount() {
        try {
            const serverUrl = this.getServerUrl();
            const response = await fetch(`${serverUrl}/v1/monitor/messages/count`);
            if (response.ok) {
                const data = await response.json();
                this.totalStoredMessages = data.total;
                document.getElementById('totalStoredMessages').textContent = this.formatNumber(data.total);
            }
        } catch (error) {
            console.error('Failed to fetch total message count:', error);
        }

        // Refresh count every 30 seconds
        setTimeout(() => this.fetchTotalMessageCount(), 30000);
    }

    formatNumber(num) {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
        return num.toString();
    }

    connectToServer() {
        const serverUrl = this.getServerUrl();

        // Close existing connection if any
        if (this.eventSource) {
            this.eventSource.close();
        }

        console.log('Connecting to A2A server:', serverUrl);

        // Connect to SSE endpoint for real-time updates
        this.eventSource = new EventSource(`${serverUrl}/v1/monitor/stream`);

        this.eventSource.onopen = () => {
            console.log('✓ Connected to A2A server - Real-time monitoring active');
            this.updateConnectionStatus(true);
            this.showToast('Connected to A2A server', 'success');
        };

        this.eventSource.onerror = (error) => {
            console.error('SSE connection error:', error);
            this.updateConnectionStatus(false);

            // EventSource will automatically reconnect, but we'll add a fallback
            if (this.eventSource.readyState === EventSource.CLOSED) {
                console.log('Connection closed, reconnecting in 3 seconds...');
                setTimeout(() => this.connectToServer(), 3000);
            }
        };

        this.eventSource.addEventListener('message', (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        });

        this.eventSource.addEventListener('agent_status', (event) => {
            const data = JSON.parse(event.data);
            this.updateAgentStatus(data);
        });

        this.eventSource.addEventListener('stats', (event) => {
            const data = JSON.parse(event.data);
            this.updateStats(data);
        });

        // Keep connection alive with periodic heartbeat
        this.startHeartbeat();

        // Also poll for agent list
        this.pollAgentList();
    }

    async pollTaskQueue() {
        // Don't poll if paused
        if (this.isPaused) {
            setTimeout(() => this.pollTaskQueue(), 5000);
            return;
        }

        try {
            // For MCP endpoints, we need to try port 9000 if not on the same port
            let mcpServerUrl = this.getServerUrl();
            const currentPort = window.location.port;

            // If we're on the main A2A server port, try MCP server on 9000
            if (currentPort === '8000' || currentPort === '') {
                mcpServerUrl = mcpServerUrl.replace(':8000', ':9000');
            }

            const response = await fetch(`${mcpServerUrl}/mcp/v1/tasks`);
            if (response.ok) {
                const data = await response.json();
                this.tasks = data.tasks || [];
                this.displayTasks();
            } else {
                console.warn(`Failed to fetch tasks from ${mcpServerUrl}/mcp/v1/tasks (status: ${response.status})`);
            }
        } catch (error) {
            console.error('Failed to fetch task queue:', error);
        }

        // Poll every 5 seconds for task updates
        setTimeout(() => this.pollTaskQueue(), 5000);
    }

    displayTasks() {
        const container = document.getElementById('tasksContainer');

        // Filter tasks based on current filter
        let filteredTasks = this.tasks.map(task => this.normalizeTask(task));
        if (this.currentTaskFilter !== 'all') {
            filteredTasks = filteredTasks.filter(task => task.status === this.currentTaskFilter);
        }

        if (filteredTasks.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <p>No tasks in queue</p>
                </div>
            `;
            return;
        }

        container.innerHTML = '';
        filteredTasks.forEach(task => {
            const taskEl = this.createTaskElement(task);
            container.appendChild(taskEl);
        });
    }

    createTaskElement(task) {
        const normalizedTask = this.normalizeTask(task);
        const taskEl = document.createElement('div');
        taskEl.className = `task-item ${normalizedTask.status}`;
        taskEl.dataset.taskId = normalizedTask.id;
        taskEl.onclick = () => this.showTaskDetails(normalizedTask);

        const createdTime = normalizedTask.created_at ? new Date(normalizedTask.created_at).toLocaleString() : 'Unknown';
        const rawDescription = normalizedTask.description ? String(normalizedTask.description) : '';
        const description = rawDescription.length > 0 ?
            (rawDescription.length > 100 ? rawDescription.substring(0, 100) + '...' : rawDescription)
            : 'No description';
        const taskIdDisplay = normalizedTask.id ? `${String(normalizedTask.id).substring(0, 8)}...` : 'Unknown';

        taskEl.innerHTML = `
            <div class="task-header">
                <div>
                    <div class="task-title">${this.escapeHtml(normalizedTask.title)}</div>
                </div>
                <span class="task-status ${normalizedTask.status}">${normalizedTask.status}</span>
            </div>
            <div class="task-description">${this.escapeHtml(description)}</div>
            <div class="task-meta">
                <span>🆔 ${taskIdDisplay}</span>
                <span>⏰ ${createdTime}</span>
            </div>
        `;

        return taskEl;
    }

    showTaskDetails(task) {
        const normalizedTask = this.normalizeTask(task);
        const taskIdFull = normalizedTask.id ? String(normalizedTask.id) : 'Unknown';
        const modal = document.createElement('div');
        modal.className = 'task-detail-modal show';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h2>${this.escapeHtml(normalizedTask.title)}</h2>
                    <button class="close-modal" onclick="this.closest('.task-detail-modal').remove()">×</button>
                </div>
                <div class="task-status ${normalizedTask.status}">${normalizedTask.status}</div>
                <div style="margin-top: 20px;">
                    <h3 style="margin-bottom: 10px;">Description:</h3>
                    <div style="white-space: pre-wrap; line-height: 1.6; color: #495057;">
                        ${this.escapeHtml(normalizedTask.description || 'No description provided')}
                    </div>
                </div>
                <div style="margin-top: 20px;">
                    <h3 style="margin-bottom: 10px;">Details:</h3>
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 0.9em;">
                        <div><strong>Task ID:</strong> ${taskIdFull}</div>
                        <div><strong>Status:</strong> ${normalizedTask.status}</div>
                        <div><strong>Created:</strong> ${normalizedTask.created_at ? new Date(normalizedTask.created_at).toLocaleString() : 'Unknown'}</div>
                        <div><strong>Updated:</strong> ${normalizedTask.updated_at ? new Date(normalizedTask.updated_at).toLocaleString() : 'Unknown'}</div>
                    </div>
                </div>
                <div class="task-actions" style="margin-top: 20px; display: flex; gap: 10px;">
                    ${normalizedTask.status === 'pending' ? `
                        <button class="btn-primary" onclick="monitor.updateTaskStatus('${normalizedTask.id}', 'working')">
                            ▶️ Start Working
                        </button>
                    ` : ''}
                    ${normalizedTask.status === 'working' ? `
                        <button class="btn-primary" onclick="monitor.updateTaskStatus('${normalizedTask.id}', 'completed')">
                            ✅ Mark Complete
                        </button>
                        <button class="btn-secondary" onclick="monitor.updateTaskStatus('${normalizedTask.id}', 'failed')">
                            ❌ Mark Failed
                        </button>
                    ` : ''}
                    ${normalizedTask.status !== 'cancelled' ? `
                        <button class="btn-secondary" onclick="monitor.updateTaskStatus('${normalizedTask.id}', 'cancelled')">
                            🚫 Cancel Task
                        </button>
                    ` : ''}
                    <button class="btn-secondary" onclick="navigator.clipboard.writeText('${normalizedTask.id}'); monitor.showToast('Task ID copied!', 'success')">
                        📋 Copy ID
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        // Close on outside click
        modal.onclick = (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        };
    }

    async updateTaskStatus(taskId, newStatus) {
        try {
            // For MCP endpoints, we need to try port 9000 if not on the same port
            let mcpServerUrl = this.getServerUrl();
            const currentPort = window.location.port;

            // If we're on the main A2A server port, try MCP server on 9000
            if (currentPort === '8000' || currentPort === '') {
                mcpServerUrl = mcpServerUrl.replace(':8000', ':9000');
            }

            const response = await fetch(`${mcpServerUrl}/mcp/v1/tasks/${taskId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    status: newStatus
                })
            });

            if (response.ok) {
                this.showToast(`Task status updated to ${newStatus}`, 'success');
                // Close modal
                document.querySelector('.task-detail-modal')?.remove();
                // Refresh tasks
                await this.pollTaskQueue();
            } else {
                throw new Error('Failed to update task status');
            }
        } catch (error) {
            console.error('Error updating task status:', error);
            this.showToast('Failed to update task status', 'error');
        }
    }

    normalizeTask(task) {
        if (!task || typeof task !== 'object') {
            return {
                id: 'unknown',
                title: 'Untitled Task',
                description: '',
                status: 'pending',
                created_at: null,
                updated_at: null
            };
        }

        const id = task.id || task.task_id || task.uuid || 'unknown';
        const title = task.title || task.name || 'Untitled Task';
        const description = task.description || task.details || '';
        const status = (task.status || task.state || 'pending').toString();
        const createdAt = task.created_at || task.createdAt || task.created || null;
        const updatedAt = task.updated_at || task.updatedAt || task.updated || createdAt;

        return {
            ...task,
            id: String(id),
            title: String(title),
            description: description !== null && description !== undefined ? String(description) : '',
            status,
            created_at: createdAt,
            updated_at: updatedAt
        };
    }

    startHeartbeat() {
        // Clear any existing heartbeat
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
        }

        // Check connection every 30 seconds
        this.heartbeatInterval = setInterval(() => {
            if (!this.eventSource || this.eventSource.readyState !== EventSource.OPEN) {
                console.log('Connection lost, reconnecting...');
                this.connectToServer();
            }
        }, 30000);
    }

    getServerUrl() {
        // Try to get server URL from query params, current location, or use default
        const params = new URLSearchParams(window.location.search);
        if (params.get('server')) {
            return params.get('server');
        }

        // If running on the same server, use relative URL
        if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
            return window.location.origin;
        }

        // For local development, detect which port based on current page
        const currentPort = window.location.port;
        if (currentPort === '9000' || currentPort === '9001') {
            // If accessing monitor on MCP server port, use the same port
            return `http://localhost:${currentPort}`;
        } else {
            // Default to port 8000 for A2A server and port 9000 for MCP endpoints
            return 'http://localhost:8000';
        }
    }

    async pollAgentList() {
        // Don't poll if paused
        if (this.isPaused) {
            setTimeout(() => this.pollAgentList(), 5000);
            return;
        }

        try {
            const serverUrl = this.getServerUrl();
            const response = await fetch(`${serverUrl}/v1/monitor/agents`);
            if (response.ok) {
                const agents = await response.json();
                this.updateAgentList(agents);
            }
        } catch (error) {
            console.error('Failed to fetch agent list:', error);
        }

        // Poll every 5 seconds for agent updates
        setTimeout(() => this.pollAgentList(), 5000);
    }

    handleMessage(data) {
        if (this.isPaused) return;

        const messageType = data.type === 'connected' ? 'system' : (data.type || 'agent');
        const agentName = data.agent_name || data.agentName || (data.type === 'connected' ? 'Monitoring Service' : 'Unknown');
        const content =
            data.content ??
            data.message ??
            (Array.isArray(data.parts) ? data.parts.map(part => part.text || part.content).join(' ') : undefined) ??
            (data.type === 'connected' ? 'Connected to monitoring stream' : '');
        const metadata = data.metadata || {};

        const message = {
            id: Date.now() + Math.random(),
            timestamp: data.timestamp ? new Date(data.timestamp) : new Date(),
            type: messageType,
            agentName,
            content,
            metadata,
            ...data
        };

        // Skip rendering if content is still undefined/null after fallback logic
        if (message.content === undefined || message.content === null) {
            message.content = '';
        }

        this.messages.push(message);
        this.stats.totalMessages++;

        // Track response times
        if (data.response_time) {
            this.stats.responseTimes.push(data.response_time);
        }

        // Track tool calls
        if (data.type === 'tool') {
            this.stats.toolCalls++;
        }

        // Track errors
        if (data.error || data.type === 'error') {
            this.stats.errors++;
        }

        // Track tokens
        if (data.tokens) {
            this.stats.tokens += data.tokens;
        }

        this.displayMessage(message);
        this.updateStatsDisplay();
    }

    displayMessage(message) {
        const container = document.getElementById('messagesContainer');

        // Check filter
        if (this.currentFilter !== 'all' && message.type !== this.currentFilter) {
            return;
        }

        const messageEl = document.createElement('div');
        messageEl.className = `message ${message.type}`;
        messageEl.dataset.messageId = message.id;
        messageEl.dataset.messageType = message.type;

        // Handle timestamp - ensure it's a Date object
        const timestamp = message.timestamp instanceof Date ? message.timestamp : new Date(message.timestamp);
        const timeStr = timestamp.toLocaleTimeString();

        messageEl.innerHTML = `
            <div class="message-header">
                <div class="message-meta">
                    <span class="agent-name">${this.escapeHtml(message.agentName)}</span>
                    <span class="timestamp">${timeStr}</span>
                </div>
                <div class="message-actions">
                    <button class="action-btn btn-flag" onclick="flagMessage('${message.id}')">🚩 Flag</button>
                    <button class="action-btn btn-intervene" onclick="interveneAfterMessage('${message.id}')">✋ Intervene</button>
                    <button class="action-btn btn-copy" onclick="copyMessage('${message.id}')">📋 Copy</button>
                </div>
            </div>
            <div class="message-content">${this.formatContent(message.content)}</div>
            ${this.formatMetadata(message.metadata)}
        `;

        container.appendChild(messageEl);

        // Auto-scroll to bottom
        container.scrollTop = container.scrollHeight;

        // Keep only last 100 messages in DOM for performance
        while (container.children.length > 100) {
            container.removeChild(container.firstChild);
        }
    }

    formatContent(content) {
        if (typeof content === 'object') {
            return `<pre>${JSON.stringify(content, null, 2)}</pre>`;
        }
        return this.escapeHtml(String(content));
    }

    formatMetadata(metadata) {
        if (!metadata || Object.keys(metadata).length === 0) {
            return '';
        }

        const items = Object.entries(metadata)
            .map(([key, value]) => `<strong>${key}:</strong> ${value}`)
            .join(' | ');

        return `<div class="message-details">${items}</div>`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    updateAgentStatus(data) {
        this.agents.set(data.agent_id, {
            name: data.name,
            status: data.status,
            lastSeen: new Date(),
            messagesCount: data.messages_count || 0
        });

        this.updateAgentList();
        document.getElementById('activeAgents').textContent = this.agents.size;
    }

    updateAgentList(agentData) {
        if (agentData) {
            agentData.forEach(agent => {
                this.agents.set(agent.id, {
                    name: agent.name,
                    status: agent.status,
                    lastSeen: new Date(),
                    messagesCount: agent.messages_count || 0
                });
            });
        }

        const listEl = document.getElementById('agentList');
        const selectEl = document.getElementById('targetAgent');

        listEl.innerHTML = '';
        selectEl.innerHTML = '<option value="">Select Agent...</option>';

        this.agents.forEach((agent, id) => {
            // Add to list
            const li = document.createElement('li');
            li.className = 'agent-item';
            li.innerHTML = `
                <div class="agent-status">
                    <span class="status-indicator ${agent.status}"></span>
                    <span>${agent.name}</span>
                </div>
                <span>${agent.messagesCount} msgs</span>
            `;
            listEl.appendChild(li);

            // Add to select
            const option = document.createElement('option');
            option.value = id;
            option.textContent = agent.name;
            selectEl.appendChild(option);
        });
    }

    updateConnectionStatus(connected) {
        const statusEl = document.getElementById('connectionStatus');
        const indicator = document.querySelector('.status-indicator');

        if (connected) {
            statusEl.textContent = 'Connected';
            indicator.className = 'status-indicator active';
        } else {
            statusEl.textContent = 'Disconnected';
            indicator.className = 'status-indicator idle';
        }
    }

    updateStatsDisplay() {
        document.getElementById('messageCount').textContent = this.stats.totalMessages;
        document.getElementById('interventionCount').textContent = this.stats.interventions;
        document.getElementById('toolCalls').textContent = this.stats.toolCalls;
        document.getElementById('errorCount').textContent = this.stats.errors;
        document.getElementById('tokenCount').textContent = this.stats.tokens;

        if (this.stats.responseTimes.length > 0) {
            const avg = this.stats.responseTimes.reduce((a, b) => a + b, 0) / this.stats.responseTimes.length;
            document.getElementById('avgResponseTime').textContent = Math.round(avg) + 'ms';
        }
    }

    updateStats(data) {
        Object.assign(this.stats, data);
        this.updateStatsDisplay();
    }

    async sendIntervention(event) {
        event.preventDefault();

        const agentId = document.getElementById('targetAgent').value;
        const message = document.getElementById('interventionMessage').value;

        if (!agentId || !message) {
            alert('Please select an agent and enter a message');
            return;
        }

        try {
            const serverUrl = this.getServerUrl();
            const response = await fetch(`${serverUrl}/v1/monitor/intervene`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    agent_id: agentId,
                    message: message,
                    timestamp: new Date().toISOString()
                })
            });

            if (response.ok) {
                this.stats.interventions++;
                this.updateStatsDisplay();

                // Add intervention to messages
                this.handleMessage({
                    type: 'human',
                    agent_name: 'Human Operator',
                    content: `Intervention to ${this.agents.get(agentId)?.name}: ${message}`,
                    metadata: { intervention: true }
                });

                // Clear form
                document.getElementById('interventionMessage').value = '';

                this.showToast('Intervention sent successfully', 'success');
            } else {
                throw new Error('Failed to send intervention');
            }
        } catch (error) {
            console.error('Error sending intervention:', error);
            this.showToast('Failed to send intervention', 'error');
        }
    }

    setupEventListeners() {
        // Filter messages
        window.filterMessages = (type) => {
            this.currentFilter = type;

            // Update button states
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');

            // Show/hide messages
            document.querySelectorAll('.message').forEach(msg => {
                if (type === 'all' || msg.dataset.messageType === type) {
                    msg.style.display = 'block';
                } else {
                    msg.style.display = 'none';
                }
            });
        };

        // Search messages
        window.searchMessages = () => {
            const query = document.getElementById('searchInput').value.toLowerCase();
            document.querySelectorAll('.message').forEach(msg => {
                const content = msg.textContent.toLowerCase();
                msg.style.display = content.includes(query) ? 'block' : 'none';
            });
        };

        // Send intervention
        window.sendIntervention = (event) => this.sendIntervention(event);

        // Flag message
        window.flagMessage = (messageId) => {
            const message = this.messages.find(m => m.id == messageId);
            if (message) {
                message.flagged = true;
                this.showToast('Message flagged for review', 'info');
            }
        };

        // Intervene after message
        window.interveneAfterMessage = (messageId) => {
            const message = this.messages.find(m => m.id == messageId);
            if (message) {
                document.getElementById('interventionMessage').value = `Regarding: "${message.content.substring(0, 50)}..."`;
                document.getElementById('interventionMessage').focus();
            }
        };

        // Copy message
        window.copyMessage = (messageId) => {
            const message = this.messages.find(m => m.id == messageId);
            if (message) {
                navigator.clipboard.writeText(JSON.stringify(message, null, 2));
                this.showToast('Message copied to clipboard', 'success');
            }
        };

        // Export functions
        window.exportJSON = () => this.exportData('json');
        window.exportCSV = () => this.exportData('csv');
        window.exportHTML = () => this.exportData('html');
        window.exportAllJSON = () => this.exportFromServer('json', true);
        window.exportAllCSV = () => this.exportFromServer('csv', true);

        // Search persistent storage
        window.searchPersistent = () => this.searchPersistentMessages();
        window.closeSearchResults = () => this.closeSearchResults();

        // Load historical messages
        window.loadHistoricalMessages = () => this.loadHistoricalMessages();

        // Clear logs
        window.clearLogs = () => {
            if (confirm('Are you sure you want to clear all logs?')) {
                this.messages = [];
                document.getElementById('messagesContainer').innerHTML = '';
                this.showToast('Logs cleared', 'info');
            }
        };

        // Pause monitoring
        window.pauseMonitoring = () => {
            this.isPaused = !this.isPaused;
            event.target.textContent = this.isPaused ? 'Resume' : 'Pause';
            this.showToast(this.isPaused ? 'Monitoring paused' : 'Monitoring resumed', 'info');
        };

        // Task queue functions
        window.filterTasks = (status) => {
            this.currentTaskFilter = status;

            // Update button states
            const buttons = document.querySelectorAll('.task-queue-panel .filter-btn');
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            this.displayTasks();
        };

        window.refreshTasks = () => {
            this.pollTaskQueue();
            this.showToast('Tasks refreshed', 'info');
        };

        window.createNewTask = async () => {
            const title = prompt('Enter task title:');
            if (!title) return;

            const description = prompt('Enter task description (optional):');

            try {
                // For MCP endpoints, we need to try port 9000 if not on the same port
                let mcpServerUrl = this.getServerUrl();
                const currentPort = window.location.port;

                // If we're on the main A2A server port, try MCP server on 9000
                if (currentPort === '8000' || currentPort === '') {
                    mcpServerUrl = mcpServerUrl.replace(':8000', ':9000');
                }

                const response = await fetch(`${mcpServerUrl}/mcp/v1/tasks`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        title: title,
                        description: description || ''
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    this.showToast('Task created successfully!', 'success');
                    await this.pollTaskQueue();
                } else {
                    throw new Error('Failed to create task');
                }
            } catch (error) {
                console.error('Error creating task:', error);
                this.showToast('Failed to create task', 'error');
            }
        };
    }

    exportData(format) {
        const data = this.messages.map(msg => ({
            timestamp: msg.timestamp.toISOString(),
            type: msg.type,
            agent: msg.agentName,
            content: msg.content,
            metadata: msg.metadata
        }));

        let content, filename, mimeType;

        if (format === 'json') {
            content = JSON.stringify(data, null, 2);
            filename = `a2a-logs-${Date.now()}.json`;
            mimeType = 'application/json';
        } else if (format === 'csv') {
            const headers = 'Timestamp,Type,Agent,Content\n';
            const rows = data.map(row =>
                `"${row.timestamp}","${row.type}","${row.agent}","${row.content}"`
            ).join('\n');
            content = headers + rows;
            filename = `a2a-logs-${Date.now()}.csv`;
            mimeType = 'text/csv';
        } else if (format === 'html') {
            content = this.generateHTMLReport(data);
            filename = `a2a-logs-${Date.now()}.html`;
            mimeType = 'text/html';
        }

        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);

        this.showToast(`Exported as ${format.toUpperCase()}`, 'success');
    }

    async exportFromServer(format, allMessages = false) {
        try {
            const serverUrl = this.getServerUrl();
            const endpoint = format === 'json' ? 'export/json' : 'export/csv';
            const url = `${serverUrl}/v1/monitor/${endpoint}?all_messages=${allMessages}`;

            this.showToast(`Downloading ${allMessages ? 'all' : 'recent'} messages...`, 'info');

            const response = await fetch(url);
            if (!response.ok) throw new Error('Export failed');

            const blob = await response.blob();
            const downloadUrl = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = `a2a-logs-${allMessages ? 'complete' : 'recent'}-${Date.now()}.${format}`;
            a.click();
            URL.revokeObjectURL(downloadUrl);

            this.showToast(`Exported ${allMessages ? 'all' : 'recent'} messages as ${format.toUpperCase()}`, 'success');
        } catch (error) {
            console.error('Export failed:', error);
            this.showToast('Export failed', 'error');
        }
    }

    async searchPersistentMessages() {
        const query = document.getElementById('searchInput').value.trim();
        if (!query) {
            this.showToast('Please enter a search term', 'info');
            return;
        }

        try {
            const serverUrl = this.getServerUrl();
            const response = await fetch(`${serverUrl}/v1/monitor/messages/search?q=${encodeURIComponent(query)}&limit=100`);

            if (!response.ok) throw new Error('Search failed');

            const data = await response.json();
            this.displaySearchResults(data.results, query);
        } catch (error) {
            console.error('Search failed:', error);
            this.showToast('Search failed', 'error');
        }
    }

    displaySearchResults(results, query) {
        const container = document.getElementById('searchResults');
        const content = document.getElementById('searchResultsContent');

        container.style.display = 'block';

        if (results.length === 0) {
            content.innerHTML = `<p>No results found for "${this.escapeHtml(query)}"</p>`;
            return;
        }

        content.innerHTML = `<p>Found ${results.length} messages matching "${this.escapeHtml(query)}":</p>`;

        results.forEach(msg => {
            const timestamp = msg.timestamp ? new Date(msg.timestamp).toLocaleString() : 'Unknown';
            const resultEl = document.createElement('div');
            resultEl.className = 'search-result-item';
            resultEl.innerHTML = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <strong>${this.escapeHtml(msg.agent_name || 'Unknown')}</strong>
                    <span style="color: #6c757d; font-size: 0.85em;">${timestamp}</span>
                </div>
                <div style="color: #495057;">${this.highlightQuery(msg.content || '', query)}</div>
                <div style="font-size: 0.8em; color: #6c757d; margin-top: 5px;">Type: ${msg.type || 'unknown'}</div>
            `;
            content.appendChild(resultEl);
        });
    }

    highlightQuery(text, query) {
        if (!text || !query) return this.escapeHtml(text);
        const escaped = this.escapeHtml(text);
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        return escaped.replace(regex, '<mark style="background: #fff3cd;">$1</mark>');
    }

    closeSearchResults() {
        document.getElementById('searchResults').style.display = 'none';
    }

    async loadHistoricalMessages() {
        try {
            const serverUrl = this.getServerUrl();
            this.showToast('Loading historical messages...', 'info');

            const response = await fetch(`${serverUrl}/v1/monitor/messages?limit=500&use_cache=false`);
            if (!response.ok) throw new Error('Failed to load history');

            const messages = await response.json();

            // Clear current messages and load historical
            document.getElementById('messagesContainer').innerHTML = '';
            this.messages = [];

            // Add messages in chronological order
            messages.reverse().forEach(msg => {
                const message = {
                    id: msg.id || Date.now() + Math.random(),
                    timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
                    type: msg.type || 'agent',
                    agentName: msg.agent_name || 'Unknown',
                    content: msg.content || '',
                    metadata: msg.metadata || {}
                };
                this.messages.push(message);
                this.displayMessage(message);
            });

            this.showToast(`Loaded ${messages.length} historical messages`, 'success');
        } catch (error) {
            console.error('Failed to load history:', error);
            this.showToast('Failed to load historical messages', 'error');
        }
    }

    generateHTMLReport(data) {
        return `
<!DOCTYPE html>
<html>
<head>
    <title>A2A Agent Logs - ${new Date().toISOString()}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #667eea; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #667eea; color: white; }
        tr:nth-child(even) { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>A2A Agent Conversation Logs</h1>
    <p>Generated: ${new Date().toLocaleString()}</p>
    <p>Total Messages: ${data.length}</p>
    <table>
        <thead>
            <tr>
                <th>Timestamp</th>
                <th>Type</th>
                <th>Agent</th>
                <th>Content</th>
            </tr>
        </thead>
        <tbody>
            ${data.map(row => `
                <tr>
                    <td>${row.timestamp}</td>
                    <td>${row.type}</td>
                    <td>${row.agent}</td>
                    <td>${row.content}</td>
                </tr>
            `).join('')}
        </tbody>
    </table>
</body>
</html>
        `;
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        toast.style.background = type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#17a2b8';
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 3000);
    }

    startStatsUpdate() {
        setInterval(() => {
            this.updateStatsDisplay();
        }, 1000);
    }
}

// Initialize monitor when page loads
const monitor = new AgentMonitor();

// Global functions for agent output panel
function toggleAutoScroll() {
    monitor.toggleAutoScroll();
}

function clearAgentOutput() {
    monitor.clearAgentOutput();
}

function downloadAgentOutput() {
    monitor.downloadAgentOutput();
}

function switchAgentOutput() {
    monitor.switchAgentOutput();
}

// ========================================
// Task Management Functions
// ========================================

function createNewTask() {
    openTaskModal();
}

function openTaskModal(codebaseId = null) {
    const modal = document.getElementById('taskModal');
    const agentSelect = document.getElementById('taskAgent');

    // Populate agent dropdown with registered codebases
    agentSelect.innerHTML = '<option value="">Select an agent...</option>';
    monitor.codebases.forEach(cb => {
        const option = document.createElement('option');
        option.value = cb.id;
        option.textContent = `${cb.name} (${cb.status})`;
        if (cb.status === 'watching') {
            option.textContent += ' 👁️ Watching';
        }
        agentSelect.appendChild(option);
    });

    // Pre-select agent if provided
    if (codebaseId) {
        agentSelect.value = codebaseId;
        document.getElementById('taskCodebaseId').value = codebaseId;
    }

    modal.style.display = 'flex';
}

function closeTaskModal() {
    const modal = document.getElementById('taskModal');
    modal.style.display = 'none';

    // Clear form
    document.getElementById('taskTitle').value = '';
    document.getElementById('taskDescription').value = '';
    document.getElementById('taskPriority').value = '2';
    document.getElementById('taskContext').value = '';
    document.getElementById('taskAgent').value = '';
    document.getElementById('taskCodebaseId').value = '';
}

async function submitTask(event) {
    event.preventDefault();

    const codebaseId = document.getElementById('taskAgent').value;
    const title = document.getElementById('taskTitle').value;
    const description = document.getElementById('taskDescription').value;
    const priority = parseInt(document.getElementById('taskPriority').value);
    const context = document.getElementById('taskContext').value;

    if (!codebaseId) {
        monitor.showToast('Please select an agent', 'error');
        return;
    }

    try {
        const serverUrl = monitor.getServerUrl();
        const response = await fetch(`${serverUrl}/v1/opencode/codebases/${codebaseId}/tasks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: title,
                description: description,
                priority: priority,
                context: context || null
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create task');
        }

        const task = await response.json();
        monitor.showToast(`Task "${title}" created successfully!`, 'success');
        closeTaskModal();
        refreshTasks();

    } catch (error) {
        console.error('Failed to create task:', error);
        monitor.showToast(`Failed to create task: ${error.message}`, 'error');
    }
}

async function refreshTasks() {
    try {
        const serverUrl = monitor.getServerUrl();
        const response = await fetch(`${serverUrl}/v1/opencode/tasks`);

        if (!response.ok) throw new Error('Failed to fetch tasks');

        const tasks = await response.json();
        monitor.tasks = tasks;
        displayTasks(tasks);

    } catch (error) {
        console.error('Failed to refresh tasks:', error);
    }
}

function filterTasks(status) {
    // Update active filter button
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.textContent.toLowerCase().includes(status) ||
            (status === 'all' && btn.textContent.toLowerCase().includes('all'))) {
            btn.classList.add('active');
        }
    });

    monitor.currentTaskFilter = status;

    // Filter and display tasks
    let filtered = monitor.tasks;
    if (status !== 'all') {
        filtered = monitor.tasks.filter(t => t.status === status);
    }
    displayTasks(filtered);
}

function displayTasks(tasks) {
    const container = document.getElementById('tasksContainer');
    if (!container) return;

    if (tasks.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="padding: 40px; text-align: center; color: #6c757d;">
                <p>📋 No tasks in queue</p>
                <p style="font-size: 0.9em;">Create a task to assign work to an agent</p>
            </div>
        `;
        return;
    }

    container.innerHTML = tasks.map(task => {
        const codebase = monitor.codebases.find(cb => cb.id === task.codebase_id);
        const agentName = codebase ? codebase.name : 'Unknown Agent';
        const statusEmoji = getTaskStatusEmoji(task.status);
        const priorityEmoji = getPriorityEmoji(task.priority);
        const createdAt = new Date(task.created_at).toLocaleString();

        return `
            <div class="task-item ${task.status}" data-task-id="${task.id}">
                <div class="task-header" style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="task-title">${statusEmoji} ${monitor.escapeHtml(task.title)}</span>
                    <span class="task-priority">${priorityEmoji}</span>
                </div>
                <div class="task-meta">
                    <span>🤖 ${monitor.escapeHtml(agentName)}</span>
                    <span>⏰ ${createdAt}</span>
                </div>
                <div class="task-description" style="margin-top: 8px; font-size: 0.9em; color: #6c757d;">
                    ${monitor.escapeHtml(task.description).substring(0, 100)}${task.description.length > 100 ? '...' : ''}
                </div>
                <div class="task-actions" style="margin-top: 10px; display: flex; gap: 8px;">
                    ${task.status === 'pending' ? `
                        <button class="btn-small btn-primary" onclick="startTask('${task.id}')">▶️ Start</button>
                        <button class="btn-small btn-secondary" onclick="cancelTask('${task.id}')">❌ Cancel</button>
                    ` : ''}
                    ${task.status === 'working' ? `
                        <button class="btn-small btn-secondary" onclick="viewTaskOutput('${task.id}')">👁️ View Output</button>
                        <button class="btn-small btn-danger" onclick="cancelTask('${task.id}')">⏹️ Stop</button>
                    ` : ''}
                    ${task.status === 'completed' ? `
                        <button class="btn-small btn-secondary" onclick="viewTaskResult('${task.id}')">📄 View Result</button>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
}

function getTaskStatusEmoji(status) {
    const emojis = {
        'pending': '⏳',
        'working': '🔄',
        'completed': '✅',
        'failed': '❌',
        'cancelled': '🚫'
    };
    return emojis[status] || '❓';
}

function getPriorityEmoji(priority) {
    const emojis = {
        1: '🟢 Low',
        2: '🟡 Normal',
        3: '🟠 High',
        4: '🔴 Urgent'
    };
    return emojis[priority] || '🟡 Normal';
}

async function cancelTask(taskId) {
    if (!confirm('Are you sure you want to cancel this task?')) return;

    try {
        const serverUrl = monitor.getServerUrl();
        const response = await fetch(`${serverUrl}/v1/opencode/tasks/${taskId}/cancel`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Failed to cancel task');

        monitor.showToast('Task cancelled', 'success');
        refreshTasks();

    } catch (error) {
        console.error('Failed to cancel task:', error);
        monitor.showToast('Failed to cancel task', 'error');
    }
}

async function startTask(taskId) {
    try {
        const serverUrl = monitor.getServerUrl();
        const task = monitor.tasks.find(t => t.id === taskId);

        if (!task) {
            monitor.showToast('Task not found', 'error');
            return;
        }

        // Find the codebase and trigger the agent
        const response = await fetch(`${serverUrl}/v1/opencode/codebases/${task.codebase_id}/trigger`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: `Task: ${task.title}\n\nDescription: ${task.description}${task.context ? `\n\nContext: ${task.context}` : ''}`
            })
        });

        if (!response.ok) throw new Error('Failed to start task');

        monitor.showToast('Task started!', 'success');

        // Open agent output modal
        openAgentOutputModal(task.codebase_id);
        refreshTasks();

    } catch (error) {
        console.error('Failed to start task:', error);
        monitor.showToast('Failed to start task', 'error');
    }
}

function viewTaskOutput(taskId) {
    const task = monitor.tasks.find(t => t.id === taskId);
    if (task) {
        openAgentOutputModal(task.codebase_id);
    }
}

function viewTaskResult(taskId) {
    const task = monitor.tasks.find(t => t.id === taskId);
    if (task && task.result) {
        alert(`Task Result:\n\n${task.result}`);
    } else {
        monitor.showToast('No result available', 'info');
    }
}

// ========================================
// Watch Mode Functions
// ========================================

async function startWatchMode(codebaseId) {
    try {
        const serverUrl = monitor.getServerUrl();
        const response = await fetch(`${serverUrl}/v1/opencode/codebases/${codebaseId}/watch/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                poll_interval: 5.0
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to start watch mode');
        }

        monitor.showToast('Watch mode started! Agent will process queued tasks automatically.', 'success');
        monitor.loadCodebases();  // Refresh to show watching status

    } catch (error) {
        console.error('Failed to start watch mode:', error);
        monitor.showToast(`Failed to start watch mode: ${error.message}`, 'error');
    }
}

async function stopWatchMode(codebaseId) {
    try {
        const serverUrl = monitor.getServerUrl();
        const response = await fetch(`${serverUrl}/v1/opencode/codebases/${codebaseId}/watch/stop`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Failed to stop watch mode');

        monitor.showToast('Watch mode stopped', 'success');
        monitor.loadCodebases();  // Refresh status

    } catch (error) {
        console.error('Failed to stop watch mode:', error);
        monitor.showToast('Failed to stop watch mode', 'error');
    }
}

// ========================================
// Agent Output Modal Functions
// ========================================

function openAgentOutputModal(codebaseId) {
    const modal = document.getElementById('agentOutputModal');
    const content = document.getElementById('agentOutputContent');

    // Set current agent and display output
    monitor.currentOutputAgent = codebaseId;

    // Initialize output array if needed
    if (!monitor.agentOutputs.has(codebaseId)) {
        monitor.agentOutputs.set(codebaseId, []);
    }

    // Connect to event stream if not connected
    if (!monitor.agentOutputStreams.has(codebaseId)) {
        monitor.connectAgentEventStream(codebaseId);
    }

    // Display existing output in modal
    const outputs = monitor.agentOutputs.get(codebaseId) || [];
    if (outputs.length === 0) {
        content.innerHTML = '<div class="loading">Waiting for agent output...</div>';
    } else {
        content.innerHTML = outputs.map(entry => formatOutputEntry(entry)).join('');
    }

    modal.style.display = 'flex';
}

function closeAgentOutputModal() {
    document.getElementById('agentOutputModal').style.display = 'none';
}

function formatOutputEntry(entry) {
    const timestamp = new Date(entry.timestamp).toLocaleTimeString();
    let className = 'output-entry';
    let content = '';

    switch (entry.type) {
        case 'thinking':
            className += ' thinking';
            content = `<span class="output-time">[${timestamp}]</span> 🧠 ${monitor.escapeHtml(entry.content)}`;
            break;
        case 'tool_call':
            className += ' tool-call';
            content = `<span class="output-time">[${timestamp}]</span> 🔧 Tool: ${monitor.escapeHtml(entry.tool_name || 'unknown')}`;
            if (entry.tool_args) {
                content += `<pre style="margin: 5px 0; padding: 8px; background: rgba(0,0,0,0.3); border-radius: 4px; overflow-x: auto;">${monitor.escapeHtml(JSON.stringify(entry.tool_args, null, 2))}</pre>`;
            }
            break;
        case 'tool_result':
            className += ' tool-result';
            content = `<span class="output-time">[${timestamp}]</span> ✅ Result: <pre style="margin: 5px 0; padding: 8px; background: rgba(0,0,0,0.3); border-radius: 4px; overflow-x: auto;">${monitor.escapeHtml(entry.content?.substring(0, 500) || '')}${entry.content?.length > 500 ? '...' : ''}</pre>`;
            break;
        case 'response':
            className += ' response';
            content = `<span class="output-time">[${timestamp}]</span> 💬 ${monitor.escapeHtml(entry.content)}`;
            break;
        case 'error':
            className += ' error';
            content = `<span class="output-time">[${timestamp}]</span> ❌ ${monitor.escapeHtml(entry.content)}`;
            break;
        default:
            content = `<span class="output-time">[${timestamp}]</span> ${monitor.escapeHtml(entry.content || '')}`;
    }

    return `<div class="${className}" style="padding: 8px; margin-bottom: 4px; border-radius: 4px; background: rgba(255,255,255,0.05);">${content}</div>`;
}

function exportAgentOutput() {
    if (!monitor.currentOutputAgent) return;

    const outputs = monitor.agentOutputs.get(monitor.currentOutputAgent) || [];
    const codebase = monitor.codebases.find(cb => cb.id === monitor.currentOutputAgent);
    const name = codebase ? codebase.name : 'agent';

    const blob = new Blob([JSON.stringify(outputs, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${name}_output_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

// Add keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Escape to close modals
    if (e.key === 'Escape') {
        closeTaskModal();
        closeAgentOutputModal();
        closeRegisterModal();
    }

    // Ctrl+N for new task
    if (e.ctrlKey && e.key === 'n') {
        e.preventDefault();
        openTaskModal();
    }
});

// Poll tasks periodically
setInterval(() => {
    if (!document.hidden) {
        refreshTasks();
    }
}, 10000);

// Initial task load
setTimeout(() => {
    refreshTasks();
}, 1000);
