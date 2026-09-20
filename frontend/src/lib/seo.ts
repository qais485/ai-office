import { useEffect } from 'react'

interface SEOData {
  title: string
  description: string
  canonical?: string
  ogImage?: string
  ogType?: string
  noindex?: boolean
}

const SITE_NAME = 'AI Virtual Office'
const DEFAULT_OG_IMAGE = 'https://aaoffice.onrender.com/og-image.png'
const SITE_URL = 'https://aaoffice.onrender.com'

const PAGE_SEO: Record<string, SEOData> = {
  '/': {
    title: 'AI Virtual Office — Hire AI Agents for Telegram, Discord & Email',
    description: 'Self-hosted AI virtual office platform. Hire AI agents into virtual rooms, connect Telegram, Discord & Gmail, and let them handle customers 24/7 with your company knowledge.',
    ogType: 'website',
  },
  '/login': {
    title: 'Sign In — AI Virtual Office',
    description: 'Sign in to AI Virtual Office with your Google account to manage AI agents, connect channels, and automate customer support.',
    noindex: true,
  },
  '/privacy': {
    title: 'Privacy Policy — AI Virtual Office',
    description: 'Privacy policy for AI Virtual Office. Learn how we handle your data, connected service credentials, and AI agent processing.',
  },
  '/terms': {
    title: 'Terms of Service — AI Virtual Office',
    description: 'Terms of service for AI Virtual Office. Read the rules for using the platform, connected services, and AI agent automation.',
  },
  '/office': {
    title: 'Virtual Office — AI Virtual Office',
    description: 'View your AI virtual office rooms, monitor agent activity, and manage real-time tasks across connected channels.',
    noindex: true,
  },
  '/dashboard': {
    title: 'Dashboard — AI Virtual Office',
    description: 'Overview dashboard for your AI Virtual Office. Track agent performance, activity, and connected integrations.',
    noindex: true,
  },
  '/agents': {
    title: 'My Agents — AI Virtual Office',
    description: 'Manage your hired AI agents, their configurations, permissions, and channel assignments.',
    noindex: true,
  },
  '/knowledge': {
    title: 'Knowledge Base — AI Virtual Office',
    description: 'Upload and manage company knowledge sources for AI agent retrieval. Semantic search with per-agent access control.',
    noindex: true,
  },
  '/integrations': {
    title: 'Integrations — AI Virtual Office',
    description: 'Connect Telegram, Discord, Gmail, Google Drive, and other services to your AI Virtual Office agents.',
    noindex: true,
  },
  '/ceo': {
    title: 'CEO Dashboard — AI Virtual Office',
    description: 'CEO overview of AI agent activity, pending approvals, and company-wide performance metrics.',
    noindex: true,
  },
  '/ceo/inbox': {
    title: 'CEO Inbox — AI Virtual Office',
    description: 'Review and approve AI agent actions held for CEO approval. Manage sensitive and automated responses.',
    noindex: true,
  },
}

export function useSEO(pagePath: string) {
  useEffect(() => {
    const seo = PAGE_SEO[pagePath] || PAGE_SEO['/']
    const canonical = seo.canonical || `${SITE_URL}${pagePath}`

    // Title
    document.title = seo.title

    // Meta description
    setMeta('description', seo.description)

    // Robots
    if (seo.noindex) {
      setMeta('robots', 'noindex, nofollow')
    } else {
      setMeta('robots', 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1')
    }

    // Canonical
    setLink('canonical', canonical)

    // Open Graph
    setMeta('og:type', seo.ogType || 'website')
    setMeta('og:url', canonical)
    setMeta('og:title', seo.title)
    setMeta('og:description', seo.description)
    setMeta('og:image', seo.ogImage || DEFAULT_OG_IMAGE)
    setMeta('og:site_name', SITE_NAME)
    setMeta('og:locale', 'en_US')

    // Twitter Card
    setMeta('twitter:card', 'summary_large_image')
    setMeta('twitter:title', seo.title)
    setMeta('twitter:description', seo.description)
    setMeta('twitter:image', seo.ogImage || DEFAULT_OG_IMAGE)
  }, [pagePath])
}

function setMeta(name: string, content: string) {
  let el = document.querySelector(`meta[name="${name}"], meta[property="${name}"]`)
  if (!el) {
    el = document.createElement('meta')
    if (name.startsWith('og:')) {
      el.setAttribute('property', name)
    } else {
      el.setAttribute('name', name)
    }
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

function setLink(rel: string, href: string) {
  let el = document.querySelector(`link[rel="${rel}"]`)
  if (!el) {
    el = document.createElement('link')
    el.setAttribute('rel', rel)
    document.head.appendChild(el)
  }
  el.setAttribute('href', href)
}
