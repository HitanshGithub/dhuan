# Every app tells you the air is bad. I built one that tells you tomorrow.

*How I turned NASA fire detections and a wind forecast into a 48-hour smoke forecast for North India in one weekend, on Step Functions, Lambda, CloudFront and Bedrock, and what fought back.*

Cover image: `frontend/screenshots/07-replay-desktop.png`
Inline images: `frontend/screenshots/architecture.png`, `frontend/screenshots/02-place-desktop.png`, `frontend/screenshots/06-place-mobile.png`

Tags: Lambda, Step Functions, Amazon Bedrock, CloudFront, Amplify, Serverless, Python, Sustainability, Environmental Hacks, Bharat Builds Tour

---

On 9 November 2025, NASA's satellites counted 4,828 fires across Punjab, Haryana and the plains in forty-eight hours. Most were rice fields being cleared after harvest. By six that evening the smoke was over Delhi. By five the next morning it had settled to about 71 micrograms per cubic metre of extra PM2.5 at ground level, on top of everything the city produces itself, and most of it had come from three districts: Mansa, Sangrur and Jind.

Nobody in Delhi could have known that the evening before. Every air-quality app, including the government's, shows the number *right now*. None shows what is coming. So the response is always a day late: sports day happens in the peak, the purifier is bought after the worst night, the inhaler runs out mid-week.

