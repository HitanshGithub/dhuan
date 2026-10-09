# Submission kit (Environmental Hacks, Air track)

Everything to paste into the form, say in the video, and publish on Builder Center. Links:

* Live app: https://main.d9com2kyiohi6.amplifyapp.com
* Code: https://github.com/HitanshGithub/dhuan
* API: https://96yaz4a479.execute-api.ap-south-1.amazonaws.com/api/health

---

## Form fields

**Project title:** Dhuan — where the smoke goes

**Tagline (one line):** A live 48-hour forecast of North India's farm-fire smoke: when it reaches you, how heavy, and which districts it came from, with a day's notice by email in Hindi, Punjabi or English.

**The problem**

Every October and November, rice stubble is burnt across Punjab, Haryana and western UP, and the smoke drifts for hundreds of kilometres over 300 million people. Every air-quality app tells you how bad the air is *right now*. Nobody tells a school principal in Delhi, a mother in Panipat or an asthma patient in Lucknow what is coming tonight, so the response is always a day late: sports day happens in the peak, the purifier is bought after the worst night, the inhaler runs out mid-week. The only source attribution that exists is one city-level percentage for Delhi in a government bulletin. Nobody can see where *their* smoke came from.

**What I built**

Dhuan pulls NASA's satellite fire detections (VIIRS, three satellites, 375 m) and the hourly wind forecast every hour, then simulates where the smoke from each fire travels over the next 48 hours with a Lagrangian parcel model: parcels released over a field's burning hours, carried by the 100 m wind, spread by turbulence, binned onto a 5 km grid and divided by the depth of the mixed layer (which is why the worst hours are late night and early morning). The map plays the next two days as an animation with the wind streaks that carry it. Tap any place and you get the hour the smoke arrives, the hour it peaks, how heavy it will be, and the top source districts. Subscribe and you get an email a day ahead, written in your language by Ministral 3 on Amazon Bedrock from a template that is always right about the numbers. Tomorrow's fires are unknown, so fields seen burning in the last 24 hours are assumed to burn again, and the app says so on screen. It is an indicative model, and it says that too.

**Where AWS fits**

The whole thing is serverless in ap-south-1. An EventBridge schedule starts a Step Functions workflow every hour: Lambda fetches fires and winds, a 3 GB Lambda runs the simulation in about 20 seconds and renders 61 PNG frames plus the forecast grids to S3, served to the browser through CloudFront with an Origin-aware cache policy. The API is FastAPI on Lambda behind API Gateway. Subscribers live in DynamoDB; each gets their own SNS topic so confirmation and unsubscribe are handled by SNS; the alerts step writes the advisory with Ministral 3 on Bedrock. The site is on Amplify Hosting. GitHub Actions deploys the stack with OIDC, no AWS keys stored anywhere. Idle cost is a few rupees a day.

**AI tools used:** Claude Code (Claude) wrote most of the code under my direction and review; I chose the problem, the model and its assumptions, the data sources and the architecture, and checked the outputs. Ministral 3 14B on Amazon Bedrock runs inside the product for the Hindi and Punjabi advisories.

**Feedback for AWS (if asked)**

1. CloudFront's response-headers CORS policy only adds headers when the request has an Origin header, and the managed CachingOptimized policy does not key on Origin, so a frame cached from a plain `<img>` request is later served to a `fetch()` and blocked. The fix (a cache policy whitelisting Origin) should be a managed policy or a one-line warning in the console.
2. A new account cannot run `sam deploy` from a locked-down Windows laptop (application control blocked the SAM CLI and even the uv-installed Python). `aws cloudformation package/deploy` did the job; it would help if the SAM docs said so up front.
3. Bedrock in Mumbai: Ministral 3 worked the moment the account was verified, with no use-case form. For a hackathon weekend that matters more than model size.

**Team-leader contribution (solo):** everything, with an AI coding assistant: problem choice, model design and its stated assumptions, data sourcing and attribution, architecture, deployment, testing, the writing.

---

## Video script (under 3:00, record the live site)

Set up before recording: live site in one tab (desktop, 1440 wide), AWS console tabs: Step Functions execution graph of the latest run, the S3 bucket's `runs/` folder, the DynamoDB table, Bedrock model access. Phone mirror optional. Subscribe with your own email *before* recording and confirm the SNS email, so the alert can be sent live.

