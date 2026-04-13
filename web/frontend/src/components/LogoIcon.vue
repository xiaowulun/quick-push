<template>
  <svg viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" style="stop-color:#4A90D9"/>
        <stop offset="50%" style="stop-color:#7B68EE"/>
        <stop offset="100%" style="stop-color:#B46BFF"/>
      </linearGradient>
      <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
        <feMerge>
          <feMergeNode in="coloredBlur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
      <filter id="strongGlow" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="6" result="coloredBlur"/>
        <feMerge>
          <feMergeNode in="coloredBlur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
    </defs>
    
    <circle cx="100" cy="100" r="85" fill="none" stroke="url(#logoGradient)" stroke-width="0.5" opacity="0.3" filter="url(#glow)"/>
    <circle cx="100" cy="100" r="90" fill="none" stroke="url(#logoGradient)" stroke-width="0.3" opacity="0.2" filter="url(#glow)"/>
    
    <g stroke="url(#logoGradient)" stroke-width="1.2" opacity="0.5">
      <line x1="100" y1="35" x2="65" y2="65"/>
      <line x1="100" y1="35" x2="100" y2="65"/>
      <line x1="100" y1="35" x2="135" y2="65"/>
      <line x1="65" y1="65" x2="35" y2="100"/>
      <line x1="65" y1="65" x2="65" y2="100"/>
      <line x1="100" y1="65" x2="65" y2="100"/>
      <line x1="100" y1="65" x2="100" y2="100"/>
      <line x1="100" y1="65" x2="135" y2="100"/>
      <line x1="135" y1="65" x2="100" y2="100"/>
      <line x1="135" y1="65" x2="135" y2="100"/>
      <line x1="135" y1="65" x2="165" y2="100"/>
      <line x1="35" y1="100" x2="65" y2="135"/>
      <line x1="65" y1="100" x2="65" y2="135"/>
      <line x1="65" y1="100" x2="100" y2="135"/>
      <line x1="100" y1="100" x2="65" y2="135"/>
      <line x1="100" y1="100" x2="100" y2="135"/>
      <line x1="100" y1="100" x2="135" y2="135"/>
      <line x1="135" y1="100" x2="100" y2="135"/>
      <line x1="135" y1="100" x2="135" y2="135"/>
      <line x1="135" y1="100" x2="165" y2="135"/>
      <line x1="165" y1="100" x2="135" y2="135"/>
      <line x1="65" y1="135" x2="100" y2="165"/>
      <line x1="100" y1="135" x2="100" y2="165"/>
      <line x1="135" y1="135" x2="100" y2="165"/>
      <line x1="100" y1="35" x2="100" y2="20"/>
      <line x1="35" y1="100" x2="20" y2="100"/>
      <line x1="165" y1="100" x2="180" y2="100"/>
      <line x1="100" y1="165" x2="100" y2="180"/>
    </g>
    
    <path d="M100 30 C85 30, 70 38, 65 52 C55 48, 45 52, 40 62 C35 58, 30 58, 28 65 C25 72, 28 80, 32 85 C28 95, 28 105, 32 115 C28 120, 25 128, 28 135 C30 142, 35 142, 40 138 C45 148, 55 152, 65 148 C70 158, 85 165, 100 165 C115 165, 130 158, 135 148 C145 152, 155 148, 160 138 C165 142, 170 142, 172 135 C175 128, 172 120, 168 115 C172 105, 172 95, 168 85 C172 80, 175 72, 172 65 C170 58, 165 58, 160 62 C155 52, 145 48, 135 52 C130 38, 115 30, 100 30Z" stroke="url(#logoGradient)" stroke-width="2.5" fill="none" filter="url(#strongGlow)"/>
    
    <path d="M65 52 L52 28 L78 42" stroke="url(#logoGradient)" stroke-width="2" fill="none" filter="url(#glow)"/>
    <path d="M135 52 L148 28 L122 42" stroke="url(#logoGradient)" stroke-width="2" fill="none" filter="url(#glow)"/>
    
    <path d="M160 138 C175 145, 178 130, 172 120 C168 112, 175 105, 180 100" stroke="url(#logoGradient)" stroke-width="2.5" fill="none" stroke-linecap="round" filter="url(#glow)"/>
    
    <g fill="url(#logoGradient)">
      <circle cx="100" cy="65" r="5" filter="url(#strongGlow)"/>
      <circle cx="65" cy="100" r="5" filter="url(#strongGlow)"/>
      <circle cx="100" cy="100" r="6" filter="url(#strongGlow)"/>
      <circle cx="135" cy="100" r="5" filter="url(#strongGlow)"/>
      <circle cx="100" cy="135" r="5" filter="url(#strongGlow)"/>
      <circle cx="100" cy="35" r="4" filter="url(#glow)"/>
      <circle cx="65" cy="65" r="3.5" filter="url(#glow)"/>
      <circle cx="135" cy="65" r="3.5" filter="url(#glow)"/>
      <circle cx="35" cy="100" r="4" filter="url(#glow)"/>
      <circle cx="165" cy="100" r="4" filter="url(#glow)"/>
      <circle cx="65" cy="135" r="3.5" filter="url(#glow)"/>
      <circle cx="135" cy="135" r="3.5" filter="url(#glow)"/>
      <circle cx="100" cy="165" r="4" filter="url(#glow)"/>
      <circle cx="100" cy="20" r="2.5" filter="url(#glow)"/>
      <circle cx="20" cy="100" r="2.5" filter="url(#glow)"/>
      <circle cx="180" cy="100" r="2.5" filter="url(#glow)"/>
      <circle cx="100" cy="180" r="2.5" filter="url(#glow)"/>
    </g>
    
    <g fill="url(#logoGradient)" opacity="0.8" font-family="monospace" font-size="7">
      <text x="82" y="48">{ }</text>
      <text x="108" y="48">[ ]</text>
      <text x="48" y="82">&lt;/&gt;</text>
      <text x="142" y="82">( )</text>
      <text x="82" y="118">...</text>
      <text x="108" y="118">;;</text>
      <text x="92" y="152">fn</text>
    </g>
  </svg>
</template>
