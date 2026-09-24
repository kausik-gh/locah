'use client'

import { useEffect, useRef } from 'react'

/**
 * "From one conversation to a living business" — LOCAH's one marketing moment.
 *
 * An original drawing, not the Sylva/ThreeUI scene: a business at the root,
 * growing branches into the parts LOCAH connects. It is plain SVG and CSS
 * (a few KB, no WebGL), so it costs nothing on the first paint and runs on
 * any phone. The branches draw once; pollen drifts and small signals travel
 * the branches while it is on screen. Pointer depth is for fine pointers
 * only, and prefers-reduced-motion leaves the finished drawing standing still.
 */

type Node = { label: string; x: number; y: number; tone: 'ink' | 'orange' | 'neem' | 'indigo' }

const ROOT = { x: 300, y: 452 }

// Only parts that exist at launch (see lib/product-catalogue.ts).
const NODES: Node[] = [
  { label: 'Website', x: 96, y: 300, tone: 'ink' },
  { label: 'Marketplace', x: 124, y: 168, tone: 'orange' },
  { label: 'Customers', x: 226, y: 82, tone: 'neem' },
  { label: 'Orders', x: 378, y: 82, tone: 'ink' },
  { label: 'Bookings', x: 478, y: 168, tone: 'indigo' },
  { label: 'Payments', x: 504, y: 300, tone: 'neem' },
  { label: 'Enquiries', x: 418, y: 394, tone: 'indigo' },
  { label: 'Team', x: 182, y: 394, tone: 'orange' },
]

// Where each branch leaves the trunk, top of the tree first.
const TRUNK_Y = [360, 318, 296, 296, 318, 350, 414, 420]

function branch(node: Node, index: number) {
  const ty = TRUNK_Y[index]
  const tx = 300 + (node.x < 300 ? -2 : 2)
  const lift = Math.max(40, (ty - node.y) * 0.55)
  const c2x = node.x + (tx - node.x) * 0.42
  const c2y = node.y + (ty > node.y ? 34 : -10)
  return `M${tx} ${ty} C${tx} ${ty - lift} ${c2x} ${c2y} ${node.x} ${node.y}`
}

function pointOn(d: string, t: number) {
  const n = d.match(/-?\d+(\.\d+)?/g)!.map(Number)
  const [x0, y0, x1, y1, x2, y2, x3, y3] = n
  const u = 1 - t
  return {
    x: u * u * u * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t * x3,
    y: u * u * u * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y3,
  }
}

const BRANCHES = NODES.map((node, i) => branch(node, i))

// Leaves sit along the branches, alternating sides.
const LEAVES = BRANCHES.flatMap((d, i) =>
  [0.38, 0.66].map((t, j) => {
    const p = pointOn(d, t)
    const q = pointOn(d, t + 0.02)
    const angle = (Math.atan2(q.y - p.y, q.x - p.x) * 180) / Math.PI + ((i + j) % 2 ? 58 : -58)
    return { x: p.x, y: p.y, angle, key: `${i}-${j}` }
  })
)

// Deterministic scatter, so the server and the browser draw the same thing.
const POLLEN = Array.from({ length: 18 }, (_, i) => {
  const a = (i * 137.508 * Math.PI) / 180
  const r = 60 + ((i * 53) % 190)
  return {
    x: 300 + Math.cos(a) * r * 1.15,
    y: 240 + Math.sin(a) * r * 0.78,
    r: 1.6 + (i % 3) * 0.9,
    d: 7 + (i % 5) * 1.6,
    delay: -(i * 0.7),
  }
})

// Signals travelling the branches: an enquiry arriving, an order, a payment.
const PULSES = [1, 3, 5, 6]