| Time | Screen | Say |
|---|---|---|
| 0:00–0:20 | The live map, fires glowing over Punjab, wind streaks moving, coloured station dots | "This is North India right now. Every orange dot is a field or forest burning, seen by NASA satellites in the last 48 hours; the coloured dots are CPCB monitors measuring the air. Every winter this smoke reaches 300 million people, and every app tells you how bad the air is *right now*. None tells you what's coming. Dhuan does." |
| 0:20–0:40 | Click the "Sun, 9 Nov" replay button. The map fills with 4,800 fires and a brown plume. Press play | "The season has only just begun, so here is the same model on a peak day last November, from archived fires and winds: 4,800 fires in two days. Watch the smoke pour south-east, collect over Haryana at night, and sit over Delhi at dawn when the air is still and the layer is shallow." |
| 0:40–1:10 | Click Delhi. Panel: Arrives today 6 pm, Peaks Tuesday 5 am Heavy 71 µg/m³, chart, sources | "Pick your place. It tells you when the smoke arrives, when it peaks, how heavy, and which districts it came from: Mansa, Sangrur, Jind. Not one number for a whole city: your place, your hours. This is the first time anyone can see where *their* smoke came from." |
| 1:10–1:30 | Click Live. Click Delhi again. Point at "Measured now at Mandir Marg: AQI 152" under the forecast | "Back to today. Next to every forecast is what the nearest CPCB station is measuring right now, so you can see the farm-fire share against the real air. The model is checked against the ground, not trusted blindly." |
| 1:30–1:50 | Toggle Hindi, then Punjabi. The advisory re-renders | "Advice comes in the language the family reads. The numbers come from the model; Ministral 3 on Amazon Bedrock writes the words. If the model fails, the template goes out, so an alert is never lost." |
| 1:50–2:10 | Type your email, Alert me, then "Send me today's advisory now". Switch to your inbox: the email arrives | "Subscribe and you get a day's notice by email, through Amazon SNS, before the peak, not after." |
| 2:10–2:40 | AWS console: Step Functions graph (fetch → simulate → alert, green), S3 run folder with 61 frames, DynamoDB table, Bedrock | "All of it is serverless on AWS in Mumbai: EventBridge wakes a Step Functions workflow every hour, Lambda simulates and renders to S3 behind CloudFront, the API is Lambda and API Gateway, subscribers are in DynamoDB, alerts go through SNS, the words through Bedrock, the site is on Amplify. It costs a few rupees a day." |
| 2:40–2:55 | Back to the map; open "How it works", scroll to "What it assumes, honestly" | "It's an indicative model, built in a weekend, and it says so: tomorrow's fires are assumed to repeat today's, and the level is an estimate, not a measurement. The code, the model notes and every assumption are public." |
| 2:55–3:00 | Replay map playing, URL on screen | "Dhuan. Where the smoke goes." |

Keep each cut short; the judges see 3 minutes and nothing else.

---

## Builder Center blog

**Title:** I built a 48-hour smoke forecast for North India in a weekend, on Lambda, Step Functions and Bedrock

**Description:** Dhuan turns NASA fire detections and the wind forecast into an hourly, animated forecast of where stubble-burning smoke goes, who it reaches, and when, with alerts in Hindi and Punjabi. Here is the model, the AWS architecture, and the three things that fought back.

**Tags:** Lambda, Step Functions, Amazon Bedrock, CloudFront, Amplify, Serverless, Python, Sustainability, Environmental Hacks

**Body**

Every October the same thing happens in North India. The rice harvest ends, hundreds of thousands of fields are burnt in a few weeks, and a wall of smoke moves south-east over Punjab, Haryana, Delhi and western Uttar Pradesh. Every app on my phone shows me the AQI right now, in red. None of them told my family that the smoke from Sangrur would sit over our colony at six the next morning.

So for Environmental Hacks I built Dhuan (धुआं, "smoke"): a live, hourly, 48-hour forecast of where the farm-fire smoke is going, for any place in North India, with a day's notice by email in Hindi, Punjabi or English. It is public at main.d9com2kyiohi6.amplifyapp.com and the code is on GitHub.

### The idea in one sentence

Satellites can see every fire within hours; the wind forecast tells you where the air goes; so you can draw tomorrow's smoke today.

### The data, all free

