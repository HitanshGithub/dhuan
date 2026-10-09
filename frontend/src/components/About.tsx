import { X } from 'lucide-react'
import type { RunMeta } from '../api'
import { formatCount } from '../format'

export default function About({ meta, onClose }: { meta: RunMeta | null; onClose: () => void }) {
  return (
    <div className="absolute inset-0 z-30 flex items-end justify-center bg-ink/70 p-0 backdrop-blur-sm md:items-center md:p-6" onClick={onClose}>
      <div className="glass scroll-thin max-h-[88vh] w-full max-w-2xl overflow-y-auto rounded-t-2xl p-5 shadow-2xl md:rounded-2xl md:p-7" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between">
          <h2 className="font-display text-2xl font-bold">How Dhuan works</h2>
          <button onClick={onClose} aria-label="Close" className="rounded-full p-1 text-mist hover:bg-white/10 hover:text-white">
            <X size={20} />
          </button>
        </div>
        <p className="mt-2 text-sm leading-relaxed text-mist">
          Every October and November, rice stubble is burnt across Punjab, Haryana and western Uttar Pradesh, and the smoke drifts over hundreds of
          kilometres. Air-quality apps tell you how bad it is right now. Dhuan tells you what is coming: when the smoke reaches your place, how heavy
          it will be, and which districts it came from.
        </p>

        <ol className="mt-5 space-y-3 text-sm">
          <Step n={1} title="See the fires">
            NASA's VIIRS instruments on three satellites spot active fires at 375 m. Dhuan reads the last 48 hours over South Asia every hour
            {meta ? `, currently ${formatCount(meta.fires.count)} fires` : ''}.
          </Step>
          <Step n={2} title="Follow the wind">
            Open-Meteo's hourly forecast gives the wind at 100 m and the depth of the mixed layer on a 1° grid, two days back and three ahead.
          </Step>
          <Step n={3} title="Carry the smoke">
            Each fire releases parcels of smoke over the hours it burns. Parcels drift with the wind, spread with turbulence and settle out slowly.
            Smoke trapped under a shallow night-time layer means dirtier air at ground level, which is why the worst hours are late night and early morning.
          </Step>
          <Step n={4} title="Tell people early">
            Pick a place and you get the hour it arrives, the hour it peaks, how heavy, and the districts responsible. Subscribe and an email arrives a
            day ahead, written in English, Hindi or Punjabi.
          </Step>
        </ol>

        <h3 className="mt-6 font-display text-base font-semibold">What it assumes, honestly</h3>
        <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm text-mist">
          <li>Tomorrow's fires are unknown. Fields seen burning in the last 24 hours are assumed to burn again at the same hours for two more days, with less weight each day.</li>
          <li>The smoke level is an estimated extra PM2.5 from open fires, not a measurement and not the total air quality. City traffic, dust and industry come on top.</li>
          <li>This is an indicative transport model built in a weekend, not an official forecast. Check CPCB, SAFAR or your city's bulletin before making medical decisions.</li>
        </ul>

        <h3 className="mt-6 font-display text-base font-semibold">Built on AWS</h3>
        <p className="mt-2 text-sm text-mist">
          EventBridge triggers a Step Functions workflow every hour: Lambda fetches fires and winds, runs the simulation and renders the frames to S3,
          served through CloudFront. The API is Lambda behind API Gateway; subscribers live in DynamoDB and alerts go out through SNS; Ministral 3 on
          Amazon Bedrock writes the advisories in Hindi and Punjabi; the site is on Amplify Hosting.
        </p>

        <h3 className="mt-6 font-display text-base font-semibold">Data and credits</h3>
        <ul className="mt-2 space-y-1 text-xs text-mist/80">
          <li>Fire detections: NASA FIRMS (LANCE), VIIRS 375 m from Suomi NPP, NOAA-20 and NOAA-21. We acknowledge the use of data from NASA's Fire Information for Resource Management System (FIRMS), part of NASA's Earth Science Data and Information System (ESDIS).</li>
          <li>Weather: Open-Meteo.com, CC BY 4.0.</li>
          <li>District boundaries: Census 2011 via udit-001/india-maps-data. Map tiles: OpenFreeMap, © OpenStreetMap contributors. Place search: Open-Meteo geocoding and Nominatim.</li>
          <li>
            Built solo by Hitansh Jain during WeMakeDevs × AWS Environmental Hacks, 8–11 Oct 2026, with Claude Code as the coding assistant. Source and model notes:{' '}
            <a className="text-ember hover:underline" href="https://github.com/HitanshGithub/dhuan" target="_blank" rel="noreferrer">
              github.com/HitanshGithub/dhuan
            </a>
            .
          </li>
        </ul>
      </div>
    </div>
  )
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-ember/20 font-display text-sm font-bold text-ember">{n}</span>
      <div>
        <div className="font-semibold">{title}</div>
        <div className="text-mist">{children}</div>
      </div>
    </li>
  )
}
