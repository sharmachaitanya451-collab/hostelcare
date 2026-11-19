/**
 * Custom SVG illustration portraying an Indian college hostel courtyard,
 * balconies, verandas, arched colonnades, potted tulsi/plants, and students studying.
 */
export function IndianHostelIllustration({ className = 'w-full h-auto' }) {
  return (
    <svg
      viewBox="0 0 900 620"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Illustration of an Indian college hostel courtyard and verandas with students"
    >
      <defs>
        {/* Soft background sky gradient */}
        <linearGradient
          id="skyGrad"
          x1="450"
          y1="0"
          x2="450"
          y2="400"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#FFF4E6" />
          <stop offset="0.7" stopColor="#FFE8D6" />
          <stop offset="1" stopColor="#FDE1CF" />
        </linearGradient>

        {/* Terracotta building gradient */}
        <linearGradient
          id="brickGrad"
          x1="200"
          y1="120"
          x2="700"
          y2="500"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#E57A5D" />
          <stop offset="0.5" stopColor="#C95337" />
          <stop offset="1" stopColor="#9C3A24" />
        </linearGradient>

        {/* Courtyard floor stone gradient */}
        <linearGradient
          id="floorGrad"
          x1="450"
          y1="460"
          x2="450"
          y2="620"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#F5ECE1" />
          <stop offset="0.5" stopColor="#EDE0D1" />
          <stop offset="1" stopColor="#DECDBB" />
        </linearGradient>

        {/* Jaali pattern */}
        <pattern id="jaali" width="16" height="16" patternUnits="userSpaceOnUse">
          <rect width="16" height="16" fill="#FBF5EE" />
          <circle cx="8" cy="8" r="4" fill="#C95337" fillOpacity="0.25" />
          <circle cx="0" cy="0" r="2.5" fill="#C95337" fillOpacity="0.2" />
          <circle cx="16" cy="0" r="2.5" fill="#C95337" fillOpacity="0.2" />
          <circle cx="0" cy="16" r="2.5" fill="#C95337" fillOpacity="0.2" />
          <circle cx="16" cy="16" r="2.5" fill="#C95337" fillOpacity="0.2" />
        </pattern>
      </defs>

      {/* Sky / Morning campus atmosphere */}
      <rect x="20" y="20" width="860" height="580" rx="24" fill="url(#skyGrad)" />

      {/* Sun disk rising over hostel terrace */}
      <circle cx="210" cy="140" r="72" fill="#F4AA35" fillOpacity="0.35" />
      <circle cx="210" cy="140" r="54" fill="#F4AA35" fillOpacity="0.65" />

      {/* Distant campus trees & foliage */}
      <path
        d="M40 380 Q90 320 150 380 T260 380 L260 480 L40 480 Z"
        fill="#368F83"
        fillOpacity="0.25"
      />
      <path
        d="M640 370 Q710 300 780 370 T860 370 L860 480 L640 480 Z"
        fill="#368F83"
        fillOpacity="0.3"
      />

      {/* Main Hostel Quadrangle Building - Background Block */}
      <rect x="140" y="110" width="620" height="360" rx="8" fill="url(#brickGrad)" />
      <rect x="156" y="126" width="588" height="24" fill="#A83E28" />

      {/* Parapet & Chhatri architectural highlights */}
      <rect x="140" y="98" width="620" height="12" fill="#882C17" />
      {/* Decorative parapet crenellations */}
      <g fill="#A83E28">
        {[...Array(25)].map((_, i) => (
          <rect key={i} x={152 + i * 24} y="90" width="12" height="10" rx="2" />
        ))}
      </g>

      {/* Top floor veranda corridor */}
      <rect x="170" y="150" width="560" height="96" fill="#4A1E14" />
      {/* Top floor arches & jaali balustrade */}
      <g fill="#F7EFE6">
        {[...Array(6)].map((_, i) => (
          <g key={i} transform={`translate(${190 + i * 90}, 150)`}>
            <rect x="0" y="0" width="14" height="96" fill="#F7EFE6" />
            <path d="M14 0 C14 28 66 28 66 0 Z" fill="#4A1E14" />
            <rect x="14" y="60" width="52" height="36" fill="url(#jaali)" />
            <rect x="14" y="58" width="52" height="4" fill="#C95337" />
          </g>
        ))}
      </g>

      {/* Mid floor veranda with room doors and windows */}
      <rect x="170" y="260" width="560" height="106" fill="#3D180F" />
      <g>
        {[...Array(5)].map((_, i) => (
          <g key={i} transform={`translate(${196 + i * 108}, 260)`}>
            {/* Arched veranda pillar */}
            <rect x="0" y="0" width="18" height="106" fill="#FBF5EE" />
            {/* Room Doorway with vintage glass transom */}
            <rect x="26" y="24" width="34" height="82" rx="4" fill="#5A281B" />
            <rect x="30" y="28" width="26" height="20" fill="#FFE2C2" fillOpacity="0.4" />
            <rect x="30" y="52" width="26" height="50" fill="#4A1F15" />
            <circle cx="34" cy="74" r="2" fill="#F4AA35" />
            {/* Window next to door */}
            <rect
              x="68"
              y="32"
              width="24"
              height="40"
              rx="2"
              fill="#FFE8D6"
              fillOpacity="0.6"
              stroke="#5A281B"
              strokeWidth="2"
            />
            <line x1="80" y1="32" x2="80" y2="72" stroke="#5A281B" strokeWidth="1.5" />
            <line x1="68" y1="52" x2="92" y2="52" stroke="#5A281B" strokeWidth="1.5" />
          </g>
        ))}
      </g>
      {/* Mid-floor Balustrade rail */}
      <rect x="170" y="340" width="560" height="26" fill="#C95337" fillOpacity="0.8" />
      <rect x="170" y="338" width="560" height="4" fill="#882C17" />
      <rect x="170" y="364" width="560" height="2" fill="#5A281B" />

      {/* Ground Floor Deep Arched Veranda Colonnade */}
      <rect x="150" y="370" width="600" height="110" fill="#2E130B" />
      <g>
        {[...Array(6)].map((_, i) => (
          <g key={i} transform={`translate(${170 + i * 96}, 370)`}>
            {/* Thick colonial-style brick pillar */}
            <rect x="0" y="0" width="22" height="110" fill="#FBF5EE" />
            <path d="M22 0 Q49 32 76 0 Z" fill="#2E130B" />
            <rect x="22" y="0" width="54" height="14" fill="#FBF5EE" />
          </g>
        ))}
      </g>

      {/* Central hostel signage board */}
      <g transform="translate(370, 118)">
        <rect
          x="0"
          y="0"
          width="160"
          height="28"
          rx="6"
          fill="#292039"
          stroke="#F4AA35"
          strokeWidth="2"
        />
        <text
          x="80"
          y="18"
          fill="#FFFCF7"
          fontSize="11"
          fontWeight="bold"
          fontFamily="sans-serif"
          textAnchor="middle"
          letterSpacing="2"
        >
          HOSTELCARE • BHAVAN
        </text>
      </g>

      {/* Courtyard Floor (Paved quadrangle) */}
      <path d="M40 480 L860 480 L900 620 L0 620 Z" fill="url(#floorGrad)" />

      {/* Paver stone lines */}
      <line
        x1="450"
        y1="480"
        x2="450"
        y2="620"
        stroke="#D3C3B1"
        strokeWidth="2"
        strokeDasharray="6 4"
      />
      <line
        x1="280"
        y1="480"
        x2="160"
        y2="620"
        stroke="#D3C3B1"
        strokeWidth="2"
        strokeDasharray="6 4"
      />
      <line
        x1="620"
        y1="480"
        x2="740"
        y2="620"
        stroke="#D3C3B1"
        strokeWidth="2"
        strokeDasharray="6 4"
      />
      <line
        x1="120"
        y1="480"
        x2="-20"
        y2="620"
        stroke="#D3C3B1"
        strokeWidth="2"
        strokeDasharray="6 4"
      />
      <line
        x1="780"
        y1="480"
        x2="920"
        y2="620"
        stroke="#D3C3B1"
        strokeWidth="2"
        strokeDasharray="6 4"
      />

      {/* Potted plants, terracotta planters & Tulsi Vrindavan in courtyard */}
      <g transform="translate(140, 480)">
        {/* Clay pot */}
        <path d="M0 40 L6 14 L34 14 L40 40 Z" fill="#C95337" />
        <ellipse cx="20" cy="14" rx="14" ry="4" fill="#9C3A24" />
        {/* Palm fronds */}
        <path d="M20 14 Q10 -20 -15 -10 Q5 -4 20 14" fill="#368F83" />
        <path d="M20 14 Q25 -28 35 -34 Q32 -8 20 14" fill="#2A7369" />
        <path d="M20 14 Q40 -16 55 -6 Q35 0 20 14" fill="#368F83" />
      </g>

      <g transform="translate(720, 485)">
        {/* Another lush planter */}
        <path d="M0 35 L5 12 L30 12 L35 35 Z" fill="#C95337" />
        <ellipse cx="17.5" cy="12" rx="12.5" ry="3.5" fill="#9C3A24" />
        <circle cx="18" cy="-2" r="18" fill="#368F83" fillOpacity="0.9" />
        <circle cx="8" cy="4" r="14" fill="#2A7369" />
        <circle cx="28" cy="5" r="13" fill="#4DA79A" />
      </g>

      {/* Courtyard bench with two students discussing notes */}
      <g transform="translate(480, 490)">
        {/* Wooden teak bench */}
        <rect x="0" y="32" width="130" height="8" rx="2" fill="#5A281B" />
        <rect x="0" y="16" width="130" height="6" rx="1" fill="#753726" />
        <rect x="8" y="40" width="8" height="24" fill="#292039" />
        <rect x="114" y="40" width="8" height="24" fill="#292039" />
        {/* Student 1 (sitting on left with laptop) */}
        <ellipse cx="40" cy="8" rx="9" ry="10" fill="#F4AA35" /> {/* Head */}
        <path d="M30 18 Q40 16 50 18 L54 44 L26 44 Z" fill="#D94378" /> {/* Kurta/Shirt */}
        <rect x="36" y="32" width="22" height="4" fill="#E2E8F0" rx="1" /> {/* Open Laptop base */}
        <path d="M38 32 L48 18 L50 19 L42 32 Z" fill="#CBD5E1" /> {/* Screen */}
        <rect x="30" y="44" width="8" height="22" fill="#292039" /> {/* Legs */}
        <rect x="42" y="44" width="8" height="22" fill="#292039" />
        {/* Student 2 (sitting on right with notebook & chai kulhad) */}
        <ellipse cx="90" cy="8" rx="9" ry="10" fill="#DE975A" />
        <path d="M80 18 Q90 16 100 18 L104 44 L76 44 Z" fill="#368F83" />
        <rect x="80" y="44" width="8" height="22" fill="#292039" />
        <rect x="92" y="44" width="8" height="22" fill="#292039" />
        {/* Notebook in lap */}
        <rect
          x="82"
          y="30"
          width="18"
          height="14"
          rx="2"
          fill="#FFF"
          stroke="#292039"
          strokeWidth="1"
        />
        {/* Clay Kulhad (chai cup) */}
        <polygon points="104,38 108,38 107,44 105,44" fill="#C95337" />
      </g>

      {/* Student 3 (walking with backpack in corridor/veranda foreground) */}
      <g transform="translate(290, 480)">
        <ellipse cx="20" cy="12" rx="9" ry="10" fill="#F4AA35" />
        {/* Backpack */}
        <rect x="2" y="24" width="12" height="24" rx="5" fill="#292039" />
        {/* T-shirt */}
        <path d="M12 22 Q20 20 28 22 L32 50 L8 50 Z" fill="#F4AA35" />
        {/* Pants & Shoes */}
        <rect x="10" y="50" width="8" height="32" fill="#368F83" />
        <rect x="22" y="50" width="8" height="32" fill="#368F83" />
        <ellipse cx="14" cy="83" rx="6" ry="3" fill="#292039" />
        <ellipse cx="26" cy="83" rx="6" ry="3" fill="#292039" />
        {/* Clipboard */}
        <rect
          x="26"
          y="34"
          width="12"
          height="16"
          rx="1"
          fill="#FFFCF7"
          stroke="#A83E28"
          strokeWidth="1"
        />
      </g>

      {/* Birds flying over the hostel towers */}
      <path
        d="M280 80 Q288 74 296 80 Q304 74 312 80"
        stroke="#753726"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
      />
      <path
        d="M310 95 Q316 90 322 95 Q328 90 334 95"
        stroke="#753726"
        strokeWidth="1.5"
        fill="none"
        strokeLinecap="round"
      />
      <path
        d="M660 70 Q668 64 676 70 Q684 64 692 70"
        stroke="#753726"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  )
}

