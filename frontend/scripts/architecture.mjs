// Render the architecture diagram to frontend/screenshots/architecture.png with Mermaid in headless Chrome.
import { chromium } from 'playwright'

const mermaidSrc = (await import("node:fs")).readFileSync(new URL("../node_modules/mermaid/dist/mermaid.min.js", import.meta.url), "utf8")
const html = `<!doctype html><html><head><meta charset="utf-8">
<script>${mermaidSrc}</script>
<style>body{margin:0;background:#0b0f14;font-family:Inter,system-ui,sans-serif}#d{padding:28px 32px;display:inline-block;width:1900px}</style>
</head><body><div id="d"><pre class="mermaid">
flowchart LR
  classDef aws fill:#1b2432,stroke:#ff8a3d,color:#f1f4f8,stroke-width:1.5px
  classDef data fill:#121820,stroke:#5b6b80,color:#c7d0dc
  classDef ext fill:#0f1a14,stroke:#4caf50,color:#c7d0dc
  N[NASA FIRMS<br/>VIIRS fires, 3 satellites]:::ext
  W[Open-Meteo<br/>100 m wind, mixed-layer depth]:::ext
  C[CPCB stations<br/>via WAQI]:::ext
  EB[Amazon EventBridge<br/>every hour]:::aws --> SF[AWS Step Functions<br/>fetch → simulate → alert]:::aws
  N --> F
  W --> F
  C --> F
  SF --> F[Lambda: fetch]:::aws
  F --> S[Lambda 3 GB: parcel model<br/>180k parcels, 48 h, ~25 s]:::aws
  S --> B[(Amazon S3<br/>61 frames · grids · attribution)]:::data
  B --> CF[Amazon CloudFront<br/>Origin-aware cache]:::aws
  CF --> UI[React + MapLibre<br/>AWS Amplify Hosting]:::aws
  UI --> G[API Gateway → Lambda<br/>FastAPI: forecast, advisory, subscribe]:::aws
  G --> B
  G --> D[(DynamoDB<br/>subscribers)]:::data
  S --> A[Lambda: alerts]:::aws
  A --> BR[Amazon Bedrock<br/>Ministral 3: Hindi · Punjabi · English]:::aws
  A --> SNS[Amazon SNS<br/>email, confirm, unsubscribe]:::aws
  S --> CW[CloudWatch metrics<br/>dashboard · alarms · Budgets]:::aws
</pre></div>
<script>mermaid.initialize({startOnLoad:true,theme:'dark',themeVariables:{fontFamily:'Inter, system-ui, sans-serif',fontSize:'15px',lineColor:'#8e9bab',primaryTextColor:'#f1f4f8'},flowchart:{curve:"basis",nodeSpacing:30,rankSpacing:56,padding:12,useMaxWidth:false}})</script>
</body></html>`

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 2600, height: 1000 }, deviceScaleFactor: 2 })
await page.setContent(html, { waitUntil: "load" })
await page.waitForSelector('svg')
await page.waitForTimeout(800)
const box = await page.locator("#d svg").boundingBox()
await page.screenshot({ path: 'screenshots/architecture.png', clip: { x: 0, y: 0, width: Math.ceil(box.x + box.width + 380), height: Math.ceil(box.y + box.height + 28) } })
console.log('saved screenshots/architecture.png', Math.ceil(box.width), 'x', Math.ceil(box.height))
await browser.close()
