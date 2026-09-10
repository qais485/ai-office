"use client";

import * as React from "react";
import { motion, type Transition } from "framer-motion";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface PerspectiveCarouselItem {
  src: string;
  title: string;
  alt?: string;
}

export interface PerspectiveCarouselProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "onChange"> {
  items: PerspectiveCarouselItem[];
  activeIndex?: number;
  defaultActiveIndex?: number;
  onActiveIndexChange?: (index: number) => void;
  loop?: boolean;
  slideWidth?: number;
  rotationStep?: number;
  inactiveScale?: number;
  transition?: Transition;
  showControls?: boolean;
  showDots?: boolean;
  viewportClassName?: string;
  slideClassName?: string;
  imageClassName?: string;
  labelClassName?: string;
  controlsClassName?: string;
}

const DEFAULT_TRANSITION: Transition = {
  type: "spring",
  bounce: 0.14,
  duration: 0.9,
};

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

export function PerspectiveCarousel({
  items,
  activeIndex,
  defaultActiveIndex = 0,
  onActiveIndexChange,
  loop = false,
  slideWidth = 200,
  rotationStep = 60,
  inactiveScale = 0.85,
  transition = DEFAULT_TRANSITION,
  showControls = true,
  showDots = true,
  viewportClassName,
  slideClassName,
  imageClassName,
  labelClassName,
  controlsClassName,
  className,
  onKeyDown,
  tabIndex,
  ...props
}: PerspectiveCarouselProps) {
  const maxIndex = Math.max(0, items.length - 1);
  const realLen = items.length;

  // ── Seamless infinite loop ─────────────────────────────────────────
  // In loop mode the items are rendered 3× (prev | main | next copies) and
  // the track keeps moving forward forever. After each slide finishes, the
  // virtual index is silently snapped back into the middle copy (duration-0
  // reposition), so the user never sees a "slide back to the start" jump.
  const [virtualIndex, setVirtualIndex] = React.useState(() =>
    loop ? realLen + clamp(defaultActiveIndex, 0, maxIndex) : 0
  );
  const virtualRef = React.useRef(virtualIndex);
  const [snapping, setSnapping] = React.useState(false);

  const [uncontrolledIndex, setUncontrolledIndex] = React.useState(() =>
    clamp(defaultActiveIndex, 0, maxIndex)
  );
  const normalizedIndex = loop
    ? ((virtualIndex % realLen) + realLen) % realLen
    : clamp(activeIndex ?? uncontrolledIndex, 0, maxIndex);
  const currentIndex = clamp(activeIndex ?? normalizedIndex, 0, maxIndex);
  const safeSlideWidth = Math.max(96, slideWidth);
  const safeInactiveScale = clamp(inactiveScale, 0.5, 1);

  React.useEffect(() => {
    virtualRef.current = virtualIndex;
  }, [virtualIndex]);

  const selectSlide = React.useCallback(
    (nextIndex: number) => {
      if (!items.length) {
        return;
      }

      if (loop) {
        const delta = nextIndex - currentIndex;
        // Move forward/backward exactly one step from the current virtual
        // position — never clamped, so the motion keeps its direction.
        let target = virtualRef.current + (delta || 1);
        // Guard only against sliding PAST the rendered copies (3× items).
        // Hitting this requires ~10 clicks with zero completions; re-center
        // silently, then apply the step once the jump has rendered. The
        // normal wrap (into the 3rd copy) is NOT re-centered here — that
        // would kill the forward animation with a duration-0 jump.
        if (target < 0 || target >= realLen * 3) {
          const norm = ((target % realLen) + realLen) % realLen;
          const rebased = norm + realLen;
          setSnapping(true);
          virtualRef.current = rebased;
          setVirtualIndex(rebased);
          window.setTimeout(() => {
            const stepped = rebased + (delta || 1);
            virtualRef.current = stepped;
            setVirtualIndex(stepped);
          }, 40);
          onActiveIndexChange?.(norm);
          return;
        }
        virtualRef.current = target;
        setVirtualIndex(target);
        onActiveIndexChange?.(((target % realLen) + realLen) % realLen);
        return;
      }

      const resolvedIndex = clamp(nextIndex, 0, maxIndex);
      if (activeIndex === undefined) {
        setUncontrolledIndex(resolvedIndex);
      }
      onActiveIndexChange?.(resolvedIndex);
    },
    [activeIndex, currentIndex, items.length, loop, maxIndex, onActiveIndexChange, realLen]
  );

  const renderedItems = React.useMemo(
    () => (loop ? [...items, ...items, ...items] : items),
    [items, loop]
  );

  React.useEffect(() => {
    if (!loop || !snapping) return;
    const id = requestAnimationFrame(() => setSnapping(false));
    return () => cancelAnimationFrame(id);
  }, [loop, snapping]);

  const handleTrackAnimationComplete = () => {
    if (!loop) return;
    const v = virtualRef.current;
    if (v >= realLen * 2 || v < realLen) {
      const norm = ((v % realLen) + realLen) % realLen;
      const fixed = norm + realLen;
      setSnapping(true);
      virtualRef.current = fixed;
      setVirtualIndex(fixed);
    }
  };

  if (!items.length) {
    return null;
  }

  const isPreviousDisabled = !loop && currentIndex === 0;
  const isNextDisabled = !loop && currentIndex === maxIndex;
  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    onKeyDown?.(event);

    if (event.defaultPrevented) {
      return;
    }

    if (event.key === "ArrowLeft") {
      event.preventDefault();
      selectSlide(currentIndex - 1);
    }

    if (event.key === "ArrowRight") {
      event.preventDefault();
      selectSlide(currentIndex + 1);
    }
  };

  return (
    <div
      role="region"
      aria-roledescription="carousel"
      aria-label="Perspective image carousel"
      tabIndex={tabIndex ?? 0}
      onKeyDown={handleKeyDown}
      className={cn("relative isolate flex h-full w-full flex-col", className)}
      {...props}
    >
      <div
        className={cn("relative flex-1 overflow-hidden", viewportClassName)}
        style={{ perspective: "1200px" }}
      >
        <motion.div
          className="absolute left-1/2 top-1/2 flex w-fit -translate-y-1/2 items-center"
          animate={{ x: -((loop ? virtualIndex : currentIndex) * safeSlideWidth + safeSlideWidth / 2) }}
          transition={snapping ? { duration: 0 } : transition}
          onAnimationComplete={handleTrackAnimationComplete}
        >
          {renderedItems.map((item, index) => {
            // Circular distance from the active slide, wrapped to ±realLen/2 —
            // prevents the cumulative rotateY from pushing far cards through
            // 90°/180° (edge-on = invisible, 180° = mirrored), which made
            // cards vanish and re-appear while looping.
            const trackPos = loop ? virtualIndex : currentIndex;
            const rawRel = trackPos - index;
            const rel = loop
              ? (((rawRel % realLen) + realLen) % realLen) > realLen / 2
                ? ((((rawRel % realLen) + realLen) % realLen) - realLen)
                : ((rawRel % realLen) + realLen) % realLen
              : rawRel;
            const isActive = (loop ? virtualIndex : currentIndex) % realLen === index % realLen && (loop || currentIndex === index);

            return (
              <div
                key={`${item.src}-${index}`}
                className="shrink-0"
                style={{ width: safeSlideWidth, perspective: "1200px" }}
              >
                <motion.div
                  className={cn(
                    "flex w-full flex-col items-center gap-3 will-change-transform",
                    slideClassName
                  )}
                  animate={{
                    rotateY: rel * rotationStep,
                    scale: isActive ? 1 : safeInactiveScale,
                  }}
                  transition={transition}
                  style={{ transformStyle: "preserve-3d" }}
                >
                  <button
                    type="button"
                    aria-label={`Show ${item.title}`}
                    aria-current={isActive ? "true" : undefined}
                    className="relative aspect-[3/4] w-full cursor-pointer overflow-hidden rounded-lg"
                    onClick={() => selectSlide(index)}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={item.src}
                      alt={item.alt ?? item.title}
                      draggable={false}
                      className={cn(
                        "absolute inset-0 h-full w-full select-none object-cover shadow-xl",
                        imageClassName
                      )}
                    />
                  </button>

                  <motion.p
                    className={cn("whitespace-nowrap text-sm", labelClassName)}
                    animate={{
                      filter: isActive ? "blur(0px)" : "blur(2px)",
                      opacity: isActive ? 1 : 0,
                    }}
                    transition={transition}
                  >
                    {item.title}
                  </motion.p>
                </motion.div>
              </div>
            );
          })}
        </motion.div>
      </div>

      {showControls && (
        <div
          className={cn(
            "relative z-10 mx-auto mt-3 flex w-fit shrink-0 items-center justify-center gap-3 rounded-full border border-neutral-300/80 bg-neutral-200/70 px-2 text-neutral-700 shadow-sm backdrop-blur-sm dark:border-white/10 dark:bg-neutral-900/70 dark:text-neutral-100",
            controlsClassName
          )}
        >
          <button
            type="button"
            aria-label="Show previous slide"
            disabled={isPreviousDisabled}
            className="inline-flex size-9 items-center justify-center rounded-full transition-colors hover:bg-white/70 disabled:cursor-not-allowed disabled:opacity-35 dark:hover:bg-white/10"
            onClick={() => selectSlide(currentIndex - 1)}
          >
            <ChevronLeft className="size-5" />
          </button>

          {showDots && (
            <div className="flex items-center justify-center gap-2">
              {items.map((item, index) => (
                <button
                  key={`${item.title}-${index}`}
                  type="button"
                  aria-label={`Show slide ${index + 1}: ${item.title}`}
                  aria-current={currentIndex === index ? "true" : undefined}
                  className={cn(
                    "h-2 rounded-full bg-current transition-[width,opacity] duration-300",
                    currentIndex === index ? "w-7 opacity-100" : "w-2 opacity-30"
                  )}
                  onClick={() => selectSlide(index)}
                />
              ))}
            </div>
          )}

          <button
            type="button"
            aria-label="Show next slide"
            disabled={isNextDisabled}
            className="inline-flex size-9 items-center justify-center rounded-full transition-colors hover:bg-white/70 disabled:cursor-not-allowed disabled:opacity-35 dark:hover:bg-white/10"
            onClick={() => selectSlide(currentIndex + 1)}
          >
            <ChevronRight className="size-5" />
          </button>
        </div>
      )}
    </div>
  );
}

export default PerspectiveCarousel;
