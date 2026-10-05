import type { ReactNode } from 'react'
import { useState } from 'react'
import { motion, useDragControls } from 'framer-motion'
import { ModalHeader } from './ModalHeader'

interface AIPRDModalProps {
    title: string
    subtitle: string
    headerActions?: ReactNode
    footerActions?: ReactNode
    onCancel: () => void
    onMinimize?: () => void
    onSwitchToManual: () => void
    children: ReactNode
    visible?: boolean
}

export function AIPRDModal({ title, subtitle, headerActions, footerActions, onCancel, onMinimize, onSwitchToManual, children, visible = true }: AIPRDModalProps) {
    const dragControls = useDragControls()
    const [dimensions, setDimensions] = useState({ width: 1200, height: 800 })
    const [position, setPosition] = useState({ x: 0, y: 0 })
    const [isResizing, setIsResizing] = useState(false)
    const [hoveredEdge, setHoveredEdge] = useState<string | null>(null)

    const startDrag = (e: React.MouseEvent | React.PointerEvent) => {
        // Don't drag if we're selecting text (shift+click or dragging on text)
        const selection = window.getSelection()
        if (selection && selection.toString().length > 0) {
            return
        }
        setIsResizing(false)
        e.preventDefault()
        // Convert MouseEvent to PointerEvent if needed
        if (e instanceof MouseEvent) {
            const pointerEvent = new PointerEvent('pointerdown', {
                pointerId: 1,
                clientX: e.clientX,
                clientY: e.clientY,
                bubbles: e.bubbles,
                cancelable: e.cancelable,
            })
            dragControls.start(pointerEvent, { snapToCursor: false })
        } else {
            dragControls.start(e as any, { snapToCursor: false })
        }
    }

    const startResize = (edge: string) => (e: React.MouseEvent) => {
        e.preventDefault()
        e.stopPropagation()
        setIsResizing(true)
        
        const startX = e.clientX
        const startY = e.clientY
        const startWidth = dimensions.width
        const startHeight = dimensions.height
        const startPosX = position.x
        const startPosY = position.y

        const handleMouseMove = (moveEvent: MouseEvent) => {
            const deltaX = moveEvent.clientX - startX
            const deltaY = moveEvent.clientY - startY

            let newWidth = startWidth
            let newHeight = startHeight
            let newX = startPosX
            let newY = startPosY

            if (edge.includes('e')) {
                newWidth = Math.max(600, startWidth + deltaX)
            }
            if (edge.includes('w')) {
                newWidth = Math.max(600, startWidth - deltaX)
                newX = startPosX + deltaX
            }
            if (edge.includes('s')) {
                newHeight = Math.max(400, startHeight + deltaY)
            }
            if (edge.includes('n')) {
                newHeight = Math.max(400, startHeight - deltaY)
                newY = startPosY + deltaY
            }

            setDimensions({ width: newWidth, height: newHeight })
            setPosition({ x: newX, y: newY })
        }

        const handleMouseUp = () => {
            document.removeEventListener('mousemove', handleMouseMove)
            document.removeEventListener('mouseup', handleMouseUp)
            setIsResizing(false)
            setHoveredEdge(null)
        }

        document.addEventListener('mousemove', handleMouseMove)
        document.addEventListener('mouseup', handleMouseUp)
    }

    const handleEdgeHover = (edge: string) => () => setHoveredEdge(edge)
    const handleEdgeLeave = () => setHoveredEdge(null)

    // SVG icons for resize handles
    const dotsIcon = (
        <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
            <circle cx="4" cy="4" r="1.5"/>
            <circle cx="4" cy="12" r="1.5"/>
            <circle cx="12" cy="4" r="1.5"/>
            <circle cx="12" cy="8" r="1.5"/>
            <circle cx="12" cy="12" r="1.5"/>
            <circle cx="8" cy="12" r="1.5"/>
        </svg>
    )

    const hDotsIcon = (
        <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
            <circle cx="8" cy="8" r="1.5"/>
            <circle cx="4" cy="8" r="1.5"/>
            <circle cx="12" cy="8" r="1.5"/>
        </svg>
    )

    const vDotsIcon = (
        <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
            <circle cx="8" cy="4" r="1.5"/>
            <circle cx="8" cy="8" r="1.5"/>
            <circle cx="8" cy="12" r="1.5"/>
        </svg>
    )

    const grabIcon = (
        <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
            <path d="M7 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM7 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM4 7a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM4 13a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM13 7a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM13 13a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/>
        </svg>
    )

    // Don't render anything if not visible (but component stays mounted to preserve state)
    if (!visible) {
        return null
    }

    return (
        <div 
            className="fixed inset-0 z-50 bg-black/50 p-4"
            onClick={(e) => {
                // Only minimize if clicking directly on the backdrop, not on the modal
                // This preserves chat state - user can reopen with AI Assist button
                if (e.target === e.currentTarget) {
                    if (onMinimize) {
                        onMinimize()
                    } else {
                        onCancel()
                    }
                }
            }}
        >
            {/* Help tip */}
            <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2 bg-gray-900/80 text-white text-sm px-4 py-2 rounded-full backdrop-blur-sm pointer-events-none select-none">
                Click outside to minimize • Pull edges to resize • Drag top bar to move
            </div>
            <motion.div
                drag={!isResizing}
                dragControls={dragControls}
                dragMomentum={false}
                dragElastic={0}
                style={{
                    width: dimensions.width,
                    height: dimensions.height,
                    position: 'absolute',
                    left: `calc(50% - ${dimensions.width / 2}px + ${position.x}px)`,
                    top: `calc(50% - ${dimensions.height / 2}px + ${position.y}px)`,
                }}
                onDrag={(e: any, info: any) => setPosition(prev => ({
                    x: prev.x + info.delta.x,
                    y: prev.y + info.delta.y
                }))}
                className={`overflow-hidden rounded-xl bg-white dark:bg-gray-800 shadow-2xl flex flex-col relative transition-shadow ${isResizing ? 'shadow-cyan-500/50' : ''}`}
            >
                <ModalHeader 
                    title={title} 
                    subtitle={subtitle} 
                    onCancel={onCancel} 
                    onSwitchToManual={onSwitchToManual}
                    onMouseDown={startDrag}
                    dragIcon={grabIcon}
                />
                <div className="flex-1 overflow-auto pointer-events-none">
                    <div className="pointer-events-auto">
                        {children}
                    </div>
                </div>
                {footerActions && (
                    <div className="pointer-events-none">
                        {footerActions}
                    </div>
                )}
                
                {/* Top edge */}
                <div 
                    className={`absolute inset-x-4 top-0 h-6 flex items-center justify-center cursor-ns-resize z-50 transition-all ${
                        hoveredEdge === 'n' ? 'bg-cyan-500/30 border-b border-cyan-400' : ''
                    }`}
                    onMouseEnter={handleEdgeHover('n')}
                    onMouseLeave={handleEdgeLeave}
                    onMouseDown={startResize('n')}
                >
                    <div className="flex gap-1.5">
                        <div className="w-1.5 h-1.5 bg-gray-400 rounded-full"/>
                        <div className="w-1.5 h-1.5 bg-gray-400 rounded-full"/>
                        <div className="w-1.5 h-1.5 bg-gray-400 rounded-full"/>
                    </div>
                </div>
                
                {/* Bottom edge */}
                <div 
                    className={`absolute inset-x-4 bottom-0 h-6 flex items-center justify-center cursor-ns-resize z-50 transition-all ${
                        hoveredEdge === 's' ? 'bg-cyan-500/30 border-t border-cyan-400' : ''
                    }`}
                    onMouseEnter={handleEdgeHover('s')}
                    onMouseLeave={handleEdgeLeave}
                    onMouseDown={startResize('s')}
                >
                    <div className="flex gap-1.5">
                        <div className="w-1.5 h-1.5 bg-gray-400 rounded-full"/>
                        <div className="w-1.5 h-1.5 bg-gray-400 rounded-full"/>
                        <div className="w-1.5 h-1.5 bg-gray-400 rounded-full"/>
                    </div>
                </div>
                
                {/* Left edge */}
                <div 
                    className={`absolute inset-y-4 left-0 w-6 flex items-center justify-center cursor-ew-resize z-50 transition-all ${
                        hoveredEdge === 'w' ? 'bg-cyan-500/30 border-r border-cyan-400' : ''
                    }`}
                    onMouseEnter={handleEdgeHover('w')}
                    onMouseLeave={handleEdgeLeave}
                    onMouseDown={startResize('w')}
                >
                    <div className="flex flex-col gap-1.5">
                        <div className="w-1.5 h-1.5 bg-gray-400 rounded-full"/>
                        <div className="w-1.5 h-1.5 bg-gray-400 rounded-full"/>
                        <div className="w-1.5 h-1.5 bg-gray-400 rounded-full"/>
                    </div>
                </div>
                
                {/* Right edge */}
                <div 
                    className={`absolute inset-y-4 right-0 w-6 flex items-center justify-center cursor-ew-resize z-50 transition-all ${
                        hoveredEdge === 'e' ? 'bg-cyan-500/30 border-l border-cyan-400' : ''
                    }`}
                    onMouseEnter={handleEdgeHover('e')}
                    onMouseLeave={handleEdgeLeave}
                    onMouseDown={startResize('e')}
                >
                    <div className="flex flex-col gap-1.5">
                        <div className="w-1.5 h-1.5 bg-gray-400 rounded-full"/>
                        <div className="w-1.5 h-1.5 bg-gray-400 rounded-full"/>
                        <div className="w-1.5 h-1.5 bg-gray-400 rounded-full"/>
                    </div>
                </div>
                
                {/* Corner dots */}
                {/* Top-left */}
                <div 
                    className={`absolute top-0 left-0 w-8 h-8 flex items-start justify-start p-1.5 cursor-nwse-resize z-50 transition-all ${
                        hoveredEdge === 'nw' ? 'bg-cyan-500/30 rounded-tr-lg rounded-bl-lg' : ''
                    }`}
                    onMouseEnter={handleEdgeHover('nw')}
                    onMouseLeave={handleEdgeLeave}
                    onMouseDown={startResize('nw')}
                >
                    <svg className="w-4 h-4 text-gray-400" viewBox="0 0 16 16" fill="currentColor">
                        <circle cx="4" cy="4" r="1.5"/>
                        <circle cx="4" cy="8" r="1.5"/>
                        <circle cx="8" cy="4" r="1.5"/>
                    </svg>
                </div>
                
                {/* Top-right */}
                <div 
                    className={`absolute top-0 right-0 w-8 h-8 flex items-start justify-end p-1.5 cursor-nesw-resize z-50 transition-all ${
                        hoveredEdge === 'ne' ? 'bg-cyan-500/30 rounded-tl-lg rounded-br-lg' : ''
                    }`}
                    onMouseEnter={handleEdgeHover('ne')}
                    onMouseLeave={handleEdgeLeave}
                    onMouseDown={startResize('ne')}
                >
                    <svg className="w-4 h-4 text-gray-400" viewBox="0 0 16 16" fill="currentColor">
                        <circle cx="12" cy="4" r="1.5"/>
                        <circle cx="12" cy="8" r="1.5"/>
                        <circle cx="8" cy="4" r="1.5"/>
                    </svg>
                </div>
                
                {/* Bottom-left */}
                <div 
                    className={`absolute bottom-0 left-0 w-8 h-8 flex items-end justify-start p-1.5 cursor-nesw-resize z-50 transition-all ${
                        hoveredEdge === 'sw' ? 'bg-cyan-500/30 rounded-tr-lg rounded-bl-lg' : ''
                    }`}
                    onMouseEnter={handleEdgeHover('sw')}
                    onMouseLeave={handleEdgeLeave}
                    onMouseDown={startResize('sw')}
                >
                    <svg className="w-4 h-4 text-gray-400" viewBox="0 0 16 16" fill="currentColor">
                        <circle cx="4" cy="8" r="1.5"/>
                        <circle cx="4" cy="12" r="1.5"/>
                        <circle cx="8" cy="12" r="1.5"/>
                    </svg>
                </div>
                
                {/* Bottom-right */}
                <div 
                    className={`absolute bottom-0 right-0 w-8 h-8 flex items-end justify-end p-1.5 cursor-nwse-resize z-50 transition-all ${
                        hoveredEdge === 'se' ? 'bg-cyan-500/30 rounded-tl-lg rounded-br-lg' : ''
                    }`}
                    onMouseEnter={handleEdgeHover('se')}
                    onMouseLeave={handleEdgeLeave}
                    onMouseDown={startResize('se')}
                >
                    <svg className="w-4 h-4 text-gray-400" viewBox="0 0 16 16" fill="currentColor">
                        <circle cx="12" cy="8" r="1.5"/>
                        <circle cx="8" cy="12" r="1.5"/>
                        <circle cx="12" cy="12" r="1.5"/>
                    </svg>
                </div>
            </motion.div>
        </div>
    )
}
