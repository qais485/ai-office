import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { MotionConfig } from 'framer-motion'
import { useAuthStore } from '../stores/useAuthStore'
import { FlipFadeText } from '@/components/ui/flip-fade-text'
import { PerspectiveCarousel } from '@/components/ui/perspective-carousel'

/** Deterministic gradient slide images (no external assets needed). */
function gradientSlide(from: string, to: string): string {
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800">` +
    `<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">` +
    `<stop offset="0%" stop-color="${from}"/><stop offset="100%" stop-color="${to}"/>` +
    `</linearGradient></defs>` +
    `<rect width="600" height="800" fill="url(#g)"/>` +
    `<circle cx="470" cy="140" r="180" fill="white" opacity="0.06"/>` +
    `<circle cx="110" cy="640" r="220" fill="black" opacity="0.12"/>` +
    `</svg>`
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}

const CAROUSEL_SLIDES = [
  { src: gradientSlide('#4f46e5', '#7c3aed'), title: 'AI Agents', alt: 'AI Agents' },
  { src: gradientSlide('#0e7490', '#0284c7'), title: 'Telegram', alt: 'Telegram channel' },
  { src: gradientSlide('#5b21b6', '#a21caf'), title: 'Discord', alt: 'Discord channel' },
  { src: gradientSlide('#b45309', '#dc2626'), title: 'Email', alt: 'Email channel' },
  { src: gradientSlide('#065f46', '#059669'), title: 'Knowledge', alt: 'Knowledge base' },
]

const FLIP_WORDS = ['Customers', 'Emails', 'Telegram', 'Drive Files', 'Meetings']

/**
 * Custom card images: drop Card1.png, Card2.png, … into `frontend/public/`
 * and they replace the built-in gradient textures (index 0 → Card1.png).
 * Missing files silently keep the gradient fallback.
 */
function useOptionalCardImages(fallbacks: string[]): string[] {
  const [srcs, setSrcs] = useState<string[]>(fallbacks)

  useEffect(() => {
    let cancelled = false
    fallbacks.forEach((_, i) => {
      const img = new Image()
      img.onload = () => {
        if (cancelled) return
        setSrcs((prev) => {
          if (prev[i] === `/Card${i + 1}.png`) return prev
          const next = [...prev]
          next[i] = `/Card${i + 1}.png`
          return next
        })
      }
      // onerror → keep the gradient fallback
      img.src = `/Card${i + 1}.png`
    })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return srcs
}

const HomePage = () => {
  const { isAuthenticated } = useAuthStore()
  const [isMobile, setIsMobile] = useState(false)

  // Card1..Card5.png → carousel slides.
  const carouselSrcs = useOptionalCardImages(CAROUSEL_SLIDES.map((s) => s.src))
  const carouselItems = CAROUSEL_SLIDES.map((slide, i) => ({
    ...slide,
    src: carouselSrcs[i],
  }))

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 640px)')
    const update = () => setIsMobile(mq.matches)
    update()
    mq.addEventListener('change', update)
    return () => mq.removeEventListener('change', update)
  }, [])

  return (
    <MotionConfig reducedMotion="user">
      <section
        aria-label="Hero"
        className="relative flex min-h-[100svh] w-full flex-col overflow-hidden bg-[#070710]"
      >
        {/* Ambient glows */}
        <div aria-hidden className="pointer-events-none absolute inset-0">
          <div className="absolute -top-40 left-1/2 h-[560px] w-[900px] -translate-x-1/2 rounded-full bg-indigo-600/20 blur-[140px]" />
          <div className="absolute bottom-0 right-[-10%] h-[420px] w-[520px] rounded-full bg-purple-600/10 blur-[120px]" />
          <div
            aria-hidden
            className="absolute inset-0 opacity-[0.35] [background-image:linear-gradient(to_right,rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.04)_1px,transparent_1px)] [background-size:64px_64px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_35%,black,transparent)]"
          />
        </div>

        {/* ── Text block ─────────────────────────────────────────── */}
        <div className="relative z-10 mx-auto flex w-full max-w-5xl flex-col items-center px-4 pt-16 text-center sm:px-6 sm:pt-20">
          <span className="inline-flex items-center gap-2 rounded-full border border-indigo-500/25 bg-indigo-500/10 px-3.5 py-1 text-xs font-medium text-indigo-300">
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
            AI Virtual Office
          </span>

          <h1 className="mt-6 text-3xl font-bold tracking-tight text-white sm:text-4xl lg:text-5xl">
            <span className="sr-only">AI Virtual Office — AI agents that handle your customers, emails and files</span>
            <span aria-hidden className="block">
              Hire AI agents that handle your
            </span>
            <span aria-hidden className="mt-2 block">
              <FlipFadeText
                words={FLIP_WORDS}
                interval={2600}
                className="min-h-0 py-1"
                textClassName="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-indigo-300 via-purple-300 to-indigo-300 dark:text-transparent"
              />
            </span>
          </h1>

          <p className="mt-5 max-w-2xl text-balance text-base text-white/60 sm:mt-6 sm:text-lg">
            Connect Telegram, Discord and email — your agents answer customers around the clock,
            grounded in your company knowledge, with everything sensitive held for your approval.
          </p>

          <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:mt-9 sm:flex-row">
            {isAuthenticated ? (
              <>
                <Link
                  to="/office"
                  className="w-full sm:w-auto inline-flex items-center justify-center px-6 py-3 rounded-lg bg-indigo-600 text-white font-medium text-sm hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 transition-colors"
                >
                  Enter Virtual Office
                </Link>
                <Link
                  to="/dashboard"
                  className="w-full sm:w-auto inline-flex items-center justify-center px-6 py-3 rounded-lg border border-indigo-500/40 text-indigo-300 font-medium text-sm hover:bg-indigo-500/15 hover:text-indigo-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 transition-colors"
                >
                  View Dashboard
                </Link>
              </>
            ) : (
              <Link
                to="/login"
                className="w-full sm:w-auto inline-flex items-center justify-center px-6 py-3 rounded-lg bg-indigo-600 text-white font-medium text-sm hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 transition-colors"
              >
                Sign in with Google
              </Link>
            )}
          </div>
        </div>

        {/* ── 3D perspective carousel ────────────────────────────── */}
        <div className="relative z-10 mx-auto w-full max-w-3xl px-4 pt-10 sm:px-6 sm:pt-12">
          <div className="h-[300px] sm:h-[350px]">
            <PerspectiveCarousel
              items={carouselItems}
              loop
              slideWidth={isMobile ? 130 : 190}
              rotationStep={45}
              inactiveScale={0.82}
              showDots
              viewportClassName="[mask-image:linear-gradient(to_right,transparent,black_12%,black_88%,transparent)]"
              imageClassName="ring-1 ring-white/10 shadow-indigo-950/60"
              labelClassName="text-white/70"
              controlsClassName="border-white/10 bg-white/5 backdrop-blur-md text-white/80"
            />
          </div>
        </div>
      </section>
    </MotionConfig>
  )
}

export default HomePage
