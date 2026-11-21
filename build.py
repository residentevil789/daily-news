import datetime, os, html, re, json
import requests
import feedparser
import trafilatura
from ebooklib import epub
from googlenewsdecoder import gnewsdecoder as new_decoderv1

GITHUB_USER = "residentevil789"
REPO_NAME = "daily-news"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9"
}

S = chr(47)
W = "www" + "."

def gnews(query):
    host = "news." + "google." + "com"
    return f"https:{S}{S}{host}{S}rss{S}search?q={query}&hl=en-PH&gl=PH&ceid=PH:en"

def direct(host, path):
    return f"https:{S}{S}{host}{S}{path}"

def resolve_url(link):
    if "google.com" in link:
        try:
            decoded = new_decoderv1(link, interval=1)
            if decoded.get("status") and decoded.get("decoded_url"):
                return decoded["decoded_url"]
        except Exception:
            pass
    return link

def make_brief(text, title="", max_sentences=5, max_chars=850):
    clean = " ".join(text.split())
    if title and clean.lower().startswith(title.lower()):
        clean = clean[len(title):].lstrip(" -:|—–")
    sentences = re.split(r'(?<=[.!?])\s+', clean)
    brief = " ".join(sentences[:max_sentences])
    if len(brief) > max_chars:
        brief = brief[:max_chars].rsplit(" ", 1)[0] + "..."
    return brief

def extract_recipe_html(page_html):
    scripts = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', page_html, re.S | re.I)
    for raw in scripts:
        try:
            data = json.loads(raw.strip())
            items = data if isinstance(data, list) else data.get("@graph", [data])
            for item in items:
                if isinstance(item, dict) and item.get("@type") == "Recipe":
                    ings = item.get("recipeIngredient", [])
                    steps = item.get("recipeInstructions", [])
                    out = ""
                    if ings:
                        out += "<p><strong>Ingredients:</strong></p><ul>" + "".join(f"<li>{html.escape(str(i))}</li>" for i in ings) + "</ul>"
                    if steps:
                        step_texts = []
                        for st in steps:
                            if isinstance(st, dict):
                                step_texts.append(st.get("text", ""))
                            else:
                                step_texts.append(str(st))
                        out += "<p><strong>Instructions:</strong></p><ol>" + "".join(f"<li>{html.escape(t)}</li>" for t in step_texts if t) + "</ol>"
                    if out:
                        return out
        except Exception:
            continue
    return None

FEEDS = [
    # National Breaking & Politics
    ("Philippine Daily Inquirer", gnews("site:inquirer.net+when:1d")),
    ("Rappler", gnews("site:rappler.com+when:1d")),
    ("Philstar Headlines", gnews("site:philstar.com+when:1d")),
    ("GMA News", gnews("site:gmanetwork.com+news+when:1d")),

    # Davao & Mindanao Local
    ("MindaNews", gnews("site:mindanews.com+when:2d")),
    ("Edge Davao", direct("edgedavao.net", "feed/")),
    ("SunStar Davao", gnews("site:sunstar.com.ph+davao+when:2d")),

    # Business & PH Economy
    ("BusinessWorld", gnews("site:bworldonline.com+when:1d")),
    ("Inquirer Business", gnews("site:business.inquirer.net+when:1d")),
    ("Philstar Business", gnews("site:philstar.com+business+when:1d")),

    # Tech & Gadgets
    ("YugaTech", direct(W + "yugatech.com", "feed/")),
    ("Unbox PH", direct("unbox.ph", "feed/")),
    ("The Verge", direct(W + "theverge.com", "rss/index.xml")),

    # Sports
    ("Spin.ph", gnews("site:spin.ph+when:1d")),
    ("Tiebreaker Times", direct("tiebreakertimes.com.ph", "feed/")),

    # Lifestyle & Culture
    ("Pepper.ph", gnews("site:pepper.ph+recipes+when:30d")),
    ("Inquirer Lifestyle", gnews("site:lifestyle.inquirer.net+when:2d")),

    # World Headlines
    ("BBC World", direct("feeds.bbci.co.uk", "news/world/rss.xml")),
    ("Al Jazeera", direct(W + "aljazeera.com", "xml/rss/all.xml")),
]

