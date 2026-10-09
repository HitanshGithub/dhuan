"""Plain-language advisories in English, Hindi or Punjabi.

A template written from the forecast is always available and always right about the numbers. When Bedrock is
enabled, Ministral 3 rewrites it in the reader's language with the same facts; if that fails or comes back
empty, the template is sent instead.
"""

from __future__ import annotations

import logging
import re

from .config import settings

log = logging.getLogger(__name__)

ACTIONS = {
    "en": {
        "clear": ["No smoke precautions needed for now."],
        "light": ["People with asthma or heart disease should carry their medicine.", "Keep windows closed during the peak hours."],
        "moderate": ["Shorten outdoor exercise and school sports during the peak hours.", "Keep windows closed and run an air purifier if you have one.",
                     "Wear an N95 mask on long commutes."],
        "heavy": ["Keep children, elders and anyone with asthma or heart disease indoors during the peak hours.",
                  "Seal windows and run air purifiers; a damp cloth under doors helps.", "Wear an N95 mask outdoors. Avoid morning walks."],
        "severe": ["Stay indoors; move school sports and assemblies inside.", "Seal windows, run purifiers, and keep rescue inhalers at hand.",
                   "Wear an N95 mask if you must go out, and seek care for breathlessness or chest pain."],
    },
    "hi": {
        "clear": ["अभी धुएं से बचाव के लिए कोई खास कदम ज़रूरी नहीं।"],
        "light": ["दमा या दिल की बीमारी वाले लोग अपनी दवा साथ रखें।", "सबसे ज़्यादा धुएं वाले घंटों में खिड़कियां बंद रखें।"],
        "moderate": ["सबसे ज़्यादा धुएं वाले घंटों में बाहर की कसरत और स्कूल के खेल कम करें।", "खिड़कियां बंद रखें और एयर प्यूरीफायर हो तो चलाएं।",
                     "लंबे सफ़र में N95 मास्क पहनें।"],
        "heavy": ["बच्चों, बुज़ुर्गों और दमा या दिल के मरीज़ों को उन घंटों में घर के अंदर रखें।",
                  "खिड़कियां सील करें और प्यूरीफायर चलाएं; दरवाज़े के नीचे गीला कपड़ा रखें।", "बाहर N95 मास्क पहनें। सुबह की सैर टालें।"],
        "severe": ["घर के अंदर रहें; स्कूल के खेल और सभाएं अंदर करें।", "खिड़कियां सील करें, प्यूरीफायर चलाएं और इनहेलर पास रखें।",
                   "बाहर जाना ज़रूरी हो तो N95 मास्क पहनें; सांस फूलने या सीने में दर्द पर डॉक्टर को दिखाएं।"],
    },
}
LANGUAGE_NAMES = {"en": "English", "hi": "Hindi (Devanagari script)", "pa": "Punjabi (Gurmukhi script)"}


def template(fc: dict, label: str, language: str = "en") -> tuple[str, str]:
    """(subject, body) in English or Hindi from the forecast numbers alone."""
    place = label or f"{fc['lat']:.2f}, {fc['lon']:.2f}"
    peak, now, arrival = fc["peak"], fc["now"], fc.get("arrival")
    sources = ", ".join(s["district"] for s in fc["sources"][:3]) or "fires across the region"
    lang = language if language in ACTIONS else "en"
    actions = ACTIONS[lang][peak["key"]]
    if lang == "hi":
        subject = f"धुआं: {place} में {peak['ist']} के आसपास {peak['label']} स्तर का धुआं"
        when = f"{arrival['ist']} से पहुंचना शुरू होगा और {peak['ist']} के आसपास सबसे ज़्यादा ({peak['ug']} µg/m³ अनुमानित) रहेगा" if arrival else \
            f"{peak['ist']} के आसपास सबसे ज़्यादा ({peak['ug']} µg/m³ अनुमानित) रहेगा"
        clears = f" {fc['clears']['ist']} तक हल्का हो जाएगा।" if fc.get("clears") else ""
        lines = [f"{place} के लिए खेतों की आग का धुआं: {when}।{clears}", f"धुआं मुख्य रूप से यहां से आ रहा है: {sources}।", "", "क्या करें:"]
    else:
        subject = f"Dhuan: {peak['label'].lower()} smoke at {place} around {peak['ist']}"
        when = f"starts arriving around {arrival['ist']} and peaks around {peak['ist']} (about {peak['ug']} µg/m³ of PM2.5, estimated)" if arrival else \
            f"peaks around {peak['ist']} (about {peak['ug']} µg/m³ of PM2.5, estimated)"
        clears = f" It should thin out by {fc['clears']['ist']}." if fc.get("clears") else ""
        lines = [f"Farm-fire smoke at {place}: {when}.{clears}", f"Most of it comes from fires in {sources}.", "", "What to do:"]
    lines += [f"- {a}" for a in actions]
    lines += ["", f"Right now: {now['label']} ({now['ug']} µg/m³ estimated). Forecast made {fc['generated_at'][:16].replace('T', ' ')} UTC from "
                  f"{fc['fires']['count']} satellite fire detections and the wind forecast.",
              "Dhuan is an indicative estimate, not an official air-quality forecast. https://github.com/HitanshGithub/dhuan"]
    return subject, "\n".join(lines)


def compose(fc: dict, label: str, language: str = "en") -> dict:
    subject, body = template(fc, label, language)
    if settings.llm != "bedrock" or language == "en":
        return {"subject": subject, "body": body, "language": language if language in ACTIONS else "en", "generated_by": "template"}
    try:
        text = _rewrite(body, language)
        if text and len(text) > 80:
            return {"subject": subject, "body": text + "\n\nhttps://github.com/HitanshGithub/dhuan", "language": language, "generated_by": "ai"}
    except Exception:  # never let the model stop an alert from going out
        log.exception("advisory rewrite failed")
    return {"subject": subject, "body": body, "language": "hi" if language == "hi" else "en", "generated_by": "template"}


def _rewrite(body: str, language: str) -> str:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=settings.region)
    prompt = (
        f"Rewrite this smoke advisory in natural, simple {LANGUAGE_NAMES[language]} for a family in North India. Keep every fact, "
        "number, place name and time exactly as given, keep the same actions, and keep it under 130 words. Plain text only: no headings, "
        "no markdown, no greeting, no sign-off. Do not add a link.\n\n" + body
    )
    resp = client.converse(modelId=settings.model_id, messages=[{"role": "user", "content": [{"text": prompt}]}],
                           inferenceConfig={"maxTokens": 600, "temperature": 0.2})
    text = resp["output"]["message"]["content"][0]["text"].strip()
    text = re.sub(r"\*\*|__|^#+\s*", "", text, flags=re.M)
    return text
