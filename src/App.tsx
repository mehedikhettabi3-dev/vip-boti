import { useEffect, useMemo, useState, type PointerEvent } from 'react'
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion'
import { Copy, Crown, Diamond, Gem, MessageCircle, Music2, Radio, ShieldCheck, Sparkles, Star, Smartphone, Trophy, Zap, Check } from 'lucide-react'

type VipNumber = {
  number: string
  price: string
  status?: string
  tier: string
}

type Catalog = Record<string, VipNumber[]>

const API_URL = 'https://vip-boti.onrender.com/api/full_catalog'
const HERO_NUMBER = '07 22 33 33 31'
const WHATSAPP_BASE = 'https://wa.me/212778375026?text='
const BRAND_NAME = 'Inwi VIP Number'

const fallbackCatalog: Catalog = {
  Royal: [
    { number: '07 22 33 33 31', price: '300 DH', status: 'available', tier: 'Royal' },
    { number: '07 03 33 34 35', price: '300 DH', status: 'available', tier: 'Royal' },
    { number: '06 99 09 88 08', price: '300 DH', status: 'available', tier: 'Royal' },
    { number: '07 40 01 00 94', price: '300 DH', status: 'available', tier: 'Royal' },
  ],
  Diamond: [
    { number: '07 03 31 33 13', price: '200 DH', status: 'available', tier: 'Diamond' },
    { number: '06 38 38 88 85', price: '200 DH', status: 'available', tier: 'Diamond' },
    { number: '06 05 55 51 18', price: '200 DH', status: 'available', tier: 'Diamond' },
    { number: '07 12 11 12 28', price: '200 DH', status: 'available', tier: 'Diamond' },
    { number: '06 87 77 79 50', price: '200 DH', status: 'available', tier: 'Diamond' },
    { number: '06 29 94 44 41', price: '200 DH', status: 'available', tier: 'Diamond' },
    { number: '06 29 01 11 13', price: '200 DH', status: 'available', tier: 'Diamond' },
    { number: '06 30 33 38 18', price: '200 DH', status: 'available', tier: 'Diamond' },
    { number: '07 07 66 63 69', price: '200 DH', status: 'available', tier: 'Diamond' },
    { number: '06 80 80 30 47', price: '200 DH', status: 'available', tier: 'Diamond' },
    { number: '07 07 23 60 61', price: '200 DH', status: 'available', tier: 'Diamond' },
  ],
  Gold: [
    { number: '06 09 39 01 07', price: '200 DH', status: 'available', tier: 'Gold' },
    { number: '07 06 06 36 79', price: '100 DH', status: 'available', tier: 'Gold' },
    { number: '06 04 03 89 84', price: '100 DH', status: 'available', tier: 'Gold' },
    { number: '07 05 05 76 81', price: '100 DH', status: 'available', tier: 'Gold' },
    { number: '07 03 22 06 00', price: '100 DH', status: 'available', tier: 'Gold' },
    { number: '06 06 09 03 48', price: '200 DH', status: 'available', tier: 'Gold' },
    { number: '06 07 03 13 11', price: '100 DH', status: 'available', tier: 'Gold' },
    { number: '07 24 01 23 01', price: '100 DH', status: 'available', tier: 'Gold' },
    { number: '07 05 11 19 13', price: '100 DH', status: 'available', tier: 'Gold' },
    { number: '07 20 05 07 44', price: '100 DH', status: 'available', tier: 'Gold' },
    { number: '07 05 70 74 08', price: '100 DH', status: 'available', tier: 'Gold' },
    { number: '06 02 44 01 11', price: '100 DH', status: 'available', tier: 'Gold' },
    { number: '06 35 38 28 35', price: '100 DH', status: 'available', tier: 'Gold' },
    { number: '06 99 46 46 49', price: '100 DH', status: 'available', tier: 'Gold' },
    { number: '07 10 14 44 48', price: '100 DH', status: 'available', tier: 'Gold' },
    { number: '07 05 07 06 71', price: '200 DH', status: 'available', tier: 'Gold' },
  ],
  Inwi: [
    { number: '06 99 99 34 38', price: '200 DH', status: 'available', tier: 'Inwi' },
    { number: '07 11 11 67 33', price: '200 DH', status: 'available', tier: 'Inwi' },
    { number: '07 06 03 33 03', price: '150 DH', status: 'available', tier: 'Inwi' },
    { number: '06 06 96 06 07', price: '150 DH', status: 'available', tier: 'Inwi' },
    { number: '07 13 33 37 06', price: '150 DH', status: 'available', tier: 'Inwi' },
    { number: '07 25 37 77 70', price: '150 DH', status: 'available', tier: 'Inwi' },
    { number: '07 04 46 66 61', price: '150 DH', status: 'available', tier: 'Inwi' },
    { number: '06 08 78 88 82', price: '150 DH', status: 'available', tier: 'Inwi' },
    { number: '07 22 20 23 10', price: '150 DH', status: 'available', tier: 'Inwi' },
    { number: '07 25 24 22 29', price: '150 DH', status: 'available', tier: 'Inwi' },
    { number: '06 09 91 96 27', price: '100 DH', status: 'available', tier: 'Inwi' },
    { number: '07 05 77 97 77', price: '100 DH', status: 'available', tier: 'Inwi' },
    { number: '06 99 22 90 94', price: '100 DH', status: 'available', tier: 'Inwi' },
    { number: '07 00 67 08 07', price: '100 DH', status: 'available', tier: 'Inwi' },
    { number: '07 00 50 04 53', price: '150 DH', status: 'available', tier: 'Inwi' },
    { number: '07 25 02 22 28', price: '150 DH', status: 'available', tier: 'Inwi' },
    { number: '07 03 85 04 03', price: '150 DH', status: 'available', tier: 'Inwi' },
    { number: '06 06 78 09 57', price: '150 DH', status: 'available', tier: 'Inwi' },
    { number: '07 04 05 54 59', price: '150 DH', status: 'available', tier: 'Inwi' },
  ],
  Silver: [
    { number: '06 33 37 42 84', price: '100 DH', status: 'available', tier: 'Silver' },
    { number: '07 03 33 81 35', price: '100 DH', status: 'available', tier: 'Silver' },
    { number: '07 20 43 20 59', price: '100 DH', status: 'available', tier: 'Silver' },
    { number: '07 16 34 94 44', price: '100 DH', status: 'available', tier: 'Silver' },
    { number: '07 25 88 33 03', price: '100 DH', status: 'available', tier: 'Silver' },
  ],
}