NASA's FIRMS publishes VIIRS fire detections (375 m pixels, from Suomi NPP, NOAA-20 and NOAA-21) as a CSV for South Asia, refreshed continuously, with no API key. Open-Meteo gives the hourly wind at 100 m and the boundary-layer height on a 1-degree grid, two days back and three ahead, in one request. District boundaries come from Census 2011 open data. That is the whole input list.

### The model

Dhuan is a Lagrangian parcel model, the same family as HYSPLIT, written in a few hundred lines of numpy. A field seen burning at the 13:30 overpass is assumed to burn from about 10:30 to 18:00; every burning hour releases parcels carrying the fire's radiative power. Each parcel drifts with the 100 m wind (bilinear in space, linear in time), spreads with a random walk and a per-parcel speed and heading offset standing in for wind shear, and loses mass slowly. Every hour the parcels are binned onto a 5 km grid and divided by the depth of air they are mixed through. That last step is why the worst hours are late night and early morning: the same smoke trapped under a 300 m night-time layer is five times dirtier at the ground than mixed through 1,500 m at noon.

Two things I had to get honest about. Tomorrow's fires cannot be seen today, so fields burning in the last 24 hours are assumed to burn again at the same hours for two more days, with less weight each day; the app says so on the timeline whenever a frame depends on it. And when the boundary layer collapses at dusk, smoke that was mixed through a deep daytime layer does not all drop to the ground at once; the first version did exactly that and the index jumped six-fold in one hour. Each parcel now carries its own mixing depth that relaxes towards the new layer over about six hours.

The raw index becomes an estimated extra PM2.5 through one scaling constant, chosen by order of magnitude against published estimates of the farm-fire share of Delhi's PM2.5 on peak days. It is an estimate, labelled as one, and the next step is to fit it hourly against CPCB station readings.

### The architecture

All serverless, all in Mumbai. An EventBridge schedule starts a Step Functions workflow every hour with three Lambda tasks: fetch (fires and winds, saved with the run so it is reproducible), simulate (about 20 seconds in a 3 GB function, writing 61 PNG frames, the forecast grid and the source-attribution grid to S3), and alerts. The frames reach the browser through CloudFront. The API is FastAPI on Lambda behind API Gateway, answering the one question that matters for a pin: arrival, peak, how heavy, which districts. Subscribers live in DynamoDB, each with their own SNS topic so SNS handles confirmation and unsubscribe. Ministral 3 on Amazon Bedrock rewrites a templated advisory into Hindi or Punjabi; the template always goes out if the model does not. The site is React and MapLibre on Amplify Hosting, and GitHub Actions deploys the stack with OIDC, so there are no AWS keys anywhere.

### Three things that fought back

**CloudFront and CORS.** The map fetches the frames with `fetch()`, which sends an Origin header, but my preloader used a plain `<img>`, which does not. CloudFront's CORS response-headers policy only adds headers when the request has an Origin, and the managed cache policy does not key on it, so the first copy was cached without CORS headers and the map's fetch was blocked. The fix is a cache policy that whitelists the Origin header. CloudFront also refuses `Access-Control-Allow-Origin` as a custom header, which I learnt from a rolled-back stack.

**MapLibre 6 and Vite.** MapLibre now loads its web worker from a file next to its own module URL, which Vite rewrites; and its CSS forces the map container to `position: relative`, which beats Tailwind's layered utilities. The result was a blank map that took an hour to understand: serve the worker from `/public` with `setWorkerUrl`, and put the map in a plain wrapper div.

**The SAM CLI on a locked-down laptop.** Application control blocked the SAM binary and even the Python it was installed with. `aws cloudformation package` and `deploy` do the same job, as long as `CodeUri` sits on each function rather than in `Globals`.

### What I would do next

Assimilate CPCB station readings every hour to calibrate the scale and show the fit on the map; add plume rise for strong fires; and offer the forecast to school networks as a daily bulletin, which is the use that made me build it.

Dhuan is MIT-licensed. It gives an indicative estimate, not an official forecast, and it says so on every screen.

---

## Checklist before the deadline (Sunday 11 Oct, confirm the time on the schedule page)

- [ ] Video under 3:00, uploaded to YouTube as public or unlisted, link opens in a signed-out browser
- [ ] Repository public with the README's AI-tools declaration and data credits
- [ ] Builder Center blog published, link pasted in the form
- [ ] Form submitted once, before the deadline
- [ ] Try the live site in a private window and on a phone the morning of submission; the hourly run must be fresh