now_mnl = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
today_str = now_mnl.strftime("%Y-%m-%d")
nice_date = now_mnl.strftime("%b %d, %Y")

book = epub.EpubBook()
book.set_identifier(f"daily-digest-{today_str}")
book.set_title(f"Daily Digest - {nice_date}")
book.set_language("en")
book.add_author("Daily News Bot")

chapters = []

for idx, (name, url) in enumerate(FEEDS):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        parsed = feedparser.parse(resp.content)
    except Exception:
        parsed = feedparser.parse("")

    if not parsed.entries:
        continue

    items_html = f"<h1>{html.escape(name)}</h1>"
    limit = 2 if name == "Pepper.ph" else 4

    for entry in parsed.entries[:limit]:
        raw_title = entry.get("title", "No Title")
        title = html.escape(raw_title)
        raw_link = entry.get("link", "")
        real_link = resolve_url(raw_link) if raw_link else ""

        page_html = ""
        full_text = None
        if real_link and "google.com" not in real_link:
            try:
                art_resp = requests.get(real_link, headers=HEADERS, timeout=12)
                if art_resp.status_code == 200:
                    page_html = art_resp.text
                    full_text = trafilatura.extract(page_html, include_comments=False)
            except Exception:
                pass

        if name == "Pepper.ph" and page_html:
            recipe_block = extract_recipe_html(page_html)
            if recipe_block:
                items_html += f"<h3>{title}</h3>{recipe_block}<hr/>"
                continue

        if not full_text and entry.get("content"):
            raw_content = entry["content"][0].get("value", "")
            full_text = trafilatura.extract(raw_content, include_comments=False)

        if full_text:
            brief_text = html.escape(make_brief(full_text, raw_title))
            paragraphs = f"<p>{brief_text}</p>"
        else:
            raw_summary = trafilatura.extract(entry.get("summary", "")) or ""
            cleaned_summary = make_brief(raw_summary, raw_title)
            if len(cleaned_summary) < 25:
                cleaned_summary = "Full text blocked by publisher; headline only."
            paragraphs = f"<p>{html.escape(cleaned_summary)}</p>"

        items_html += f"<h3>{title}</h3>{paragraphs}<hr/>"

    c = epub.EpubHtml(title=name, file_name=f"section_{idx}.xhtml", lang="en")
    c.content = f"<html><body>{items_html}</body></html>"
    book.add_item(c)
    chapters.append(c)

if not chapters:
    c = epub.EpubHtml(title="Notice", file_name="section_0.xhtml", lang="en")
    c.content = "<html><body><h1>No articles fetched today.</h1></body></html>"
    book.add_item(c)
    chapters.append(c)

book.toc = tuple(chapters)
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())
book.spine = ["nav"] + chapters

os.makedirs("docs", exist_ok=True)
epub_filename = "Daily-Digest.epub"
epub.write_epub(f"docs/{epub_filename}", book)

base_url = f"https:{S}{S}{GITHUB_USER}.github.io{S}{REPO_NAME}"

opds = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http:{S}{S}www.w3.org{S}2005{S}Atom">
  <id>urn:daily-newspaper</id>
  <title>My Daily Newspaper</title>
  <updated>{today_str}T06:00:00Z</updated>
  <entry>
    <title>Daily Digest ({nice_date})</title>
    <id>urn:daily-digest:{today_str}</id>
    <updated>{today_str}T06:00:00Z</updated>
    <author><name>Daily News Bot</name></author>
    <link rel="http:{S}{S}opds-spec.org{S}acquisition" href="{base_url}{S}{epub_filename}" type="application/epub+zip"/>
  </entry>
</feed>"""

with open("docs/opds.xml", "w", encoding="utf-8") as f:
    f.write(opds)