const buyers = [
  { name: 'Reda', city: 'Fes' },
  { name: 'Yassine', city: 'Casa' },
  { name: 'Mehdi', city: 'Marrakech' },
  { name: 'Othmane', city: 'Tanger' },
  { name: 'Anass', city: 'Rabat' },
  { name: 'Soufiane', city: 'Agadir' },
  { name: 'Amine', city: 'Tetouan' },
  { name: 'Hamza', city: 'Oujda' },
  { name: 'Ilyas', city: 'Meknes' },
  { name: 'Nabil', city: 'Kenitra' },
]

const normalizePhone = (number: string) => number.replace(/\D/g, '')

const removedNumbers = new Set([
  '0706888818',
  '0604050559',
  '0722232325',
  '0717474447',
].map(normalizePhone))

const tierOrder = ['Royal', 'Diamond', 'Gold', 'Inwi', 'Silver']
const getWhatsAppUrl = (number: string, price?: string, tier?: string) => `${WHATSAPP_BASE}${encodeURIComponent(price && tier ? `Salam, bghit nreservi had nmra VIP: ${number} - ${price} - Tier: ${tier}` : number)}`

const getPatternLabel = (number: string) => {
  const clean = normalizePhone(number)
  if (/3333|4444|1111|9999|8888/.test(clean)) return 'Ultra Repeat'
  if (/777|888|999|333|111|444/.test(clean)) return 'Lucky Triple'
  if (/00$/.test(clean)) return 'Clean Ending'
  if (/(\d)\1.*(\d)\2/.test(clean)) return 'Mirror Style'
  return 'Easy Recall'
}

const getRarityScore = (item: VipNumber) => {
  const clean = normalizePhone(item.number)
  let score = item.price === '300 DH' ? 96 : item.price === '200 DH' ? 88 : item.price === '150 DH' ? 78 : 68
  if (/3333|4444|1111|9999|8888/.test(clean)) score += 4
  if (/777|888|999|333|111|444/.test(clean)) score += 3
  if (/00$/.test(clean)) score += 2
  return Math.min(score, 99)
}

const mergeWithProtectedCatalog = (apiCatalog: Catalog): Catalog => {
  const merged: Catalog = {}

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

  return Object.entries(merged).reduce<Catalog>((acc, [tier, numbers]) => {
    const cleanNumbers = numbers.filter((item) => !removedNumbers.has(normalizePhone(item.number)))
    if (cleanNumbers.length) acc[tier] = cleanNumbers
    return acc
  }, {})
}

const normalizeCatalog = (data: unknown): Catalog => {
  if (!data || typeof data !== 'object') return fallbackCatalog

  return Object.entries(data as Record<string, unknown>).reduce<Catalog>((acc, [tier, value]) => {
    if (!Array.isArray(value)) return acc

    const items = value
      .map((item) => item as Partial<VipNumber>)
      .filter((item) => typeof item.number === 'string' && typeof item.price === 'string')
      .map((item) => ({
        number: item.number as string,
        price: item.price as string,
        status: item.status ?? 'available',
        tier: item.tier ?? tier,
      }))

    if (items.length) acc[tier] = items
    return acc
  }, {})
}

