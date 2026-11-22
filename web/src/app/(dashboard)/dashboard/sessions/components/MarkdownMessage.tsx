'use client'

import React, { useMemo } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'
import { MarkdownComponents, looksLikeDiff, diffLineClass, DiffBlock } from './MarkdownComponents'
import { safeParseJson, parseJsonPayload, formatJsonValue, getJsonSummary } from './JsonHelpers'
import { CopyButton } from './CopyButton'
import { JsonNode } from './JsonNode'
import { JsonMessage } from './JsonMessage'
import { StructuredMessage } from './StructuredMessage'
import type { ParsedJsonPayload, JsonValue } from './JsonHelpers'

type OpencodeTextPart = {
    type: 'text'
    text: string
}

type OpencodeReasoningPart = {
    type: 'reasoning'
    text: string
}

type OpencodeMessagePart = OpencodeTextPart | OpencodeReasoningPart

type OpencodeMessageText = OpencodeMessagePart['text']

interface MarkdownMessageProps {
    text: OpencodeMessageText
}

const remarkPlugins = [remarkGfm, remarkBreaks]

function MarkdownMessageInner({ text }: MarkdownMessageProps) {
    const jsonPayload = useMemo(() => {
        if (!text) return null
        return parseJsonPayload(text)
    }, [text])

    const content = useMemo(() => {
        if (!text || jsonPayload) return null
        return (
            <ReactMarkdown remarkPlugins={remarkPlugins} components={MarkdownComponents}>
                {text}
            </ReactMarkdown>
        )
    }, [text, jsonPayload])

    if (!text) return null

    return (
        <div className="text-sm leading-relaxed wrap-break-word">
            {jsonPayload ? <StructuredMessage payload={jsonPayload as ParsedJsonPayload} /> : content}
        </div>
    )
}

export const MarkdownMessage = React.memo(MarkdownMessageInner)
MarkdownMessage.displayName = 'MarkdownMessage'