export function LivingSystem() {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const svg = el.querySelector('svg')
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (still) svg?.pauseAnimations()

    // Nothing animates while it is off screen.
    const io = new IntersectionObserver(
      ([entry]) => {
        el.toggleAttribute('data-paused', !entry.isIntersecting)
        if (still) return
        if (entry.isIntersecting) svg?.unpauseAnimations()
        else svg?.pauseAnimations()
      },
      { threshold: 0.05 }
    )
    io.observe(el)

    const fine = window.matchMedia('(hover: hover) and (pointer: fine)').matches
    if (!fine || still) return () => io.disconnect()

    let frame = 0
    const onMove = (e: PointerEvent) => {
      const box = el.getBoundingClientRect()
      const x = (e.clientX - box.left) / box.width - 0.5
      const y = (e.clientY - box.top) / box.height - 0.5
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        el.style.setProperty('--px', x.toFixed(3))
        el.style.setProperty('--py', y.toFixed(3))
      })
    }
    const onLeave = () => {
      el.style.setProperty('--px', '0')
      el.style.setProperty('--py', '0')
    }
    const host = el.closest('section') || el
    host.addEventListener('pointermove', onMove as EventListener)
    host.addEventListener('pointerleave', onLeave)
    return () => {
      io.disconnect()
      cancelAnimationFrame(frame)
      host.removeEventListener('pointermove', onMove as EventListener)
      host.removeEventListener('pointerleave', onLeave)
    }
  }, [])

  return (
    <div className="hx-tree" ref={ref}>
      <svg
        viewBox="0 0 600 540"
        role="img"
        aria-label="A business at the root, growing into its website, Marketplace listing, customers, orders, bookings, payments, enquiries and team, all connected."
      >
        <defs>
          <radialGradient id="hx-glow" cx="50%" cy="46%" r="55%">
            <stop offset="0%" stopColor="#f6e2cf" stopOpacity="0.95" />
            <stop offset="60%" stopColor="#f3ece1" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#faf7f1" stopOpacity="0" />
          </radialGradient>
        </defs>
        <ellipse cx="300" cy="250" rx="300" ry="250" fill="url(#hx-glow)" />

        <g className="hx-tree__pollen" aria-hidden="true">
          {POLLEN.map((p, i) => (
            <circle
              key={i}
              cx={p.x}
              cy={p.y}
              r={p.r}
              style={{ ['--d' as string]: `${p.d}s`, ['--delay' as string]: `${p.delay}s` }}
            />
          ))}
        </g>

        <g className="hx-tree__canopy">
          <path
            className="hx-tree__trunk"
            d={`M${ROOT.x} ${ROOT.y - 20} C 294 404, 308 346, 300 292`}
            pathLength={1}
          />
          {BRANCHES.map((d, i) => (
            <path
              key={NODES[i].label}
              className="hx-tree__branch"
              d={d}
              pathLength={1}
              style={{ ['--i' as string]: i }}
            />
          ))}
          {LEAVES.map((leaf, i) => (
            <path
              key={leaf.key}
              className="hx-tree__leaf"
              d="M0 0 C 6 -7, 16 -7, 22 0 C 16 7, 6 7, 0 0 Z"
              transform={`translate(${leaf.x.toFixed(1)} ${leaf.y.toFixed(1)}) rotate(${leaf.angle.toFixed(0)})`}
              style={{ ['--i' as string]: i }}
            />
          ))}
          {PULSES.map((b, i) => (
            <circle key={b} className="hx-tree__pulse" r="4" opacity="0">
              <animateMotion
                path={BRANCHES[b]}
                dur="3.4s"
                begin={`${(i * 1.3 + 1.8).toFixed(1)}s`}
                repeatCount="indefinite"
                calcMode="spline"
                keyTimes="0;1"
                keySplines="0.77 0 0.18 1"
              />
              <animate
                attributeName="opacity"
                values="0;1;1;0"
                keyTimes="0;0.12;0.8;1"
                dur="3.4s"
                begin={`${(i * 1.3 + 1.8).toFixed(1)}s`}
                repeatCount="indefinite"
              />
            </circle>
          ))}
          {NODES.map((node, i) => {
            const w = node.label.length * 8.6 + 34
            return (
              <g
                key={node.label}
                className={`hx-tree__node hx-tree__node--${node.tone}`}
                transform={`translate(${node.x - w / 2} ${node.y - 17})`}
                style={{ ['--i' as string]: i }}
              >
                <rect width={w} height="34" rx="17" />
                <circle cx="17" cy="17" r="4.5" />
                <text x="28" y="22">
                  {node.label}
                </text>
              </g>
            )
          })}
        </g>

        <g className="hx-tree__root">
          <rect x={ROOT.x - 92} y={ROOT.y - 22} width="184" height="56" rx="28" />
          <circle cx={ROOT.x - 64} cy={ROOT.y + 6} r="14" />
          <path
            d={`M${ROOT.x - 70} ${ROOT.y + 2} h12 M${ROOT.x - 70} ${ROOT.y + 9} h8`}
            stroke="#fff"
            strokeWidth="2"
            strokeLinecap="round"
          />
          <text x={ROOT.x - 42} y={ROOT.y + 1} className="hx-tree__root-title">
            Your business
          </text>
          <text x={ROOT.x - 42} y={ROOT.y + 20} className="hx-tree__root-sub">
            one conversation
          </text>
        </g>
      </svg>
    </div>
  )
}
