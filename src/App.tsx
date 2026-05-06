import { useEffect, useMemo, useState, type PointerEvent } from 'react'
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion'
import { Award, BadgeCheck, Check, ChevronRight, Clock3, Copy, Crown, Diamond, Eye, Flame, Gem, LockKeyhole, MessageCircle, Music2, Radio, Search, ShieldCheck, Sparkles, Star, Smartphone, Trophy, WandSparkles, Zap } from 'lucide-react'

type VipNumber = {
  number: string
  price: string
  status?: string
  tier: string
}

type Catalog = Record<string, VipNumber[]>

const API_URL = 'https://vip-boti.onrender.com/api/full_catalog'
const HERO_NUMBER = '07 22 33 33 31'
const WHATSAPP_BASE = 'https://wa.me/212638388885?text='
const BRAND_NAME = 'Inwi VIP Number'

const fallbackCatalog: Catalog = {
  Diamond: [
    { number: '07 03 31 33 13', price: '200 DH', status: 'available', tier: 'Diamond' },
    { number: '06 38 38 88 85', price: '200 DH', status: 'available', tier: 'Diamond' },
    { number: '06 05 55 51 18', price: '200 DH', status: 'available', tier: 'Diamond' },
    { number: '07 12 11 12 28', price: '200 DH', status: 'available', tier: 'Diamond' },
    { number: '06 87 77 79 50', price: '200 DH', status: 'available', tier: 'Diamond' },
  ],
  Gold: [
    { number: '06 29 01 11 13', price: '150 DH', status: 'available', tier: 'Gold' },
    { number: '06 29 94 44 41', price: '150 DH', status: 'available', tier: 'Gold' },
    { number: '06 87 77 79 50', price: '150 DH', status: 'available', tier: 'Gold' },
    { number: '07 17 58 88 87', price: '150 DH', status: 'available', tier: 'Gold' },
    { number: '07 24 44 41 97', price: '150 DH', status: 'available', tier: 'Gold' },
  ],
  Inwi: [
    { number: '06 99 99 34 38', price: '200 DH', status: 'available', tier: 'Inwi' },
  ],
  Silver: [
    { number: '06 33 37 42 84', price: '100 DH', status: 'available', tier: 'Silver' },
  ],
}

const buyers = [
  { name: 'Reda', city: 'Fes' },
  { name: 'Yassine', city: 'Casa' },
  { name: 'Mehdi', city: 'Marrakech' },
  { name: 'Othmane', city: 'Tanger' },
  { name: 'Anass', city: 'Rabat' },
  { name: 'Soufiane', city: 'Agadir' },
]

const normalizePhone = (number) => number.replace(/\D/g, '')

const removedNumbers = new Set([
  '0706888818',
  '0604050559',
  '0722232325',
  '0717474447',
].map(normalizePhone))

const tierOrder = ['Diamond', 'Gold', 'Inwi', 'Silver']
const getWhatsAppUrl = (number, price, tier) => WHATSAPP_BASE + encodeURIComponent(price && tier ? 'Salam, bghit nreservi had nmra VIP: ' + number + ' - ' + price + ' - Tier: ' + tier : number)

const getPatternLabel = (number) => {
  const clean = normalizePhone(number)
  if (/3333|4444|1111|9999|8888/.test(clean)) return 'Ultra Repeat'
  if (/777|888|999|333|111|444/.test(clean)) return 'Lucky Triple'
  if (/00$/.test(clean)) return 'Clean Ending'
  if (/(\d)\1.*(\d)\2/.test(clean)) return 'Mirror Style'
  return 'Easy Recall'
}

const getRarityScore = (item) => {
  const clean = normalizePhone(item.number)
  let score = item.price === '200 DH' ? 88 : item.price === '150 DH' ? 78 : 68
  if (/3333|4444|1111|9999|8888/.test(clean)) score += 4
  if (/777|888|999|333|111|444/.test(clean)) score += 3
  if (/00$/.test(clean)) score += 2
  return Math.min(score, 99)
}

