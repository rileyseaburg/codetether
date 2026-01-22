'use client'

import { createContext } from 'react'
import type { JsonExpandContextValue } from './JsonHelpers'

export const JsonExpandContext = createContext<JsonExpandContextValue>({
    action: null,
    version: 0,
})
