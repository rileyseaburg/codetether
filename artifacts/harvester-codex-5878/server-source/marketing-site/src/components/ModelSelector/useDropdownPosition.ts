import { useState, useEffect } from 'react'

export const useDropdownPosition = (isOpen: boolean, inputRef: React.RefObject<HTMLInputElement | null>) => {
    const [pos, setPos] = useState({ top: 0, left: 0, width: 0 })
    
    const updatePos = () => {
        if (isOpen && inputRef.current) {
            const r = inputRef.current.getBoundingClientRect()
            setPos({ top: r.bottom + window.scrollY, left: r.left + window.scrollX, width: r.width })
        }
    }
    
    useEffect(() => {
        updatePos()
    }, [isOpen])
    
    useEffect(() => {
        window.addEventListener('resize', updatePos)
        window.addEventListener('scroll', updatePos, true)
        return () => {
            window.removeEventListener('resize', updatePos)
            window.removeEventListener('scroll', updatePos, true)
        }
    }, [isOpen])
    
    return pos
}