function App() {
  const [catalog, setCatalog] = useState<Catalog>(fallbackCatalog)
  const [loading, setLoading] = useState(true)
  const [catalogSource, setCatalogSource] = useState<'fallback' | 'live'>('fallback')
  const [popupSale, setPopupSale] = useState<VipNumber>(fallbackCatalog.Royal[0])
  const [popupBuyer, setPopupBuyer] = useState(buyers[0])
  const [popupVisible, setPopupVisible] = useState(false)
  const [welcomeVisible, setWelcomeVisible] = useState(false)
  const [copiedNumber, setCopiedNumber] = useState<string | null>(null)
  const [spotlightIndex, setSpotlightIndex] = useState(0)

  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)

  const smoothX = useSpring(mouseX, { stiffness: 80, damping: 24 })
  const smoothY = useSpring(mouseY, { stiffness: 80, damping: 24 })

  const rotateX = useTransform(smoothY, [-0.5, 0.5], [8, -8])
  const rotateY = useTransform(smoothX, [-0.5, 0.5], [-10, 10])

  const orbX = useTransform(smoothX, [-0.5, 0.5], [-40, 40])
  const orbY = useTransform(smoothY, [-0.5, 0.5], [-30, 30])

  const pupilX = useTransform(smoothX, [-0.5, 0.5], [-22, 22])
  const pupilY = useTransform(smoothY, [-0.5, 0.5], [-14, 14])

  const simRotateX = useTransform(smoothY, [-0.5, 0.5], [14, -14])
  const simRotateY = useTransform(smoothX, [-0.5, 0.5], [-18, 18])

  const robotRotateX = useTransform(smoothY, [-0.5, 0.5], [7, -7])
  const robotRotateY = useTransform(smoothX, [-0.5, 0.5], [-9, 9])

  useEffect(() => {
    const handleMouseMove = (event: MouseEvent) => {
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
  }, [])

  const allNumbers = useMemo(() => Object.values(catalog).flat(), [catalog])
  const totalNumbers = allNumbers.length
  const heroItem = allNumbers.find((item) => item.number === HERO_NUMBER) ?? fallbackCatalog.Royal[0]
  const royalNumbers = catalog.Royal ?? fallbackCatalog.Royal
  const diamondTopNumbers = catalog.Diamond ?? fallbackCatalog.Diamond
  const spotlightItem = allNumbers[spotlightIndex % Math.max(allNumbers.length, 1)] ?? heroItem

  const orderedCatalog = useMemo(() => {
    return Object.entries(catalog).sort(([a], [b]) => {
      const aIndex = tierOrder.indexOf(a)
      const bIndex = tierOrder.indexOf(b)
      return (aIndex === -1 ? 99 : aIndex) - (bIndex === -1 ? 99 : bIndex)
    })
  }, [catalog])

  const copyNumber = async (number: string) => {
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

  const handlePointerMove = (event: PointerEvent<HTMLElement>) => {
    mouseX.set(event.clientX / window.innerWidth - 0.5)
    mouseY.set(event.clientY / window.innerHeight - 0.5)
  }

  const tierStyle = (tier: string) => {
    const lower = tier.toLowerCase()

    if (lower.includes('royal')) {
      return {
        icon: Trophy,
        accent: 'from-purple-200 via-fuchsia-400 to-amber-300',
        ring: 'border-purple-200/35',
        badge: 'bg-gradient-to-r from-purple-300 to-amber-200 text-black',
      }
    }

    if (lower.includes('diamond')) {
      return {
        icon: Diamond,
        accent: 'from-amber-100 via-yellow-400 to-white',
        ring: 'border-amber-200/30',
        badge: 'bg-amber-200 text-black',
      }
    }

    if (lower.includes('gold')) {
      return {
        icon: Crown,
        accent: 'from-yellow-300 via-amber-500 to-orange-700',
        ring: 'border-yellow-400/25',
        badge: 'bg-yellow-500 text-black',
      }
    }

    if (lower.includes('inwi')) {
      return {
        icon: Zap,
        accent: 'from-purple-300 via-fuchsia-500 to-amber-300',
        ring: 'border-purple-300/25',
        badge: 'bg-purple-400 text-black',
      }
    }

    return {
      icon: Star,
      accent: 'from-stone-200 via-stone-400 to-amber-300',
      ring: 'border-stone-300/20',
      badge: 'bg-stone-200 text-black',
    }
  }

  const NumberCard = ({ item, tier }: { item: VipNumber; tier: string }) => {
    const style = tierStyle(tier)
    const Icon = style.icon
    const isSpotlight = item.number === spotlightItem.number
    const patternLabel = getPatternLabel(item.number)
    const rarityScore = getRarityScore(item)
    const isCopied = copiedNumber === item.number

    return (
      <motion.article
        initial={false}
        whileHover={{ y: -8, rotateX: 4, rotateY: -3, scale: 1.015 }}
        animate={isSpotlight ? { scale: 1.02, rotateX: 2, rotateY: -1 } : {}}
        transition={{ type: 'spring', stiffness: 180, damping: 18 }}
        className={`winged-card group relative overflow-hidden rounded-3xl border ${style.ring} bg-gradient-to-br ${style.accent} p-[1px] shadow-2xl shadow-black/40 [transform-style:preserve-3d] ${isSpotlight ? 'ring-2 ring-amber-400/50 shadow-lg shadow-amber-400/30' : ''}`}
      >
        <span className="card-wing card-wing-left absolute -left-8 top-1/2 -translate-y-1/2 h-16 w-16 rounded-full opacity-0 blur-md transition-all duration-300 group-hover:opacity-60" style={{ background: `radial-gradient(circle, ${isSpotlight ? '#fbbf24' : '#6366f1'}, transparent)` }} />
        <span className="card-wing card-wing-right absolute -right-8 top-1/2 -translate-y-1/2 h-16 w-16 rounded-full opacity-0 blur-md transition-all duration-300 group-hover:opacity-60" style={{ background: `radial-gradient(circle, ${isSpotlight ? '#fbbf24' : '#6366f1'}, transparent)` }} />

        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_0%,rgba(255,236,170,0.28),transparent_36%),radial-gradient(circle_at_100%_100%,rgba(124,58,237,0.18),transparent_42%)] opacity-70 transition group-hover:opacity-100" />

        <div className="relative rounded-3xl bg-[#060503]/95 p-4 sm:p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-amber-200/30 bg-amber-200/10 text-amber-100 shadow-lg shadow-amber-500/10">
                <Icon size={19} />
              </span>

              <div>
                <p className="font-mono text-xl font-black tracking-[0.08em] text-white sm:text-2xl">
                  {item.number}
                </p>
                <p className="mt-1 text-xs uppercase tracking-[0.28em] text-stone-500">
                  {tier} VIP
                </p>
              </div>
            </div>

            <span className={`shrink-0 rounded-full px-3 py-1.5 text-sm font-black ${style.badge}`}>
              {item.price}
            </span>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-lg bg-black/60 px-2 py-1 text-xs font-semibold text-purple-200">
              <Radio size={12} /> {patternLabel}
            </span>
            <span className="inline-flex items-center gap-1 rounded-lg bg-black/60 px-2 py-1 text-xs font-semibold text-amber-300">
              ⚡ {rarityScore}%
            </span>
          </div>

          <div className="mt-4 flex gap-2">
            <a
              href={getWhatsAppUrl(item.number, item.price, tier)}
              target="_blank"
              rel="noreferrer"
              className="flex-1 inline-flex items-center justify-center gap-2 rounded-2xl border border-amber-200/20 bg-gradient-to-r from-amber-200 via-yellow-500 to-amber-700 px-4 py-3 text-sm font-black uppercase tracking-[0.14em] text-black shadow-[0_14px_40px_rgba(245,158,11,0.18)] transition hover:scale-[1.01] hover:from-amber-100 hover:to-yellow-500"
            >
              <MessageCircle size={18} /> Order
            </a>

            <button
              onClick={() => copyNumber(item.number)}
              className={`flex items-center justify-center rounded-2xl px-3 py-3 transition ${isCopied ? 'bg-emerald-500/30 border border-emerald-400' : 'bg-black/40 border border-stone-600 hover:border-amber-400/60'}`}
            >
              {isCopied ? <Check size={18} className="text-emerald-300" /> : <Copy size={18} className="text-stone-400" />}
            </button>
          </div>
        </div>
      </motion.article>
    )
  }

  return (
    <main onPointerMove={handlePointerMove} className="min-h-screen overflow-hidden bg-[#030201] text-stone-100">
      <div className="pointer-events-none fixed inset-0 opacity-95">
        <motion.div
          style={{ x: orbX, y: orbY }}
          className="absolute -top-44 left-1/2 h-[38rem] w-[38rem] -translate-x-1/2 rounded-full bg-amber-500/16 blur-3xl"
        />
        <motion.div
          style={{ x: orbY, y: orbX }}
          className="absolute top-24 right-0 h-[30rem] w-[30rem] rounded-full bg-purple-700/18 blur-3xl"
        />

        <div className="absolute bottom-0 left-0 h-[34rem] w-[34rem] rounded-full bg-yellow-700/10 blur-3xl" />

        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,215,128,0.045)_1px,transparent_1px),linear-gradient(90deg,rgba(255,215,128,0.035)_1px,transparent_1px)] bg-[size:74px_74px] [mask-image:radial-gradient(circle_at_top,black,transparent_72%)]" />

        <div className="luxury-3d-bg absolute inset-0" />

        <div className="mobile-safe-3d absolute inset-0">
          <span className="phone-shape phone-shape-one" />
          <span className="phone-shape phone-shape-two" />
          <span className="sim-chip-bg" />
        </div>
      </div>

      <div className="pointer-events-none fixed inset-0 z-[1] overflow-hidden">
        <motion.div
          style={{
            rotateX: simRotateX,
            rotateY: simRotateY,
            x: orbX,
            y: orbY,
            transformPerspective: 900,
          }}
          className="sim-card-3d absolute right-[4%] top-[18%] hidden h-64 w-44 rounded-[2rem] border border-amber-200/30 bg-gradient-to-br from-amber-100 via-yellow-500 to-amber-900 p-5 shadow-[0_35px_120px_rgba(245,158,11,0.28)] md:block"
        >
          <div className="absolute right-0 top-0 h-16 w-16 rounded-bl-[2rem] bg-[#030201]" />

          <div className="h-20 w-24 rounded-2xl border-2 border-black/50 bg-gradient-to-br from-yellow-200 to-amber-700 p-3 shadow-inner">
            <div className="grid h-full grid-cols-2 gap-2">
              <span className="rounded bg-black/30" />
              <span className="rounded bg-black/20" />
              <span className="rounded bg-black/20" />
              <span className="rounded bg-black/30" />
            </div>
          </div>

          <p className="mt-10 text-xs font-black uppercase tracking-[0.28em] text-black/70">
            VIP SIM
          </p>
          <p className="mt-2 font-mono text-xl font-black tracking-[0.08em] text-black">
            INWI VIP
          </p>

          <div className="absolute bottom-5 left-5 right-5 h-1 rounded-full bg-black/25" />
        </motion.div>

        <motion.div
          style={{
            x: orbY,
            y: orbX,
            rotateX: robotRotateX,
            rotateY: robotRotateY,
            transformPerspective: 900,
          }}
          className="robot-face-3d absolute left-[3%] top-[34%] hidden h-44 w-56 rounded-[2rem] border border-purple-300/30 bg-black/55 p-5 shadow-[0_30px_100px_rgba(0,0,0,0.65)] backdrop-blur-xl lg:block"
        >
          <div className="mb-4 flex items-center justify-between">
            <span className="h-3 w-3 rounded-full bg-purple-300 shadow-[0_0_24px_rgba(216,180,254,0.8)]" />
            <span className="text-[10px] font-black uppercase tracking-[0.35em] text-purple-200">
              VIP Bot
            </span>
          </div>

          <div className="grid grid-cols-2 gap-5">
            {[0, 1].map((eye) => (
              <div
                key={eye}
                className="relative h-16 overflow-hidden rounded-3xl border border-purple-200/25 bg-gradient-to-b from-stone-900 to-black shadow-inner"
              >
                <motion.span
                  style={{ x: pupilX, y: pupilY }}
                  className="robot-pupil absolute left-[calc(50%-14px)] top-[calc(50%-14px)] h-7 w-7 rounded-full bg-gradient-to-br from-purple-100 to-fuchsia-500 shadow-[0_0_28px_rgba(168,85,247,0.95)]"
                />
              </div>
            ))}
          </div>

          <div className="mx-auto mt-5 h-2 w-28 rounded-full bg-gradient-to-r from-transparent via-purple-300/90 to-transparent" />
        </motion.div>
      </div>

      {welcomeVisible && (
        <motion.div
          initial={{ opacity: 0, scale: 0.4, y: 30 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.3, y: 50 }}
          transition={{ duration: 0.5, type: 'spring', stiffness: 200, damping: 25 }}
          className="welcome-bot fixed top-1/2 left-1/2 z-40 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-4 rounded-3xl border border-purple-300/40 bg-gradient-to-b from-purple-900/60 via-black/70 to-stone-950/60 p-8 backdrop-blur-xl sm:p-10"
        >
          <motion.div
            animate={{ rotate: [0, 4, -4, 0] }}
            transition={{ duration: 1.4, repeat: Infinity }}
            className="text-6xl sm:text-7xl"
          >
            🤖
          </motion.div>

          <div className="text-center">
            <p className="text-lg font-black text-transparent bg-gradient-to-r from-purple-200 via-fuchsia-400 to-amber-300 bg-clip-text sm:text-xl">
              مرحبا! Welcome! 👋
            </p>
            <p className="mt-2 text-sm text-stone-300 sm:text-base">
              اختر رقمك الفاخر من أفضل الأرقام الفاخرة
            </p>
          </div>

          <div className="flex gap-3 pt-2">
            <span className="inline-flex h-2 w-2 rounded-full bg-purple-400 animate-pulse" />
            <span className="inline-flex h-2 w-2 rounded-full bg-fuchsia-400 animate-pulse animation-delay-200" />
            <span className="inline-flex h-2 w-2 rounded-full bg-amber-400 animate-pulse animation-delay-400" />
          </div>
        </motion.div>
      )}

      <motion.header
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-5 py-6 sm:px-8"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-amber-300/40 bg-gradient-to-br from-amber-100 via-yellow-500 to-amber-800 text-black shadow-[0_0_40px_rgba(245,158,11,0.28)]">
            <Zap size={24} />
          </div>

          <div>
            <p className="text-lg font-black tracking-[0.18em] text-purple-200">
              INWI VIP NUMBER
            </p>
            <p className="text-xs uppercase tracking-[0.35em] text-purple-300/60">
              سوق الأرقام الفاخرة
            </p>
          </div>
        </div>

        <button
          onClick={scrollToCollection}
          className="hidden rounded-full border border-amber-300/30 bg-black/30 px-5 py-2.5 text-sm font-semibold uppercase tracking-[0.2em] text-amber-100 transition hover:bg-amber-300 hover:text-black sm:block"
        >
          View Catalog
        </button>
      </motion.header>

      <section className="relative z-10 mx-auto grid max-w-7xl items-center gap-14 px-5 pb-16 pt-14 sm:px-8 lg:grid-cols-[1.05fr_0.95fr] lg:pb-24 lg:pt-20">
        <motion.div initial={{ opacity: 0, y: 36 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
          <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-amber-300/25 bg-amber-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.28em] text-amber-100">
            <Sparkles size={15} />
            {catalogSource === 'live' ? 'Live VIP Catalog • API Connected' : 'VIP Catalog • Safe Mode'}
          </div>

          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-purple-300/25 bg-purple-500/10 px-4 py-2 text-xs font-black uppercase tracking-[0.22em] text-purple-100 sm:ml-3">
            <Music2 size={15} /> TikTok mobile ready
          </div>

          <h1 className="max-w-4xl text-5xl font-black leading-[0.95] tracking-[-0.06em] text-white sm:text-7xl lg:text-8xl">
            <span className="bg-gradient-to-r from-purple-200 via-fuchsia-400 to-amber-300 bg-clip-text text-transparent">
              {BRAND_NAME}
            </span>
          </h1>

          <p className="mt-7 max-w-2xl text-lg leading-8 text-stone-300 sm:text-xl">
            A premium Moroccan marketplace for Inwi VIP phone numbers. Purple luxury style, animated 3D background, and instant WhatsApp ordering.
          </p>

          <div className="mt-9 flex flex-col gap-4 sm:flex-row">
            <button
              onClick={scrollToCollection}
              className="rounded-full bg-gradient-to-r from-amber-200 via-yellow-500 to-amber-700 px-8 py-4 text-sm font-black uppercase tracking-[0.22em] text-black shadow-[0_20px_80px_rgba(245,158,11,0.25)] transition hover:scale-[1.02]"
            >
              Browse Numbers
            </button>

            <a
              href={getWhatsAppUrl(HERO_NUMBER)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center justify-center gap-2 rounded-full border border-stone-700 bg-black/30 px-8 py-4 text-sm font-bold uppercase tracking-[0.2em] text-stone-200 transition hover:border-amber-300/60 hover:text-amber-100"
            >
              <MessageCircle size={17} /> Order Hero Number
            </a>

            <button
              onClick={scrollToCollection}
              className="inline-flex items-center justify-center gap-2 rounded-full border border-purple-400/35 bg-purple-500/10 px-8 py-4 text-sm font-bold uppercase tracking-[0.2em] text-purple-100 transition hover:border-purple-200 hover:bg-purple-400/20"
            >
              <Smartphone size={17} /> Phone Catalog
            </button>
          </div>

          <div className="mt-10 grid max-w-xl grid-cols-3 gap-3 border-t border-amber-100/10 pt-8">
            <div>
              <p className="text-3xl font-black text-amber-200">{totalNumbers}</p>
              <p className="mt-1 text-xs uppercase tracking-[0.2em] text-stone-500">
                VIP Lines
              </p>
            </div>

            <div>
              <p className="text-3xl font-black text-amber-200">100</p>
              <p className="mt-1 text-xs uppercase tracking-[0.2em] text-stone-500">
                From DH
              </p>
            </div>

            <div>
              <p className="text-3xl font-black text-amber-200">{orderedCatalog.length}</p>
              <p className="mt-1 text-xs uppercase tracking-[0.2em] text-stone-500">
                Tiers
              </p>
            </div>
          </div>
        </motion.div>

        <motion.div
          style={{ rotateX, rotateY, transformPerspective: 900 }}
          className="relative mx-auto w-full max-w-lg [transform-style:preserve-3d]"
        >
          <div className="absolute -inset-8 rounded-full bg-gradient-to-br from-amber-300/20 via-yellow-500/10 to-purple-500/10 blur-2xl" />

          <div className="relative rounded-[2.4rem] border border-amber-200/20 bg-gradient-to-br from-amber-950/25 via-black to-stone-950/90 p-6 shadow-2xl shadow-black/70">
            <div className="rounded-[1.8rem] border border-amber-100/10 bg-black/60 p-6">
              <div className="flex items-center justify-between">
                <Gem className="text-amber-200" size={42} />
                <span className="rounded-full border border-amber-300/30 bg-amber-500/10 px-4 py-2 text-xs uppercase tracking-[0.25em] text-amber-100">
                  Hero Pick
                </span>
              </div>

              <p className="mt-12 text-sm uppercase tracking-[0.35em] text-stone-500">
                Featured Diamond
              </p>

              <p className="mt-4 font-mono text-4xl font-black tracking-[0.08em] text-white sm:text-5xl">
                {HERO_NUMBER}
              </p>

              <div className="mt-8 rounded-2xl bg-gradient-to-r from-amber-200 via-yellow-500 to-amber-700 p-[1px]">
                <div className="rounded-2xl bg-black px-5 py-4">
                  <p className="text-sm text-stone-400">Diamond reservation price</p>
                  <p className="mt-1 text-3xl font-black text-amber-200">{heroItem.price}</p>
                </div>
              </div>

              <a
                href={getWhatsAppUrl(HERO_NUMBER)}
                target="_blank"
                rel="noreferrer"
                className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-amber-200 via-yellow-500 to-amber-700 px-5 py-4 text-sm font-black uppercase tracking-[0.18em] text-black transition hover:scale-[1.01]"
              >
                <MessageCircle size={18} /> Order via WhatsApp
              </a>
            </div>
          </div>
        </motion.div>
      </section>

      <section id="collections" className="relative z-10 mx-auto max-w-7xl px-5 pb-24 sm:px-8">
        <div className="mb-10 flex flex-col justify-between gap-5 md:flex-row md:items-end">
          <div>
            <p className="text-sm font-bold uppercase tracking-[0.35em] text-amber-300">
              Dynamic VIP catalog
            </p>
            <h2 className="mt-3 text-4xl font-black tracking-[-0.04em] text-white sm:text-5xl">
              اختر رقمك الفاخر
            </h2>
          </div>

          <p className="max-w-md text-stone-400">
            Numbers stay visible permanently.{' '}
            {loading
              ? 'Syncing live catalog in the background...'
              : catalogSource === 'live'
                ? 'Live API catalog loaded successfully.'
                : 'Using protected backup catalog because the API is slow.'}
          </p>
        </div>

        <div className="mb-6 rounded-2xl border border-amber-200/15 bg-black/40 px-5 py-4 text-sm text-amber-100 backdrop-blur-xl">
          {loading
            ? '⏳ Numbers are visible now — syncing live API in background.'
            : catalogSource === 'live'
              ? '✅ Live catalog connected. All numbers are loaded from the API.'
              : '🛡️ Backup catalog active. Numbers will not disappear if the API sleeps.'}
        </div>

        {royalNumbers.length > 0 && (
          <section className="mb-8 rounded-[2rem] border border-purple-200/35 bg-gradient-to-br from-purple-950/40 via-black/60 to-stone-950/40 p-4 shadow-2xl shadow-purple-500/10 sm:p-6">
            <div className="mb-6 flex items-center justify-between gap-4 rounded-3xl bg-gradient-to-br from-purple-200/15 via-fuchsia-500/8 to-transparent p-5">
              <div>
                <div className="flex items-center gap-2 text-amber-100">
                  <Trophy size={24} />
                  <span className="text-sm font-bold uppercase tracking-[0.3em]">Royal</span>
                </div>
                <h3 className="mt-2 text-3xl font-black text-transparent bg-gradient-to-r from-purple-200 via-fuchsia-400 to-amber-300 bg-clip-text">
                  🏆 Wajiha / Top Royal
                </h3>
              </div>
              <span className="rounded-full bg-gradient-to-r from-purple-300 to-amber-200 text-black px-4 py-2 text-xs font-black uppercase tracking-[0.2em]">
                {catalogSource === 'live' ? 'Live' : 'Safe'}
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {royalNumbers.map((item) => (
                <NumberCard key={`Royal-${item.number}`} item={item} tier="Royal" />
              ))}
            </div>
          </section>
        )}

        {diamondTopNumbers.length > 0 && (
          <section className="mb-8 rounded-[2rem] border border-amber-200/30 bg-gradient-to-br from-amber-950/30 via-black/60 to-stone-950/30 p-4 shadow-2xl shadow-amber-500/5 sm:p-6">
            <div className="mb-6 flex items-center justify-between gap-4 rounded-3xl bg-gradient-to-br from-amber-100/12 via-yellow-500/8 to-transparent p-5">
              <div>
                <div className="flex items-center gap-2 text-amber-100">
                  <Diamond size={24} />
                  <span className="text-sm font-bold uppercase tracking-[0.3em]">Diamond</span>
                </div>
                <h3 className="mt-2 text-3xl font-black text-amber-200">
                  ✨ Next Level
                </h3>
              </div>
              <span className="rounded-full bg-amber-200 text-black px-4 py-2 text-xs font-black uppercase tracking-[0.2em]">
                200 DH
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {diamondTopNumbers.slice(0, 9).map((item) => (
                <NumberCard key={`Diamond-${item.number}`} item={item} tier="Diamond" />
              ))}
            </div>
          </section>
        )}

        <div className="grid gap-8 lg:grid-cols-2">
          {orderedCatalog.map(([tier, numbers]) => {
            const style = tierStyle(tier)
            const Icon = style.icon

            return (
              <section
                key={tier}
                className={`rounded-[2rem] border ${style.ring} bg-[#080604]/85 p-4 shadow-2xl shadow-black/40 sm:p-6`}
              >
                <div className="mb-6 flex items-center justify-between gap-4 rounded-3xl bg-gradient-to-br from-amber-100/12 via-yellow-500/8 to-transparent p-5">
                  <div>
                    <div className="flex items-center gap-2 text-amber-100">
                      <Icon size={22} />
                      <span className="text-sm font-bold uppercase tracking-[0.3em]">
                        {tier}
                      </span>
                    </div>

                    <h3 className="mt-2 text-3xl font-black text-white">
                      {numbers.length} VIP numbers
                    </h3>
                  </div>

                  <span className={`rounded-full px-4 py-2 text-xs font-black uppercase tracking-[0.2em] ${style.badge}`}>
                    {catalogSource === 'live' ? 'Live' : 'Safe'}
                  </span>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  {numbers.map((item) => (
                    <NumberCard key={`${tier}-${item.number}`} item={item} tier={tier} />
                  ))}
                </div>
              </section>
            )
          })}
        </div>

        <div className="mt-10 rounded-[2rem] border border-amber-300/15 bg-gradient-to-r from-amber-950/25 via-black/70 to-stone-950/70 p-6 text-center sm:p-8">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-amber-200/25 bg-amber-200/10 text-amber-100">
            <ShieldCheck size={28} />
          </div>

          <h3 className="mt-4 text-2xl font-black text-white">
            Premium reservation, Moroccan marketplace style
          </h3>

          <p className="mx-auto mt-2 max-w-2xl text-stone-400">
            Tap "Order via WhatsApp" and the chosen number will be inserted automatically in the message.
          </p>
        </div>
      </section>

      <motion.div
        initial={false}
        animate={
          popupVisible
            ? { opacity: 1, y: 0, rotateX: 0, scale: 1 }
            : { opacity: 0, y: 45, rotateX: -24, scale: 0.92 }
        }
        transition={{ type: 'spring', stiffness: 240, damping: 22 }}
        className="fixed bottom-5 left-5 z-50 max-w-[calc(100vw-2.5rem)] rounded-3xl border border-amber-200/25 bg-white/10 p-4 text-white shadow-[0_20px_80px_rgba(0,0,0,0.45)] backdrop-blur-xl sm:p-5 [transform-style:preserve-3d]"
      >
        <div className="flex items-center gap-4">
          <div className="animate-float-3d text-4xl">✨</div>

          <div>
            <p className="text-sm text-stone-200">
              <strong className="text-amber-100">
                {popupBuyer.name} mn {popupBuyer.city}
              </strong>{' '}
              chra n-nmra VIP
            </p>

            <p className="my-1 font-mono text-lg font-black tracking-[0.16em] text-amber-300">
              {popupSale.number}
            </p>

            <p className="font-black text-emerald-300">{popupSale.price}</p>
            <small className="text-stone-400">Hadi 2 d-qayq...</small>
          </div>
        </div>
      </motion.div>

      <footer className="relative z-10 border-t border-amber-100/10 px-5 py-10 text-center text-sm text-stone-500 sm:px-8">
        <p className="font-semibold tracking-[0.25em] text-purple-200">
          INWI VIP NUMBER
        </p>
        <p className="mt-2">
          Dynamic purple luxury VIP phone number marketplace.
        </p>
      </footer>
    </main>
  )
}

export default App
