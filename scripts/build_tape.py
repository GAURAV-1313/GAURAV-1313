#!/usr/bin/env python3
"""Re-records the profile mixtape.

Draws assets/tape-light.svg and assets/tape-dark.svg: a Midnight & Gold cassette whose
reels spin, whose tape winds from the left reel to the right as the year goes by, and
whose receipt prints whatever I pushed last. Also refreshes the live numbers in the
README tracklist. Stdlib only; runs daily from .github/workflows/tape.yml.
"""
import base64
import calendar
import datetime as dt
import json
import os
import pathlib
import re
import urllib.request
from xml.sax.saxutils import escape

USER = "GAURAV-1313"
ROOT = pathlib.Path(__file__).resolve().parent.parent
FONTS = pathlib.Path(__file__).resolve().parent / "fonts"

SIDE_A = ["phodex", "codecall", "recall", "writeupsc", "friction"]
SIDE_B = ["praman setu", "k8s whisperer", "roomy", "csc copilot"]


# ── data ────────────────────────────────────────────────────────────────────

def get(url):
    headers = {"User-Agent": "gauravgives-tape", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
            return json.load(r)
    except Exception as e:  # a missing number should never stop the press
        print(f"skip {url}: {e}")
        return None


def now_playing():
    """Latest public commit outside this repo: (repo, first line of message, date)."""
    for ev in get(f"https://api.github.com/users/{USER}/events/public?per_page=50") or []:
        repo = ev["repo"]["name"]
        if ev["type"] != "PushEvent" or repo == f"{USER}/{USER}":
            continue
        head = ev["payload"].get("head")
        c = get(f"https://api.github.com/repos/{repo}/commits/{head}") if head else None
        if c:
            msg = c["commit"]["message"].splitlines()[0]
            return repo.split("/")[1], msg, ev["created_at"][:10]
    return "gauravgives.lol", "pressing the next track", dt.date.today().isoformat()


def stats():
    year = dt.date.today().year
    s = {}
    for name in ["phodex", "codecall", "roomy", "praman-setu", "csc", "insiders"]:
        r = get(f"https://api.github.com/repos/{USER}/{name}")
        s[name] = r["stargazers_count"] if r else None
    npm = get("https://api.npmjs.org/downloads/point/last-year/codecall")
    s["npm"] = npm["downloads"] if npm else None
    c = get(f"https://api.github.com/search/commits?q=author:{USER}+author-date:>={year}-01-01")
    s["commits"] = c["total_count"] if c else None
    return s


# ── drawing ─────────────────────────────────────────────────────────────────

THEMES = {
    "light": dict(bg="#F4EEE1", shade="#1D1B20", ink="#1D1B20", navy="#151C36", navy2="#1F2850",
                  gold="#D1A544", label="#E6D8B4", blue="#2B3E8C", tape="#4A3428",
                  receipt="#FFFDF7", rtext="#1D1B20", muted="#6B6454", grain=".07"),
    "dark": dict(bg="#191816", shade="#000000", ink="#0B0B0A", navy="#151C36", navy2="#1F2850",
                 gold="#D1A544", label="#CFC2A0", blue="#22337A", tape="#3B2A21",
                 receipt="#23211D", rtext="#DCD4C3", muted="#9C9480", grain=".05"),
}

ROBIN = ('<path d="M43.2 120Q4.8 139.2 19.2 187.2Q38.4 168 43.2 177.6Z" fill="#1d1714"/>'
         '<path d="M196.8 120Q235.2 139.2 220.8 187.2Q201.6 168 196.8 177.6Z" fill="#1d1714"/>'
         '<rect x="28.8" y="43.2" width="182.4" height="172.8" rx="81.6" fill="#2b2320"/>'
         '<rect x="64.8" y="115.2" width="110.4" height="96" rx="52.8" fill="#FF7A2F"/>'
         '<path d="M105.6 48L120 28.8L134.4 48Z" fill="#1d1714"/>'
         '<circle cx="120" cy="28.8" r="6.7" fill="#D1A544"/>'
         '<path d="M103.2 122.4L136.8 122.4L120 133.2Z" fill="#F4A93E"/>'
         '<circle cx="88.8" cy="98.4" r="14.4" fill="#FBF9F7"/><circle cx="90.8" cy="96.4" r="7.7" fill="#241A12"/>'
         '<circle cx="151.2" cy="98.4" r="14.4" fill="#FBF9F7"/><circle cx="153.2" cy="96.4" r="7.7" fill="#241A12"/>'
         '<path d="M34 110Q34 8 120 8Q206 8 206 110" stroke="#151C36" stroke-width="10" fill="none" stroke-linecap="round"/>'
         '<rect x="14" y="90" width="34" height="58" rx="15" fill="#151C36"/>'
         '<rect x="192" y="90" width="34" height="58" rx="15" fill="#151C36"/>'
         '<rect x="22" y="100" width="18" height="38" rx="8" fill="#D1A544"/>'
         '<rect x="200" y="100" width="18" height="38" rx="8" fill="#D1A544"/>')


def font_face(family, file):
    data = base64.b64encode((FONTS / file).read_bytes()).decode()
    return f"@font-face{{font-family:'{family}';src:url(data:font/woff2;base64,{data}) format('woff2')}}"


def reel(cx, cy, r_pack, t):
    teeth = "".join(
        f'<rect x="{cx - 3}" y="{cy - 17}" width="6" height="8" rx="1.5" fill="{t["navy"]}" '
        f'transform="rotate({a} {cx} {cy})"/>' for a in range(0, 360, 60))
    return (f'<circle cx="{cx}" cy="{cy}" r="{r_pack:.1f}" fill="{t["tape"]}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r_pack:.1f}" fill="none" stroke="#000" stroke-opacity=".25" stroke-width="1"/>'
            f'<g class="spin"><circle cx="{cx}" cy="{cy}" r="19" fill="#F4EEE1"/>{teeth}'
            f'<circle cx="{cx}" cy="{cy}" r="5" fill="{t["navy"]}"/></g>')


def short(text, n):
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def svg(theme, playing, s, today):
    t = THEMES[theme]
    year_days = 366 if calendar.isleap(today.year) else 365
    p = today.timetuple().tm_yday / year_days
    r_min, r_max = 22, 50
    r_left = r_min + (r_max - r_min) * (1 - p)
    r_right = r_min + (r_max - r_min) * p

    repo, msg, date = playing
    when = dt.date.fromisoformat(date).strftime("%b %d").upper()
    line1 = escape(short(f"{repo} · “{msg}”", 64))
    bits = [f"{today.year} TAPE {round(p * 100)}% RECORDED"]
    if s.get("commits"):
        bits.append(f"{s['commits']:,} COMMITS")
    if s.get("npm"):
        bits.append(f"CODECALL {s['npm']:,} INSTALLS/YR")
    line2 = escape(" · ".join(bits))

    def notes(items, x, prefix):
        return "".join(
            f'<text x="{x}" y="{136 + i * 22}" class="hand" font-size="17" fill="{t["blue"]}">'
            f'<tspan class="mono" font-size="10" fill="{t["muted"]}">{prefix}{i + 1} </tspan>{escape(n)}</text>'
            for i, n in enumerate(items))

    W, H = 640, 400
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 580" width="880" height="580" role="img" aria-label="Gaurav Singh's mixtape. Now playing: {line1}">
<title>Gaurav Singh · mixtape vol. {today.year}</title>
<style>
{font_face("Caveat", "caveat.woff2")}
{font_face("Bricolage", "bricolage.woff2")}
{font_face("SpaceMono", "spacemono-700.woff2")}
.hand{{font-family:Caveat,'Comic Sans MS',cursive}}
.disp{{font-family:Bricolage,'Arial Black',sans-serif;font-weight:800}}
.mono{{font-family:SpaceMono,ui-monospace,Menlo,monospace;font-weight:700}}
.spin{{transform-box:fill-box;transform-origin:center;animation:spin 1.9s linear infinite}}
.bob{{animation:bob .79s ease-in-out infinite alternate}}
.ghost{{animation:settle 1.4s cubic-bezier(.2,1.4,.4,1) both}}
.rec{{animation:blink 1.58s steps(1) infinite}}
.wipe{{transform-box:fill-box;transform-origin:right;animation:wipe 1.6s .5s steps(64) both}}
.wipe2{{transform-box:fill-box;transform-origin:right;animation:wipe 1.2s 2.1s steps(48) both}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
@keyframes bob{{to{{transform:translateY(-4px)}}}}
@keyframes settle{{from{{transform:translate(-14px,-11px)}}to{{transform:translate(0,0)}}}}
@keyframes blink{{50%{{opacity:.15}}}}
@keyframes wipe{{to{{transform:scaleX(0)}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>
<defs>
<filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="7"/><feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 {t["grain"]} 0"/></filter>
<clipPath id="win"><rect x="150" y="118" width="340" height="116" rx="58"/></clipPath>
</defs>
<rect width="880" height="580" rx="18" fill="{t["bg"]}"/>
<rect width="880" height="580" rx="18" filter="url(#grain)"/>

<g transform="translate(120 56)">
  <rect x="8" y="8" width="{W}" height="{H}" rx="26" fill="{t["shade"]}"/>
  <g class="ghost"><rect x="-5" y="-4" width="{W}" height="{H}" rx="26" fill="none" stroke="{t["gold"]}" stroke-width="2.5"/></g>
  <rect width="{W}" height="{H}" rx="26" fill="{t["navy"]}" stroke="{t["ink"]}" stroke-width="3"/>
  {"".join(f'<g><circle cx="{x}" cy="{y}" r="7" fill="{t["navy2"]}" stroke="{t["ink"]}" stroke-width="1.5"/><path d="M{x-4} {y}h8M{x} {y-4}v8" stroke="{t["gold"]}" stroke-width="1.5" opacity=".7"/></g>' for x, y in [(20, 20), (W - 20, 20), (20, H - 20), (W - 20, H - 20)])}

  <rect x="34" y="30" width="572" height="238" rx="12" fill="{t["label"]}" stroke="{t["ink"]}" stroke-width="2"/>
  <path d="M34 96H606" stroke="{t["gold"]}" stroke-width="2"/>
  <path d="M34 101H606" stroke="{t["blue"]}" stroke-width="1" opacity=".5"/>
  <text x="58" y="80" class="hand" font-size="46" fill="{t["blue"]}">Gaurav Singh <tspan font-size="28" fill="{t["muted"]}">— mixtape '{today.year % 100}</tspan></text>
  <g transform="rotate(-3 506 60)"><rect x="466" y="42" width="80" height="34" rx="5" fill="{t["navy"]}"/><text x="506" y="66" text-anchor="middle" class="disp" font-size="17" fill="{t["gold"]}">SIDE A</text></g>

  {notes(SIDE_A, 46, "A")}
  {notes(SIDE_B, 500, "B")}

  <rect x="150" y="118" width="340" height="116" rx="58" fill="#0E1326" stroke="{t["ink"]}" stroke-width="3"/>
  <g clip-path="url(#win)">
    <path d="M230 {176 + r_left:.1f}L320 228L410 {176 + r_right:.1f}" stroke="{t["tape"]}" stroke-width="3" fill="none"/>
    {reel(230, 176, r_left, t)}
    {reel(410, 176, r_right, t)}
  </g>
  <text x="320" y="258" text-anchor="middle" class="mono" font-size="10" fill="{t["muted"]}" letter-spacing="1.5">TYPE II · CrO2 · 365 DAYS · GAURAVGIVES.LOL</text>

  <path d="M150 300H490L530 {H}H110Z" fill="{t["navy2"]}" stroke="{t["ink"]}" stroke-width="2"/>
  <circle cx="190" cy="352" r="11" fill="#0E1326"/><circle cx="450" cy="352" r="11" fill="#0E1326"/>
  <rect x="294" y="338" width="14" height="18" rx="2" fill="#0E1326"/><rect x="332" y="338" width="14" height="18" rx="2" fill="#0E1326"/>
  <circle class="rec" cx="56" cy="290" r="6" fill="#E0533D"/>
  <text x="70" y="295" class="mono" font-size="13" fill="{t["gold"]}" letter-spacing="2">REC</text>
  <text x="{W - 40}" y="295" text-anchor="end" class="mono" font-size="11" fill="{t["gold"]}" opacity=".8" letter-spacing="1.5">LAST RECORDED {when}</text>

  <g transform="translate({W - 44} 2) rotate(9)" >
    <g class="bob">
      <circle cx="4" cy="4" r="44" fill="{t["shade"]}"/>
      <circle r="44" fill="#FFFDF7" stroke="{t["ink"]}" stroke-width="2.5"/>
      <svg x="-36" y="-38" width="72" height="72" viewBox="0 0 240 240">{ROBIN}</svg>
    </g>
  </g>
</g>

<g transform="translate(120 486)">
  <rect x="5" y="5" width="640" height="70" rx="6" fill="{t["shade"]}"/>
  <rect width="640" height="70" rx="6" fill="{t["receipt"]}" stroke="{t["ink"]}" stroke-width="2"/>
  <path d="M0 6H640" stroke="{t["gold"]}" stroke-width="2" stroke-dasharray="6 5" opacity=".8"/>
  <text x="20" y="34" class="mono" font-size="14" fill="{t["rtext"]}"><tspan fill="{t["gold"]}">▶ NOW PLAYING</tspan>  {line1}</text>
  <rect class="wipe" x="160" y="18" width="470" height="22" fill="{t["receipt"]}"/>
  <text x="20" y="56" class="mono" font-size="11" fill="{t["muted"]}" letter-spacing=".5">{line2}</text>
  <rect class="wipe2" x="16" y="44" width="620" height="18" fill="{t["receipt"]}"/>
</g>
</svg>
'''


# ── README tracklist ────────────────────────────────────────────────────────

def tracklist(s):
    def stars(name):
        return f"★ {s[name]}" if s.get(name) else "source"
    installs = f"{s['npm']:,} installs/yr · " if s.get("npm") else ""
    rows = [
        ("A1", "[**Phodex**](https://github.com/GAURAV-1313/phodex)", "Send coding tasks to Claude Code / Codex from your phone. Nothing merges until you tap approve. Flutter + FastAPI, self-hosted, MIT.", stars("phodex")),
        ("A2", "[**codecall**](https://github.com/GAURAV-1313/codecall)", "Claude Code / Codex plugin that quizzes you on the code your AI just wrote, so you actually own it.", f"{installs}{stars('codecall')}"),
        ("A3", "[**Recall**](https://recall.nofriction.space)", "LeetCode tutor whose hints cite problems *you* already solved.", "[Chrome Web Store](https://chromewebstore.google.com/detail/recall-for-leetcode/ehflchcddgcnmopbehglnnckjonebfmi)"),
        ("A4", "[**writeupsc**](https://www.writeupsc.app)", "Grades handwritten UPSC answers against 4,552 real topper answers. RAG + handwriting OCR.", "1,000+ sign-ups"),
        ("A5", "[**Friction**](https://nofriction.space)", "Chrome extension that logs a moment of confusion without breaking your flow; Gemini finds the pattern later.", "live"),
        ("B1", "[**Praman Setu**](https://github.com/GAURAV-1313/praman-setu)", "Record linkage across Hindi/English spellings for certificate officers.", stars("praman-setu")),
        ("B2", "[**K8sWhisperer**](https://github.com/GAURAV-1313/insiders)", "LangGraph agent that spots a broken pod, diagnoses it and fixes the safe cases itself. Risky ones wait for a Slack approval.", stars("insiders")),
        ("B3", "[**Roomy**](https://roomy.nofriction.space)", "iPhone storage cleaner. SwiftUI, Swift 6, fully on-device.", stars("roomy")),
        ("B4", "[**CSC AI Copilot**](https://csc-ai-copilot.vercel.app)", "Checks e-District forms before they're submitted. OCR + Gemini.", "🏆 1st, E-Summit '26"),
    ]
    out = ["| | track | liner note | plays |", "|:--|:--|:--|:--|"]
    out += [f"| `{n}` | {name} | {desc} | {plays} |" for n, name, desc, plays in rows]
    return "\n".join(out)


def main():
    today = dt.date.today()
    playing = now_playing()
    s = stats()
    (ROOT / "assets").mkdir(exist_ok=True)
    for theme in THEMES:
        (ROOT / "assets" / f"tape-{theme}.svg").write_text(svg(theme, playing, s, today))
    readme = ROOT / "README.md"
    text = readme.read_text()
    text = re.sub(r"(<!-- tracklist:start -->\n).*?(<!-- tracklist:end -->)",
                  lambda m: m.group(1) + tracklist(s) + "\n" + m.group(2), text, flags=re.S)
    readme.write_text(text)
    print("now playing:", playing, s)


if __name__ == "__main__":
    main()
