'use client';
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useRef, useEffect, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { motion, AnimatePresence } from 'framer-motion';
import { createGlobalTaskV1AgentTasksPost, getTaskV1AgentTasksTaskIdGet } from '@/lib/api';
// Constants
const STORAGE_KEY = 'intercom-chat-messages';
const CONVERSATION_ID_KEY = 'intercom-chat-conversation-id';
function getTaskId(response) {
    return response.id || response.task_id || '';
}
function normalizeTaskResponse(data) {
    var _a;
    const task = (_a = data === null || data === void 0 ? void 0 : data.task) !== null && _a !== void 0 ? _a : data;
    return {
        id: (task === null || task === void 0 ? void 0 : task.id) || (task === null || task === void 0 ? void 0 : task.task_id) || (task === null || task === void 0 ? void 0 : task.taskId) || '',
        task_id: (task === null || task === void 0 ? void 0 : task.task_id) || (task === null || task === void 0 ? void 0 : task.taskId) || (task === null || task === void 0 ? void 0 : task.id),
        title: (task === null || task === void 0 ? void 0 : task.title) || '',
        status: (task === null || task === void 0 ? void 0 : task.status) || '',
        result: task === null || task === void 0 ? void 0 : task.result,
        description: (task === null || task === void 0 ? void 0 : task.description) || (task === null || task === void 0 ? void 0 : task.detail),
    };
}
function extractErrorMessage(error) {
    if (!error)
        return undefined;
    if (typeof error === 'string')
        return error;
    if (typeof error === 'object') {
        const value = error;
        if (typeof value.detail === 'string')
            return value.detail;
        if (typeof value.message === 'string')
            return value.message;
        if (Array.isArray(value.detail)) {
            return value.detail
                .map((item) => typeof item === 'string'
                ? item
                : typeof item === 'object' && item && 'msg' in item
                    ? String(item.msg)
                    : JSON.stringify(item))
                .join('; ');
        }
    }
    return undefined;
}
function readResultPayload(result) {
    return __awaiter(this, void 0, void 0, function* () {
        if (!result)
            return undefined;
        if (typeof result === 'object' &&
            !('data' in result) &&
            !('error' in result) &&
            !('response' in result) &&
            !('request' in result)) {
            return result;
        }
        if (result.data !== undefined) {
            return result.data;
        }
        const response = result.response;
        if (!(response instanceof Response)) {
            return undefined;
        }
        const contentType = response.headers.get('Content-Type') || '';
        if (contentType.includes('application/json')) {
            return response.clone().json().catch(() => undefined);
        }
        const text = yield response.clone().text().catch(() => '');
        if (!text) {
            return undefined;
        }
        try {
            return JSON.parse(text);
        }
        catch (_a) {
            return { result: text };
        }
    });
}
// Shared icons
function ChatIcon({ className }) {
    return (_jsx("svg", { xmlns: "http://www.w3.org/2000/svg", fill: "none", viewBox: "0 0 24 24", strokeWidth: 1.5, stroke: "currentColor", className: className, children: _jsx("path", { strokeLinecap: "round", strokeLinejoin: "round", d: "M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" }) }));
}
function CloseIcon({ className }) {
    return (_jsx("svg", { xmlns: "http://www.w3.org/2000/svg", fill: "none", viewBox: "0 0 24 24", strokeWidth: 1.5, stroke: "currentColor", className: className, children: _jsx("path", { strokeLinecap: "round", strokeLinejoin: "round", d: "M6 18 18 6M6 6l12 12" }) }));
}
function SendIcon({ className }) {
    return (_jsx("svg", { xmlns: "http://www.w3.org/2000/svg", fill: "none", viewBox: "0 0 24 24", strokeWidth: 1.5, stroke: "currentColor", className: className, children: _jsx("path", { strokeLinecap: "round", strokeLinejoin: "round", d: "M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" }) }));
}
function LoadingDots() {
    return (_jsxs("div", { className: "flex space-x-1", children: [_jsx("div", { className: "w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]" }), _jsx("div", { className: "w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]" }), _jsx("div", { className: "w-2 h-2 bg-gray-400 rounded-full animate-bounce" })] }));
}
function RetryIcon({ className }) {
    return (_jsx("svg", { xmlns: "http://www.w3.org/2000/svg", fill: "none", viewBox: "0 0 24 24", strokeWidth: 1.5, stroke: "currentColor", className: className, children: _jsx("path", { strokeLinecap: "round", strokeLinejoin: "round", d: "M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" }) }));
}
function TrashIcon({ className }) {
    return (_jsx("svg", { xmlns: "http://www.w3.org/2000/svg", fill: "none", viewBox: "0 0 24 24", strokeWidth: 1.5, stroke: "currentColor", className: className, children: _jsx("path", { strokeLinecap: "round", strokeLinejoin: "round", d: "m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" }) }));
}
// System context
const CODETETHER_CONTEXT = `You are a helpful assistant for CodeTether. Answer questions based on this documentation:

# CodeTether - Turn AI Agents into Production Systems

CodeTether is a **production-ready Agent-to-Agent (A2A) platform** that is **officially A2A Protocol v0.3 compliant**. Build AI agent systems that actually work in the real world.

## Key Features

### Ralph: Autonomous Development
Ralph implements entire PRDs with zero human intervention. Define user stories, Ralph writes the code, runs tests, and commits—autonomously iterating until all acceptance criteria pass.

### MCP Tool Integration
Connect to 100+ tools via Model Context Protocol. File systems, databases, APIs, and more.

### AI Coding at Scale
Deploy AI coding agents across your infrastructure using CodeTether. Automated code generation, refactoring, and testing.

### RLM (Recursive Language Models)
Process arbitrarily long contexts through recursive LLM calls. Analyze entire monorepos without context limits.

### Email Reply to Continue Tasks
Workers send email notifications when tasks complete. Reply directly to the email to continue the conversation.

### Zapier Integration
Connect CodeTether to 5,000+ apps with native Zapier integration. OAuth2 authentication, triggers, actions, and searches.

### Voice Agent
Real-time voice interactions with AI agents through LiveKit integration.

### Real-Time Streaming
Watch agents think in real-time with SSE streaming.

## Quick Start

\`\`\`bash
pip install codetether
codetether-worker --api-url https://api.codetether.run
codetether-server --host 0.0.0.0 --port 8000
\`\`\`

## Pricing
CodeTether is open source (Apache 2.0). The hosted API at api.codetether.run is free for development use.

Answer questions helpfully and concisely based on the above documentation.`;
// API Functions using SDK
function createTask(prompt, headers) {
    return __awaiter(this, void 0, void 0, function* () {
        var _a;
        const result = yield createGlobalTaskV1AgentTasksPost({
            body: {
                title: `Chat: ${prompt.substring(0, 50)}${prompt.length > 50 ? '...' : ''}`,
                prompt: `${CODETETHER_CONTEXT}\n\n---\n\nUser question: ${prompt}\n\nProvide a helpful, concise response.`,
                agent_type: 'general',
            },
            headers,
        });
        const data = yield readResultPayload(result);
        if (!data) {
            const detail = extractErrorMessage(result.error);
            if (detail) {
                throw new Error(`Failed to create task: ${detail}`);
            }
            if ((_a = result.response) === null || _a === void 0 ? void 0 : _a.status) {
                throw new Error(`Failed to create task: HTTP ${result.response.status} ${result.response.statusText}`.trim());
            }
            throw new Error('Failed to create task: No data returned');
        }
        return normalizeTaskResponse(data);
    });
}
function getTask(taskId, headers) {
    return __awaiter(this, void 0, void 0, function* () {
        var _a;
        const result = yield getTaskV1AgentTasksTaskIdGet({
            path: { task_id: taskId },
            headers,
        });
        const data = yield readResultPayload(result);
        if (!data) {
            const detail = extractErrorMessage(result.error);
            if (detail) {
                throw new Error(`Failed to get task: ${detail}`);
            }
            if ((_a = result.response) === null || _a === void 0 ? void 0 : _a.status) {
                throw new Error(`Failed to get task: HTTP ${result.response.status} ${result.response.statusText}`.trim());
            }
            throw new Error('Failed to get task: No data returned');
        }
        return normalizeTaskResponse(data);
    });
}
function parseCodeTetherResult(result) {
    if (!result)
        return 'No response received';
    if (!result.trim().startsWith('{'))
        return result;
    const textParts = [];
    for (const line of result.split('\n').filter(l => l.trim())) {
        try {
            const parsed = JSON.parse(line);
            if (parsed.text)
                textParts.push(parsed.text);
            if (parsed.content)
                textParts.push(parsed.content);
        }
        catch (_a) {
            if (!line.trim().startsWith('{'))
                textParts.push(line);
        }
    }
    return textParts.length ? textParts.join('') : result;
}
function pollForCompletion(taskId_1, onUpdate_1) {
    return __awaiter(this, arguments, void 0, function* (taskId, onUpdate, maxAttempts = 60, intervalMs = 1000, headers) {
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            const task = yield getTask(taskId, headers);
            if (onUpdate)
                onUpdate(task);
            if (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') {
                return task;
            }
            yield new Promise(resolve => setTimeout(resolve, intervalMs));
        }
        throw new Error('Task polling timed out');
    });
}
function generateConversationId() {
    return `conv-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}
function loadFromStorage() {
    if (typeof window === 'undefined')
        return null;
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (!stored)
            return null;
        return JSON.parse(stored);
    }
    catch (_a) {
        return null;
    }
}
function saveToStorage(messages, conversationId) {
    if (typeof window === 'undefined')
        return;
    try {
        const data = { messages, conversationId };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    }
    catch (_a) { }
}
function clearStorage() {
    if (typeof window === 'undefined')
        return;
    try {
        localStorage.removeItem(STORAGE_KEY);
        localStorage.removeItem(CONVERSATION_ID_KEY);
    }
    catch (_a) { }
}
export function ChatWidget() {
    const { data: session } = useSession();
    const typedSession = session;
    const [isOpen, setIsOpen] = useState(false);
    const [message, setMessage] = useState('');
    const [messages, setMessages] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [conversationId, setConversationId] = useState('');
    const messagesEndRef = useRef(null);
    useEffect(() => {
        const stored = loadFromStorage();
        if (stored) {
            setMessages(stored.messages);
            setConversationId(stored.conversationId);
        }
        else {
            setConversationId(generateConversationId());
        }
    }, []);
    useEffect(() => {
        if (conversationId && messages.length > 0) {
            saveToStorage(messages, conversationId);
        }
    }, [messages, conversationId]);
    const scrollToBottom = useCallback(() => {
        var _a;
        (_a = messagesEndRef.current) === null || _a === void 0 ? void 0 : _a.scrollIntoView({ behavior: 'smooth' });
    }, []);
    useEffect(() => { scrollToBottom(); }, [messages, scrollToBottom]);
    const clearChat = useCallback(() => {
        setMessages([]);
        clearStorage();
        setConversationId(generateConversationId());
    }, []);
    const getRequestHeaders = useCallback(() => {
        const headers = {};
        const accessToken = (typedSession === null || typedSession === void 0 ? void 0 : typedSession.accessToken) ||
            (typeof window !== 'undefined'
                ? localStorage.getItem('a2a_token') ||
                    localStorage.getItem('access_token') ||
                    undefined
                : undefined);
        if (accessToken) {
            headers.Authorization = `Bearer ${accessToken}`;
        }
        if (typedSession === null || typedSession === void 0 ? void 0 : typedSession.tenantId) {
            headers['X-Tenant-ID'] = typedSession.tenantId;
        }
        return Object.keys(headers).length ? headers : undefined;
    }, [typedSession === null || typedSession === void 0 ? void 0 : typedSession.accessToken, typedSession === null || typedSession === void 0 ? void 0 : typedSession.tenantId]);
    const sendMessage = (userMessage_1, ...args_1) => __awaiter(this, [userMessage_1, ...args_1], void 0, function* (userMessage, isRetry = false, retryMsgId) {
        const userMsgId = isRetry ? retryMsgId : `user-${Date.now()}`;
        if (!isRetry) {
            const userMsg = {
                id: userMsgId,
                role: 'user',
                content: userMessage,
                timestamp: new Date().toISOString(),
                status: 'sent',
            };
            setMessages(prev => [...prev, userMsg]);
        }
        setIsLoading(true);
        if (isRetry && retryMsgId) {
            setMessages(prev => prev.filter(msg => msg.id !== retryMsgId));
        }
        try {
            const requestHeaders = getRequestHeaders();
            const task = yield createTask(userMessage, requestHeaders);
            const taskId = getTaskId(task);
            if (!taskId) {
                throw new Error('Failed to create task: no task ID returned');
            }
            const aiMsgId = `assistant-${Date.now()}`;
            const aiMsg = {
                id: aiMsgId,
                role: 'assistant',
                content: '',
                timestamp: new Date().toISOString(),
                status: 'sending',
                taskId: taskId,
            };
            setMessages(prev => [...prev, aiMsg]);
            const completedTask = yield pollForCompletion(taskId, undefined, 60, 1000, requestHeaders);
            const parsedResult = parseCodeTetherResult(completedTask.result || '');
            setMessages(prev => prev.map(msg => msg.id === aiMsgId
                ? Object.assign(Object.assign({}, msg), { content: parsedResult, status: 'sent' }) : msg));
        }
        catch (error) {
            const errorContent = error instanceof Error
                ? (error.message === 'Task polling timed out'
                    ? 'Request timed out after 60 seconds. Please try again.'
                    : error.message)
                : 'An error occurred';
            const errorMsg = {
                id: `error-${Date.now()}`,
                role: 'assistant',
                content: errorContent,
                timestamp: new Date().toISOString(),
                status: 'error',
            };
            setMessages(prev => [...prev, errorMsg]);
        }
        finally {
            setIsLoading(false);
        }
    });
    const retryMessage = useCallback((errorMsgId) => {
        const errorIndex = messages.findIndex(m => m.id === errorMsgId);
        if (errorIndex === -1)
            return;
        for (let i = errorIndex - 1; i >= 0; i--) {
            if (messages[i].role === 'user') {
                sendMessage(messages[i].content, true, errorMsgId);
                break;
            }
        }
    }, [messages]);
    const handleSubmit = (e) => {
        e.preventDefault();
        if (message.trim() && !isLoading) {
            sendMessage(message.trim());
            setMessage('');
        }
    };
    return (_jsxs("div", { className: "fixed bottom-6 right-6 z-50", children: [_jsx(AnimatePresence, { children: isOpen && (_jsxs(motion.div, { initial: { opacity: 0, scale: 0.95, y: 20 }, animate: { opacity: 1, scale: 1, y: 0 }, exit: { opacity: 0, scale: 0.95, y: 20 }, transition: { duration: 0.2, ease: 'easeOut' }, className: "absolute bottom-[calc(60px+16px)] right-0 w-[400px] h-[500px] bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 flex flex-col overflow-hidden", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 bg-cyan-500 text-white", children: [_jsx("h3", { className: "font-semibold text-base", children: "Chat with AI" }), _jsxs("div", { className: "flex items-center gap-2", children: [messages.length > 0 && (_jsx("button", { onClick: clearChat, className: "p-1 rounded-full hover:bg-white/20 transition-colors", "aria-label": "Clear chat", title: "Clear chat history", children: _jsx(TrashIcon, { className: "w-5 h-5" }) })), _jsx("button", { onClick: () => setIsOpen(false), className: "p-1 rounded-full hover:bg-white/20 transition-colors", "aria-label": "Close chat", children: _jsx(CloseIcon, { className: "w-5 h-5" }) })] })] }), _jsx("div", { className: "flex-1 p-4 overflow-y-auto bg-gray-50 dark:bg-gray-800", children: messages.length === 0 ? (_jsx("div", { className: "text-center text-gray-500 dark:text-gray-400 text-sm mt-8", children: _jsx("p", { children: "Welcome! How can I help you today?" }) })) : (_jsxs("div", { className: "space-y-3", children: [messages.map(msg => (_jsx("div", { className: `flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`, children: _jsxs("div", { className: "flex flex-col items-start max-w-[80%]", children: [_jsx("div", { className: `px-4 py-2 rounded-2xl text-sm ${msg.role === 'user'
                                                        ? 'bg-cyan-500 text-white rounded-br-md'
                                                        : msg.status === 'error'
                                                            ? 'bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-200 rounded-bl-md'
                                                            : 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-bl-md'}`, children: msg.status === 'sending' ? _jsx(LoadingDots, {}) : _jsx("p", { className: "whitespace-pre-wrap", children: msg.content }) }), msg.status === 'error' && !isLoading && (_jsxs("button", { onClick: () => retryMessage(msg.id), className: "mt-1 flex items-center gap-1 text-xs text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 transition-colors", children: [_jsx(RetryIcon, { className: "w-3 h-3" }), "Retry"] }))] }) }, msg.id))), _jsx("div", { ref: messagesEndRef })] })) }), _jsx("form", { onSubmit: handleSubmit, className: "p-3 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900", children: _jsxs("div", { className: "flex items-center gap-2", children: [_jsx("input", { type: "text", value: message, onChange: e => setMessage(e.target.value), placeholder: "Type a message...", disabled: isLoading, className: "flex-1 px-4 py-2 rounded-full border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent disabled:opacity-50" }), _jsx("button", { type: "submit", disabled: !message.trim() || isLoading, className: "p-2 rounded-full bg-cyan-500 text-white hover:bg-cyan-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors", "aria-label": "Send message", children: _jsx(SendIcon, { className: "w-5 h-5" }) })] }) })] })) }), _jsx(motion.button, { onClick: () => setIsOpen(!isOpen), className: "w-[60px] h-[60px] rounded-full bg-cyan-500 text-white shadow-lg hover:bg-cyan-600 transition-colors flex items-center justify-center", whileHover: { scale: 1.05 }, whileTap: { scale: 0.95 }, "aria-label": isOpen ? 'Close chat' : 'Open chat', children: _jsx(AnimatePresence, { mode: "wait", children: isOpen ? (_jsx(motion.div, { initial: { rotate: -90, opacity: 0 }, animate: { rotate: 0, opacity: 1 }, exit: { rotate: 90, opacity: 0 }, transition: { duration: 0.15 }, children: _jsx(CloseIcon, { className: "w-7 h-7" }) }, "close")) : (_jsx(motion.div, { initial: { rotate: 90, opacity: 0 }, animate: { rotate: 0, opacity: 1 }, exit: { rotate: -90, opacity: 0 }, transition: { duration: 0.15 }, children: _jsx(ChatIcon, { className: "w-7 h-7" }) }, "chat")) }) })] }));
}