/**
 * Hostel Community / Room life illustration
 */
export function StudentCommunityIllustration({ className = 'w-full h-auto' }) {
  return (
    <svg viewBox="0 0 600 420" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <rect width="600" height="420" rx="18" fill="#F7EFE6" />
      {/* Wall calendar & noticeboard */}
      <rect
        x="40"
        y="40"
        width="160"
        height="110"
        rx="6"
        fill="#FFFCF7"
        stroke="#D8CEBE"
        strokeWidth="2"
      />
      <rect x="40" y="40" width="160" height="24" fill="#D94378" />
      <text x="120" y="56" fill="#FFF" fontSize="10" fontWeight="bold" textAnchor="middle">
        HOSTEL FESTIVAL 2026
      </text>
      <circle cx="65" cy="85" r="8" fill="#F4AA35" fillOpacity="0.4" />
      <circle cx="95" cy="85" r="8" fill="#368F83" fillOpacity="0.4" />
      <circle cx="125" cy="85" r="8" fill="#D94378" fillOpacity="0.4" />
      <circle cx="155" cy="85" r="8" fill="#292039" fillOpacity="0.4" />

      {/* Study Desk */}
      <rect x="240" y="140" width="300" height="18" rx="4" fill="#C95337" />
      <rect x="250" y="158" width="14" height="180" fill="#882C17" />
      <rect x="510" y="158" width="14" height="180" fill="#882C17" />
      {/* Books stack on desk */}
      <rect x="270" y="112" width="50" height="8" rx="1" fill="#368F83" />
      <rect x="268" y="120" width="54" height="10" rx="1" fill="#F4AA35" />
      <rect x="266" y="130" width="58" height="10" rx="1" fill="#D94378" />
      {/* Brass desk lamp */}
      <path d="M480 140 L480 80 Q480 60 450 65" stroke="#F4AA35" strokeWidth="4" fill="none" />
      <path d="M435 65 L460 78 L430 85 Z" fill="#F4AA35" />

      {/* Study chair */}
      <rect x="360" y="170" width="70" height="10" rx="2" fill="#292039" />
      <rect x="360" y="100" width="70" height="60" rx="6" fill="#292039" />
      <rect x="370" y="180" width="8" height="140" fill="#554B64" />
      <rect x="412" y="180" width="8" height="140" fill="#554B64" />

      {/* Room Floor with dhurrie / Indian woven rug */}
      <rect
        x="30"
        y="340"
        width="540"
        height="60"
        rx="6"
        fill="#E8D8C3"
        stroke="#CBB499"
        strokeWidth="2"
      />
      <g fill="#D94378">
        {[...Array(12)].map((_, i) => (
          <polygon
            key={i}
            points={`${55 + i * 44},350 ${75 + i * 44},370 ${55 + i * 44},390 ${35 + i * 44},370`}
            fill="#D94378"
            fillOpacity="0.4"
          />
        ))}
      </g>
    </svg>
  )
}