const mergeWithProtectedCatalog = (apiCatalog) => {
  const merged = {}

  Object.entries(apiCatalog).forEach(([tier, numbers]) => {
    const safeNumbers = numbers.filter((item) => !removedNumbers.has(normalizePhone(item.number)))
    if (safeNumbers.length) merged[tier] = safeNumbers
  })

  Object.entries(fallbackCatalog).forEach(([tier, numbers]) => {
    if (!merged[tier]) merged[tier] = []

    numbers.forEach((protectedItem) => {
      const protectedKey = normalizePhone(protectedItem.number)

      Object.keys(merged).forEach((existingTier) => {
        merged[existingTier] = merged[existingTier].filter((item) => normalizePhone(item.number) !== protectedKey)
      })

      if (!removedNumbers.has(protectedKey)) {
        merged[tier].push(protectedItem)
      }
    })
  })

  return Object.entries(merged).reduce((acc, [tier, numbers]) => {
    const cleanNumbers = numbers.filter((item) => !removedNumbers.has(normalizePhone(item.number)))
    if (cleanNumbers.length) acc[tier] = cleanNumbers
    return acc
  }, {})
}

const normalizeCatalog = (data) => {
  if (!data || typeof data !== 'object') return fallbackCatalog

  return Object.entries(data).reduce((acc, [tier, value]) => {
    if (!Array.isArray(value)) return acc

    const items = value
      .map((item) => item)
      .filter((item) => typeof item.number === 'string' && typeof item.price === 'string')
      .map((item) => ({
        number: item.number,
        price: item.price,
        status: item.status ?? 'available',
        tier: item.tier ?? tier,
      }))

    if (items.length) acc[tier] = items
    return acc
  }, {})
}

