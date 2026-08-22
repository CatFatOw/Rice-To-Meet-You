import { useCallback, useEffect, useState } from 'react';

/**
 * Fullscreen toggle for a single element. Tracks the real browser state via
 * `fullscreenchange`, so Esc / F11 / browser chrome stay in sync with the UI.
 *
 * Pass the ref of the element that should fill the screen:
 *   const panelRef = useRef<HTMLElement>(null);
 *   const { isFullscreen, toggleFullscreen } = useFullscreen(panelRef);
 */
export function useFullscreen(targetRef: React.RefObject<HTMLElement | null>) {
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const handleChange = () => {
      setIsFullscreen(document.fullscreenElement === targetRef.current);
    };

    document.addEventListener('fullscreenchange', handleChange);
    return () => document.removeEventListener('fullscreenchange', handleChange);
  }, [targetRef]);

  const toggleFullscreen = useCallback(async () => {
    const target = targetRef.current;
    if (!target) return;

    try {
      if (document.fullscreenElement === target) {
        await document.exitFullscreen();
      } else {
        await target.requestFullscreen();
      }
    } catch (error) {
      console.error('Failed to toggle fullscreen', error);
    }
  }, [targetRef]);

  return { isFullscreen, toggleFullscreen };
}

export default useFullscreen;