import { useState, useLayoutEffect } from 'react'

export const useDropdownPosition = (
  isOpen: boolean,
  inputRef: React.RefObject<HTMLInputElement | null>,
) => {
  const [pos, setPos] = useState({
    top: 0,
    left: 0,
    width: 0,
    above: false,
    maxHeight: 448,
  })

  useLayoutEffect(() => {
    if (!isOpen) return
    const updatePos = () => {
      if (!inputRef.current) return
      const r = inputRef.current.getBoundingClientRect()
      // The popup is fixed: its coordinates are viewport-relative, not
      // document-relative. Adding page scroll moves it away from the field.
      const below = window.innerHeight - r.bottom - 8
      const above = below < 200 && r.top > below
      const width = Math.min(r.width, Math.max(0, window.innerWidth - 16))
      const next = {
        top: above ? r.top - 8 : r.bottom,
        left: Math.max(8, Math.min(r.left, window.innerWidth - width - 8)),
        width,
        above,
        maxHeight: Math.max(80, Math.min(448, above ? r.top - 8 : below)),
      }
      setPos((previous) =>
        Object.keys(next).every(
          (key) =>
            previous[key as keyof typeof next] ===
            next[key as keyof typeof next],
        )
          ? previous
          : next,
      )
    }
    updatePos()
    window.addEventListener('resize', updatePos)
    window.addEventListener('scroll', updatePos, true)
    const observer =
      typeof ResizeObserver === 'undefined'
        ? undefined
        : new ResizeObserver(updatePos)
    if (inputRef.current) observer?.observe(inputRef.current)
    return () => {
      window.removeEventListener('resize', updatePos)
      window.removeEventListener('scroll', updatePos, true)
      observer?.disconnect()
    }
  }, [isOpen, inputRef])

  return pos
}
