// A2A Agent Monitor - Real-time monitoring and intervention
class AgentMonitor {
    constructor() {
        this.messages = [];
        this.agents = new Map();
        this.eventSource = null;
        this.isPaused = false;
        this.currentFilter = 'all';
        this.stats = {
            totalMessages: 0,
            interventions: 0,
            toolCalls: 0,
            errors: 0,
            tokens: 0,
            responseTimes: []
        };
        this.init();
    }

    init() {
        this.connectToServer();
        this.setupEventListeners();
        this.startStatsUpdate();
    }

    connectToServer() {
        const serverUrl = this.getServerUrl();
        
        // Connect to SSE endpoint for real-time updates
        this.eventSource = new EventSource(`${serverUrl}/v1/monitor/stream`);
        
        this.eventSource.onopen = () => {
            console.log('Connected to A2A server');
            this.updateConnectionStatus(true);
        };

        this.eventSource.onerror = (error) => {
            console.error('SSE error:', error);
            this.updateConnectionStatus(false);
            
            // Attempt to reconnect after 5 seconds
            setTimeout(() => this.connectToServer(), 5000);
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

        // Also poll for agent list
        this.pollAgentList();
    }

    getServerUrl() {
        // Try to get server URL from query params or use default
        const params = new URLSearchParams(window.location.search);
        return params.get('server') || 'http://localhost:8000';
    }

    async pollAgentList() {
        try {
            const serverUrl = this.getServerUrl();
            const response = await fetch(`${serverUrl}/v1/monitor/agents`);
            const agents = await response.json();
            this.updateAgentList(agents);
        } catch (error) {
            console.error('Failed to fetch agent list:', error);
        }
        
        // Poll every 5 seconds
        setTimeout(() => this.pollAgentList(), 5000);
    }

    handleMessage(data) {
        if (this.isPaused) return;

        const message = {
            id: Date.now() + Math.random(),
            timestamp: new Date(),
            type: data.type || 'agent',
            agentName: data.agent_name || 'Unknown',
            content: data.content || data.message,
            metadata: data.metadata || {},
            ...data
        };

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

        const timeStr = message.timestamp.toLocaleTimeString();
        
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