That gap is the whole project. Dhuan (धुआं, "smoke") is a live 48-hour forecast of where North India's farm-fire smoke is going, for any place you tap, with a day's notice by email in Hindi, Punjabi or English. I built it alone in a weekend for Environmental Hacks on the Bharat Builds Tour. It is public at [main.d9com2kyiohi6.amplifyapp.com](https://main.d9com2kyiohi6.amplifyapp.com) and the code is at [github.com/HitanshGithub/dhuan](https://github.com/HitanshGithub/dhuan).

![Dhuan replaying 9 November 2025: the plume over Delhi, and the forecast for one place](frontend/screenshots/07-replay-desktop.png)

## The idea fits in one sentence

Satellites see every fire within hours. The wind forecast says where the air goes. So you can draw tomorrow's smoke today.

Everything else is making that sentence true, cheaply, every hour.

## What you get

Tap a town, a school, your colony. The panel tells you when the smoke arrives, when it peaks and how heavy, when it thins out, and which districts it came from, with their share. Next to that is what the nearest CPCB monitoring station is measuring right now, so the model's number sits beside the real air rather than pretending to be it. Press play and the map runs the next 48 hours: the plume collecting over Haryana at night, settling on Delhi at dawn, lifting by noon. Subscribe and an email arrives a day before the peak, written in the language your family reads.

The header puts the impact in one line: "Heavy smoke over 30 districts around tomorrow 8:30 am, moderate over 77. Worst: Amritsar, Tarn Taran, Jind." Click it and the map jumps to that hour.

Because the season had only just started during the hackathon weekend, the site also ships a replay of 9 November 2025, rebuilt from archived fires and winds with the same model. That is the screenshot above.

## The data, all free

NASA FIRMS publishes VIIRS fire detections (375 m pixels, from Suomi NPP, NOAA-20 and NOAA-21) as a CSV for South Asia with no API key. Open-Meteo gives the hourly wind at 100 m and the boundary-layer height on a one-degree grid, two days back and three ahead, in one request; its ERA5 archive gives the same for any past day. The World Air Quality Index project republishes CPCB and state-board stations. District boundaries are Census 2011 open data, rasterised once onto the grid so the runtime needs no geometry library at all.

## The model, honestly

Dhuan is a Lagrangian parcel model, the same family as HYSPLIT, in a few hundred lines of numpy.

A field seen burning at the 13:30 overpass is assumed to burn from roughly 10:30 to 18:00. Every burning hour releases eight parcels carrying the fire's radiative power. Each parcel drifts with the 100 m wind, bilinear in space and linear in time, spreads with a random walk, carries a persistent speed and heading offset standing in for wind shear, and loses mass slowly. Every hour the parcels are binned onto a 5 km grid and divided by the depth of air they are mixed through.

That last division is the whole reason the worst hours are late night and early morning. The same smoke, trapped under a 300 m night-time layer, is five times dirtier at the ground than mixed through 1,500 m at noon.

Two things I had to get right in the open:

**Tomorrow's fires cannot be seen today.** Fields burning in the last 24 hours are assumed to burn again at the same hours for two more days, with less weight each day. Operational smoke models make the same assumption. The timeline says so whenever a frame depends on it.

**Dusk.** When the boundary layer collapses at sunset, smoke that was mixed through two kilometres of air does not all drop to the ground at once. My first version did exactly that and the index jumped six-fold in one hour. Each parcel now carries its own mixing depth that relaxes towards the new layer over about six hours. The evening ramp became a ramp.

The raw index becomes an estimated extra PM2.5 through one scaling constant, chosen to the right order of magnitude against published estimates of the farm-fire share of Delhi's PM2.5 on peak days. It is labelled an estimate on every screen. The next step is obvious: fit it hourly against the CPCB readings that are already on the map.

## The architecture

![Architecture](frontend/screenshots/architecture.png)

All serverless, all in Mumbai, all in one SAM template.

- **Amazon EventBridge** starts an **AWS Step Functions** workflow every hour: fetch, simulate, alert. One `Retry` on the fetch state is what survives NASA's occasional half-finished downloads.
- **AWS Lambda** does the work. The fetch step reads fires, winds and station readings and saves them with the run, so every forecast is reproducible. A 3 GB function runs the model, about 180,000 parcels over 48 hours in roughly 25 seconds, and writes 61 PNG frames, the forecast grid and the source-attribution grid to **Amazon S3**. The alert step evaluates every subscriber against the new forecast.
- **Amazon CloudFront** serves the frames from the private bucket through an Origin Access Control, with a cache policy keyed on the Origin header. More on why below.
- **Amazon API Gateway** fronts a FastAPI app on Lambda that answers the one question that matters for a pin: arrival, peak, how heavy, from where. Subscriptions live in **Amazon DynamoDB**, one record and one **Amazon SNS** topic per subscriber, so SNS handles confirmation and unsubscribe for free.
- **Amazon Bedrock**, with Ministral 3 14B through the Converse API, rewrites a templated advisory into Hindi or Punjabi. The template is always right about the numbers and always goes out if the model does not.
- **Amazon CloudWatch** gets custom metrics from every run (fires detected, districts under heavy smoke, simulation time, stations observed), a dashboard, and alarms for "a run failed" and "no run in two hours". **AWS Budgets** watches the bill.
- The React + MapLibre site is on **AWS Amplify Hosting**, and GitHub Actions deploys the stack with OIDC, so no AWS keys exist anywhere.

The whole thing costs about two US cents an hour-run and has stayed inside the free tier.

Here is the part of the template that I think earns its keep, the hourly workflow with its retry:

```yaml
ForecastStateMachine:
  Type: AWS::Serverless::StateMachine
  Properties:
    Events:
      Hourly:
        Type: Schedule
        Properties: { Schedule: rate(1 hour) }
    Definition:
      StartAt: FetchFiresAndWinds
      States:
        FetchFiresAndWinds:
          Type: Task
          Resource: arn:aws:states:::lambda:invoke
          Parameters: { FunctionName: "${PipelineArn}", Payload: { step: fetch } }
          Retry: [{ ErrorEquals: [States.ALL], IntervalSeconds: 30, MaxAttempts: 3, BackoffRate: 2 }]
          Next: SimulateSmoke
        SimulateSmoke: { Type: Task, Resource: arn:aws:states:::lambda:invoke, Parameters: { FunctionName: "${PipelineArn}", Payload: { step: simulate, run_id.$: $.run_id } }, Next: AlertSubscribers }
        AlertSubscribers: { Type: Task, Resource: arn:aws:states:::lambda:invoke, Parameters: { FunctionName: "${PipelineArn}", Payload: { step: alerts, run_id.$: $.run_id } }, End: true }
```

## Four things that fought back

**CloudFront and CORS.** The map fetches frames with `fetch()`, which sends an Origin header. My preloader used a plain `<img>`, which does not. CloudFront's CORS response-headers policy only adds headers when the request carries an Origin, and the managed cache policy does not key on it, so the first copy was cached without CORS headers and every later fetch was blocked. A custom cache policy that whitelists the Origin header fixed it. Along the way I learnt that CloudFront refuses `Access-Control-Allow-Origin` as a custom header and that a response-headers policy comment is limited to 128 characters, both as rolled-back stacks.

**SNS and the email that never came.** Publishing to a topic whose email subscription is still pending returns a message id and delivers nothing. No error, no metric. My first live test "worked" and nobody got an email. The app now checks `ListSubscriptionsByTopic` before it publishes and tells the user to confirm first, and if the same person has an older confirmed subscription it uses that.

**The black map.** On the morning of the deadline the map went black for everyone. Three causes stacked: our layers waited for MapLibre's `load` event, which waits for every basemap resource; the basemap style's relief raster had started returning 404 that day; and the site was preloading sixteen megabytes of frames before the tiles. Our layers now install on `style.load`, the style is served from our own site without the broken source, and the frames are palette-compressed from 394 KB to 53 KB and preloaded one at a time after the map starts drawing. From "never" to two seconds.

**A SAM CLI that would not run.** Application control on my laptop blocked the SAM binary and even the Python it was installed with. `aws cloudformation package` and `deploy` do the same job, as long as `CodeUri` sits on each function rather than in `Globals`.

## By the numbers

| | |
|---|---|
| Domain | 70–88 °E, 22–34 °N, 5 km grid, 86,400 cells |
| Forecast | 12 h back, 48 h ahead, refreshed hourly |
| Parcels per live run | ~180,000 (680,000 for the 9 Nov replay) |
| Simulation | ~25 s in a 3 GB Lambda |
| Frames | 61 per run, ~50 KB each |
| Stations overlaid | 155 CPCB and state-board monitors |
| Languages | English, Hindi, Punjabi |
| Cost | about $0.02 per run |

## What I would do next

Assimilate the station readings every hour to calibrate the scale and show the fit on the map, so users can see when the model is wrong. Add plume rise for strong fires. And offer the forecast to school networks as a daily 6 am bulletin, which is the use that made me build it.

## Credits

Fire detections from NASA FIRMS (LANCE), VIIRS 375 m: we acknowledge the use of data from NASA's Fire Information for Resource Management System, part of NASA's Earth Science Data and Information System. Weather from Open-Meteo (CC BY 4.0). Station readings from the World Air Quality Index project and CPCB. District boundaries from Census 2011 via udit-001/india-maps-data. Map tiles from OpenFreeMap and OpenStreetMap contributors. Built with Claude Code as the coding assistant, directed and reviewed by me. MIT licence.

Dhuan gives an indicative estimate, not an official air-quality forecast, and says so on every screen.