function App() {
  const [catalog, setCatalog] = useState(fallbackCatalog)
  const [loading, setLoading] = useState(true)
  const [catalogSource, setCatalogSource] = useState('fallback')
  const [popupSale, setPopupSale] = useState(fallbackCatalog.Diamond[0])
  const [popupBuyer, setPopupBuyer] = useState(buyers[0])
  const [popupVisible, setPopupVisible] = useState(false)
  const [welcomeVisible, setWelcomeVisible] = useState(false)
  const [copiedNumber, setCopiedNumber] = useState(null)
  const [spotlightIndex, setSpotlightIndex] = useState(0)
  const [chatOpen, setChatOpen] = useState(false)
  const [chatMessages, setChatMessages] = useState([{ role: 'bot', text: 'Salam! 👋 Kifach nqder n3awnek? 💬' }])
  const [chatInput, setChatInput] = useState('')
  const [sendingChat, setSendingChat] = useState(false)

  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)

  const smoothX = useSpring(mouseX, { stiffness: 80, damping: 24 })
  const smoothY = useSpring(mouseY, { stiffness: 80, damping: 24 })

  const rotateX = useTransform(smoothY, [-0.5, 0.5], [8, -8])
  const rotateY = useTransform(smoothX, [-0.5, 0.5], [-10, 10])

  const orbX = useTransform(smoothX, [-0.5, 0.5], [-40, 40])
  const orbY = useTransform(smoothY, [-0.5, 0.5], [-30, 30])

  const simRotateX = useTransform(smoothY, [-0.5, 0.5], [14, -14])
  const simRotateY = useTransform(smoothX, [-0.5, 0.5], [-18, 18])

  const robotRotateX = useTransform(smoothY, [-0.5, 0.5], [7, -7])
  const robotRotateY = useTransform(smoothX, [-0.5, 0.5], [-9, 9])

  useEffect(() => {
    const handleMouseMove = (event) => {
      mouseX.set(event.clientX / window.innerWidth - 0.5)
      mouseY.set(event.clientY / window.innerHeight - 0.5)
    }

    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [mouseX, mouseY])

  useEffect(() => {
    const showTimer = window.setTimeout(() => setWelcomeVisible(true), 650)
    const hideTimer = window.setTimeout(() => setWelcomeVisible(false), 3650)

    return () => {
      window.clearTimeout(showTimer)
      window.clearTimeout(hideTimer)
    }
  }, [])

  useEffect(() => {
    const fetchCatalog = async () => {
      const controller = new AbortController()
      const timeout = window.setTimeout(() => controller.abort(), 6500)

      try {
        const response = await fetch(API_URL, { signal: controller.signal })
        if (!response.ok) throw new Error('Catalog request failed')
        const data = await response.json()
        const normalized = normalizeCatalog(data)
        if (Object.keys(normalized).length) {
          setCatalog(mergeWithProtectedCatalog(normalized))
          setCatalogSource('live')
        }
      } catch (error) {
        console.error('Could not load catalog:', error)
        setCatalog(fallbackCatalog)
        setCatalogSource('fallback')
      } finally {
        window.clearTimeout(timeout)
        setLoading(false)
      }
    }

    fetchCatalog()
    // Removed the 10-second interval to stop the blinking/flashing issue
  }, [])

  const allNumbers = useMemo(() => Object.values(catalog).flat(), [catalog])
  const heroItem = allNumbers.find((item) => item.number === HERO_NUMBER) ?? fallbackCatalog.Diamond[0]
  const spotlightItem = allNumbers[spotlightIndex % Math.max(allNumbers.length, 1)] ?? heroItem

  const orderedCatalog = useMemo(() => {
    return Object.entries(catalog).sort(([a], [b]) => {
      const aIndex = tierOrder.indexOf(a)
      const bIndex = tierOrder.indexOf(b)
      return (aIndex === -1 ? 99 : aIndex) - (bIndex === -1 ? 99 : bIndex)
    })
  }, [catalog])

  const copyNumber = async (number) => {
    await navigator.clipboard.writeText(number)
    setCopiedNumber(number)
    window.setTimeout(() => setCopiedNumber(null), 1300)
  }

  useEffect(() => {
    if (!allNumbers.length) return

    const showNewSale = () => {
      setPopupBuyer(buyers[Math.floor(Math.random() * buyers.length)])
      setPopupSale(allNumbers[Math.floor(Math.random() * allNumbers.length)])
      setPopupVisible(true)
      window.setTimeout(() => setPopupVisible(false), 4200)
    }

    const firstTimer = window.setTimeout(showNewSale, 1600)
    const interval = window.setInterval(showNewSale, 5000)

    return () => {
      window.clearTimeout(firstTimer)
      window.clearInterval(interval)
    }
  }, [allNumbers])

  useEffect(() => {
    const spotlightInterval = window.setInterval(() => {
      setSpotlightIndex((prev) => prev + 1)
    }, 1200)

    return () => window.clearInterval(spotlightInterval)
  }, [])

  const scrollToCollection = () => {
    document.getElementById('collections')?.scrollIntoView({ behavior: 'smooth' })
  }

  const handlePointerMove = (event) => {
    mouseX.set(event.clientX / window.innerWidth - 0.5)
    mouseY.set(event.clientY / window.innerHeight - 0.5)
  }

  const sendChatMessage = async () => {
    if (!chatInput.trim()) return
    
    setSendingChat(true)
    const userMsg = chatInput.trim()
    setChatInput('')
    setChatMessages(prev => [...prev, { role: 'user', text: userMsg }])

    try {
      const response = await fetch('https://vip-boti.onrender.com/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: userMsg, sender: 'web_' + Date.now() })
      })
      
      if (response.ok) {
        const data = await response.json()
        setChatMessages(prev => [...prev, { role: 'bot', text: data.response || 'Thank you! 😊' }])
      } else {
        setChatMessages(prev => [...prev, { role: 'bot', text: 'Sorry, service unavailable 🤖' }])
      }
    } catch (error) {
      setChatMessages(prev => [...prev, { role: 'bot', text: 'Connection error 📡' }])
    } finally {
      setSendingChat(false)
    }
  }

  const tierStyle = (tier) => {
    const lower = tier.toLowerCase()
    if (lower.includes('diamond')) return { icon: Diamond, accent: 'from-amber-100 via-yellow-400 to-white', ring: 'border-amber-200/30', badge: 'bg-amber-200 text-black' }
    if (lower.includes('gold')) return { icon: Crown, accent: 'from-yellow-300 via-amber-500 to-orange-700', ring: 'border-yellow-400/25', badge: 'bg-yellow-500 text-black' }
    if (lower.includes('inwi')) return { icon: Zap, accent: 'from-purple-300 via-fuchsia-500 to-amber-300', ring: 'border-purple-300/25', badge: 'bg-purple-400 text-black' }
    return { icon: Star, accent: 'from-stone-200 via-stone-400 to-amber-300', ring: 'border-stone-300/20', badge: 'bg-stone-200 text-black' }
  }

  const NumberCard = ({ item, tier }) => {
    const style = tierStyle(tier)
    const Icon = style.icon
    const label = getPatternLabel(item.number)
    const rarityScore = getRarityScore(item)

    return (
      <motion.article
        initial={false}
        whileHover={{ y: -8, rotateX: 4, rotateY: -3, scale: 1.015 }}
        transition={{ type: 'spring', stiffness: 180, damping: 18 }}
        className={`winged-card group relative overflow-visible rounded-3xl border ${style.ring} bg-gradient-to-br ${style.accent} p-[1px] shadow-2xl shadow-black/40 [transform-style:preserve-3d]`}
      >
        <span className="card-wing card-wing-left" />
        <span className="card-wing card-wing-right" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_0%,rgba(255,236,170,0.28),transparent_36%),radial-gradient(circle_at_100%_100%,rgba(124,58,237,0.18),transparent_42%)] opacity-70 transition group-hover:opacity-100" />
        <div className="relative overflow-hidden rounded-3xl bg-[#060503]/95 p-4 backdrop-blur-xl sm:p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-amber-200/30 bg-amber-200/10 text-amber-100 shadow-lg shadow-amber-500/10">
                <Icon size={19} />
              </span>
              <div>
                <p className="font-mono text-xl font-black tracking-[0.08em] text-white sm:text-2xl">{item.number}</p>
                <p className="mt-1 text-xs uppercase tracking-[0.28em] text-stone-500">{tier} VIP</p>
              </div>
            </div>
            <span className={`shrink-0 rounded-full px-3 py-1.5 text-sm font-black ${style.badge}`}>{item.price}</span>
          </div>
          <div className="mt-4 flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-2">
            <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.16em] text-fuchsia-100"><Flame size={14} /> {label}</span>
            <button onClick={() => copyNumber(item.number)} className="pointer-events-auto inline-flex items-center gap-1.5 rounded-full border border-amber-200/20 px-3 py-1.5 text-xs font-black uppercase tracking-[0.12em] text-amber-100 transition hover:bg-amber-200 hover:text-black">
              {copiedNumber === item.number ? <Check size={14} /> : <Copy size={14} />}
              {copiedNumber === item.number ? 'Copied' : 'Copy'}
            </button>
          </div>
          <div className="mt-3 rounded-2xl border border-white/10 bg-black/35 p-3">
            <div className="flex items-center justify-between text-[10px] font-black uppercase tracking-[0.22em] text-stone-400">
              <span>Rarity score</span>
              <span className="text-amber-200">{rarityScore}/99</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full bg-gradient-to-r from-fuchsia-400 via-purple-300 to-amber-300" style={{ width: `${rarityScore}%` }} />
            </div>
          </div>
          <a href={getWhatsAppUrl(item.number, item.price, tier)} target="_blank" rel="noreferrer" className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-amber-200/20 bg-gradient-to-r from-amber-200 via-yellow-500 to-amber-700 px-4 py-3 text-sm font-black uppercase tracking-[0.14em] text-black shadow-[0_14px_40px_rgba(245,158,11,0.18)] transition hover:scale-[1.01] hover:from-amber-100 hover:to-yellow-500">
            <MessageCircle size={18} /> Order via WhatsApp
          </a>
        </div>
      </motion.article>
    )
  }



  return (
    <main onPointerMove={handlePointerMove} className="min-h-screen overflow-hidden bg-[#030201] text-stone-100">
      <motion.div

        initial={false}
        animate={welcomeVisible ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: -18, scale: 0.94 }}
        transition={{ type: 'spring', stiffness: 260, damping: 22 }}
        className="pointer-events-none fixed left-1/2 top-5 z-[80] w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 rounded-[2rem] border border-fuchsia-300/25 bg-black/70 p-4 text-white shadow-[0_24px_90px_rgba(168,85,247,0.35)] backdrop-blur-2xl sm:top-7"
      >
        <div className="flex items-center gap-4">
          <div className="welcome-bot relative flex h-16 w-16 shrink-0 items-center justify-center rounded-3xl border border-fuchsia-200/30 bg-gradient-to-br from-purple-950 to-black shadow-[0_0_38px_rgba(168,85,247,0.32)]">
            <div className="absolute top-2 h-1.5 w-7 rounded-full bg-fuchsia-300/60" />
            <div className="grid grid-cols-2 gap-2">
              <span className="h-4 w-4 rounded-full bg-fuchsia-300 shadow-[0_0_18px_rgba(217,70,239,0.9)]" />
              <span className="h-4 w-4 rounded-full bg-fuchsia-300 shadow-[0_0_18px_rgba(217,70,239,0.9)]" />
            </div>
            <div className="absolute bottom-3 h-1 w-8 rounded-full bg-gradient-to-r from-transparent via-amber-200 to-transparent" />
          </div>
          <div>
            <p className="text-xs font-black uppercase tracking-[0.24em] text-fuchsia-200">VIP Bot</p>
            <p className="mt-1 text-lg font-black leading-tight text-white">Hello 👋</p>
            <p className="text-sm font-semibold text-stone-300">VIP nemuro Inwi amazing nemiro ✨</p>
          </div>
        </div>
      </motion.div>

      <div className="pointer-events-none fixed inset-0 opacity-95">
        <motion.div style={{ x: orbX, y: orbY }} className="absolute -top-44 left-1/2 h-[38rem] w-[38rem] -translate-x-1/2 rounded-full bg-amber-500/16 blur-3xl" />
        <motion.div style={{ x: orbY, y: orbX }} className="absolute top-24 right-0 h-[30rem] w-[30rem] rounded-full bg-purple-700/18 blur-3xl" />
        <div className="absolute bottom-0 left-0 h-[34rem] w-[34rem] rounded-full bg-yellow-700/10 blur-3xl" />
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,215,128,0.045)_1px,transparent_1px),linear-gradient(90deg,rgba(255,215,128,0.035)_1px,transparent_1px)] bg-[size:74px_74px] [mask-image:radial-gradient(circle_at_top,black,transparent_72%)]" />
        <div className="luxury-3d-bg absolute inset-0" />
        <div className="zellige-luxury absolute inset-0" />
        <div className="luxe-orbit absolute left-1/2 top-[18%] h-[34rem] w-[34rem] -translate-x-1/2 rounded-full" />
        <div className="aurora-crown absolute inset-x-0 top-0 h-80" />
        <div className="mobile-safe-3d absolute inset-0">
          <span className="phone-shape phone-shape-one" />
          <span className="phone-shape phone-shape-two" />
          <span className="sim-chip-bg" />
        </div>
      </div>

      <motion.header initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-5 py-6 sm:px-8">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-amber-300/40 bg-gradient-to-br from-amber-100 via-yellow-500 to-amber-800 text-black shadow-[0_0_40px_rgba(245,158,11,0.28)]"><Zap size={24} /></div>
          <div><p className="text-lg font-black tracking-[0.18em] text-purple-200">INWI VIP NUMBER</p><p className="text-xs uppercase tracking-[0.35em] text-purple-300/60">سوق الأرقام الفاخرة</p></div>
        </div>
        <button onClick={scrollToCollection} className="hidden rounded-full border border-amber-300/30 bg-black/30 px-5 py-2.5 text-sm font-semibold uppercase tracking-[0.2em] text-amber-100 transition hover:bg-amber-300 hover:text-black sm:block">View Catalog</button>
      </motion.header>
      <section className="relative z-10 mx-auto grid max-w-7xl items-center gap-14 px-5 pb-16 pt-14 sm:px-8 lg:grid-cols-[1.05fr_0.95fr] lg:pb-24 lg:pt-20">
        <motion.div initial={{ opacity: 0, y: 36 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
          <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-amber-300/25 bg-amber-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.28em] text-amber-100"><Sparkles size={15} />{catalogSource === 'live' ? 'Live VIP Catalog • Auto Refresh' : 'VIP Catalog • Safe Mode'}</div>
          <h1 className="max-w-4xl text-5xl font-black leading-[0.95] tracking-[-0.06em] text-white sm:text-7xl lg:text-8xl"><span className="bg-gradient-to-r from-purple-200 via-fuchsia-400 to-amber-300 bg-clip-text text-transparent">INWI VIP NUMBER</span></h1>
          <p className="mt-7 max-w-2xl text-lg leading-8 text-stone-300 sm:text-xl">A premium Moroccan marketplace for Inwi VIP phone numbers. Purple luxury style with auto-refresh and instant WhatsApp ordering.</p>
          <div className="mt-9 flex flex-col gap-4 sm:flex-row"><button onClick={scrollToCollection} className="rounded-full bg-gradient-to-r from-amber-200 via-yellow-500 to-amber-700 px-8 py-4 text-sm font-black uppercase tracking-[0.22em] text-black shadow-[0_20px_80px_rgba(245,158,11,0.25)] transition hover:scale-[1.02]">Browse Numbers</button></div>
        </motion.div>
        <motion.div style={{ rotateX, rotateY, transformPerspective: 900 }} className="relative mx-auto w-full max-w-lg [transform-style:preserve-3d]">
          <div className="absolute -inset-8 rounded-full bg-gradient-to-br from-amber-300/20 via-yellow-500/10 to-purple-500/10 blur-2xl" />
          <div className="relative rounded-[2.4rem] border border-amber-200/20 bg-gradient-to-br from-amber-950/25 via-black to-stone-950/90 p-6 shadow-2xl shadow-black/70">
            <div className="rounded-[1.8rem] border border-amber-100/10 bg-black/60 p-6">
              <div className="flex items-center justify-between"><Gem className="text-amber-200" size={42} /><span className="rounded-full border border-amber-300/30 bg-amber-500/10 px-4 py-2 text-xs uppercase tracking-[0.25em] text-amber-100">Featured</span></div>
              <p className="mt-12 text-sm uppercase tracking-[0.35em] text-stone-500">Top Selection</p>
              <p className="mt-4 font-mono text-4xl font-black tracking-[0.08em] text-white sm:text-5xl">{HERO_NUMBER}</p>
              <div className="mt-8 rounded-2xl bg-gradient-to-r from-amber-200 via-yellow-500 to-amber-700 p-[1px]"><div className="rounded-2xl bg-black px-5 py-4"><p className="text-sm text-stone-400">Reservation price</p><p className="mt-1 text-3xl font-black text-amber-200">{heroItem.price}</p></div></div>
              <a href={getWhatsAppUrl(HERO_NUMBER)} target="_blank" rel="noreferrer" className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-amber-200 via-yellow-500 to-amber-700 px-5 py-4 text-sm font-black uppercase tracking-[0.18em] text-black transition hover:scale-[1.01]"><MessageCircle size={18} /> Order via WhatsApp</a>
            </div>
          </div>
        </motion.div>
      </section>
      <section id="collections" className="relative z-10 mx-auto max-w-7xl px-5 pb-24 sm:px-8">
        <div className="mb-8 rounded-[2.4rem] border border-fuchsia-300/20 bg-gradient-to-br from-fuchsia-950/35 via-black/80 to-amber-950/20 p-4 shadow-[0_30px_120px_rgba(168,85,247,0.18)] sm:p-6">
        </div>

        <div className="mb-8 rounded-[2rem] border border-amber-200/15 bg-black/45 p-4 backdrop-blur-xl sm:p-6">
          <div className="mb-5 flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.3em] text-amber-300">Next level</p>
              <h3 className="mt-1 text-2xl font-black text-white">200 DH premium numbers</h3>
            </div>
            <span className="rounded-full bg-amber-200 px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-black">200 DH</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {(catalog.Diamond ?? fallbackCatalog.Diamond).slice(0, 9).map((item) => <NumberCard key={`diamond-top-${item.number}`} item={item} tier="Diamond" />)}
          </div>
        </div>

        <div className="mb-10 flex flex-col justify-between gap-5 md:flex-row md:items-end">
          <div><p className="text-sm font-bold uppercase tracking-[0.35em] text-amber-300">Dynamic VIP catalog</p><h2 className="mt-3 text-4xl font-black tracking-[-0.04em] text-white sm:text-5xl">اختر رقمك الفاخر</h2></div>
          <p className="max-w-md text-stone-400">Numbers stay visible permanently. {loading ? 'Syncing live catalog...' : catalogSource === 'live' ? 'Live API loaded.' : 'Backup catalog active.'}</p>
        </div>
        <div className="grid gap-8 lg:grid-cols-2">
          {orderedCatalog.map(([tier, numbers]) => {
            const style = tierStyle(tier); const Icon = style.icon;
            return (
              <section key={tier} className={'rounded-[2rem] border ' + style.ring + ' bg-[#080604]/85 p-4 shadow-2xl shadow-black/40 sm:p-6'}>
                <div className="mb-6 flex items-center justify-between gap-4 rounded-3xl bg-gradient-to-br from-amber-100/12 via-yellow-500/8 to-transparent p-5">
                  <div><div className="flex items-center gap-2 text-amber-100"><Icon size={22} /><span className="text-sm font-bold uppercase tracking-[0.3em]">{tier}</span></div><h3 className="mt-2 text-3xl font-black text-white">{numbers.length} VIP numbers</h3></div>
                  <span className={'rounded-full px-4 py-2 text-xs font-black uppercase tracking-[0.2em] ' + style.badge}>{catalogSource === 'live' ? 'Live' : 'Safe'}</span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">{numbers.map((item) => <NumberCard key={tier + '-' + item.number} item={item} tier={tier} />)}</div>
              </section>
            )
          })}
        </div>
      </section>

      <footer className="relative z-10 border-t border-amber-100/10 px-5 py-10 text-center text-sm text-stone-500 sm:px-8">
        <p className="font-semibold tracking-[0.25em] text-purple-200">INWI VIP NUMBER</p>
        <p className="mt-2">Premium purple luxury marketplace.</p>
      </footer>

      {/* Floating WhatsApp Button */}
      <motion.a
        href="https://wa.me/212638388885?text=Salam%20VIP%20Bot%21"
        target="_blank"
        rel="noreferrer"
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        whileHover={{ scale: 1.1 }}
        className="fixed bottom-8 right-8 z-50 flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-r from-green-400 via-emerald-500 to-green-600 text-white shadow-lg shadow-green-500/50 transition hover:shadow-xl hover:shadow-green-500/70"
      >
        <motion.div animate={{ rotate: 360 }} transition={{ duration: 3, repeat: Infinity }} className="absolute inset-0 rounded-full border-2 border-green-300/30" />
        <MessageCircle size={28} />
      </motion.a>

      {/* Chat Widget */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: chatOpen ? 1 : 0, y: chatOpen ? 0 : 20, pointerEvents: chatOpen ? 'auto' : 'none' }}
        transition={{ duration: 0.3 }}
        className="fixed bottom-28 right-8 z-50 w-80 rounded-3xl border border-amber-200/20 bg-gradient-to-br from-slate-900 via-slate-950 to-black shadow-2xl shadow-purple-900/50"
      >
        {/* Chat Header */}
        <div className="flex items-center justify-between rounded-t-3xl bg-gradient-to-r from-purple-900 via-purple-800 to-purple-900 p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-200 text-purple-900">
              <MessageCircle size={18} />
            </div>
            <div>
              <p className="text-sm font-black text-white">VIP Bot 🤖</p>
              <p className="text-xs text-green-200">● Online</p>
            </div>
          </div>
          <button
            onClick={() => setChatOpen(false)}
            className="rounded-full p-1 text-white hover:bg-white/10"
          >
            <ChevronRight size={20} className="rotate-180" />
          </button>
        </div>

        {/* Chat Messages */}
        <div className="h-80 overflow-y-auto space-y-3 p-4 bg-black/40">
          {chatMessages.map((msg, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-xs rounded-2xl px-4 py-2 text-sm ${
                  msg.role === 'user'
                    ? 'bg-gradient-to-r from-amber-500 to-yellow-500 text-black font-semibold'
                    : 'bg-gradient-to-r from-purple-700 to-purple-900 text-white'
                }`}
              >
                {msg.text}
              </div>
            </motion.div>
          ))}
          {sendingChat && (
            <div className="flex justify-start">
              <div className="bg-gradient-to-r from-purple-700 to-purple-900 rounded-2xl px-4 py-2">
                <span className="inline-flex gap-1">
                  <span className="h-2 w-2 rounded-full bg-white animate-bounce" />
                  <span className="h-2 w-2 rounded-full bg-white animate-bounce delay-100" />
                  <span className="h-2 w-2 rounded-full bg-white animate-bounce delay-200" />
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Chat Input */}
        <div className="border-t border-amber-200/10 bg-black/60 p-3 rounded-b-3xl">
          <div className="flex gap-2">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && sendChatMessage()}
              placeholder="صيفط رسالة..."
              className="flex-1 rounded-full bg-slate-700/50 px-4 py-2 text-sm text-white placeholder-stone-400 outline-none border border-amber-200/10 focus:border-amber-200/30 transition"
            />
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={sendChatMessage}
              disabled={sendingChat || !chatInput.trim()}
              className="rounded-full bg-gradient-to-r from-amber-500 to-yellow-600 p-2.5 text-white disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-lg hover:shadow-amber-500/50 transition"
            >
              <ChevronRight size={18} className="-rotate-90" />
            </motion.button>
          </div>
        </div>
      </motion.div>

      {/* Chat Toggle Button */}
      <motion.button
        onClick={() => setChatOpen(!chatOpen)}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.95 }}
        className="fixed bottom-28 right-8 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-r from-purple-600 via-purple-700 to-purple-800 text-white shadow-lg shadow-purple-600/50 transition"
      >
        <motion.div
          animate={{ rotate: chatOpen ? 180 : 0 }}
          transition={{ duration: 0.3 }}
        >
          <MessageCircle size={24} />
        </motion.div>
      </motion.button>
    </main>
  )
}

export default App
