import datetime, os, html, re, json
import requests
import feedparser
import trafilatura
from ebooklib import epub

GITHUB_USER = "residentevil789"
REPO_NAME = "daily-news"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9"
}

S = chr(47)
W = "www" + "."

def direct(host, path):
    return f"https:{S}{S}{host}{S}{path}"

def format_paragraphs(text, title=""):
    lines = [p.strip() for p in text.split("\n") if p.strip()]
    if lines and title and lines[0].lower() == title.lower():
        lines = lines[1:]
    return "".join(f"<p>{html.escape(p)}</p>" for p in lines)

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
                        step_texts = [st.get("text", "") if isinstance(st, dict) else str(st) for st in steps]
                        out += "<p><strong>Instructions:</strong></p><ol>" + "".join(f"<li>{html.escape(t)}</li>" for t in step_texts if t) + "</ol>"
                    if out:
                        return out
        except Exception:
            continue
    return None

def get_pepper_recipes():
    try:
        resp = requests.get(direct("pepper.ph", "recipes"), headers=HEADERS, timeout=15)
        slugs = re.findall(r'href="(/recipes/[a-z0-9\-]+)"', resp.text)
        seen = []
        for sl in slugs:
            if sl not in seen and sl != "/recipes":
                seen.append(sl)
            if len(seen) >= 6:
                break
        html_out = "<h1>Pepper.ph</h1>"
        for sl in seen:
            r_url = f"https:{S}{S}pepper.ph{sl}"
            r_resp = requests.get(r_url, headers=HEADERS, timeout=15)
            title_m = re.search(r'<h1[^>]*>(.*?)</h1>', r_resp.text, re.S)
            r_title = html.escape(re.sub(r'<[^>]+>', '', title_m.group(1)).strip()) if title_m else sl
            rec_body = extract_recipe_html(r_resp.text)
            if not rec_body:
                txt = trafilatura.extract(r_resp.text, include_comments=False) or "Recipe details unavailable."
                rec_body = format_paragraphs(txt, r_title)
            html_out += f"<h3>{r_title}</h3>{rec_body}<hr/>"
        return html_out if seen else None
    except Exception:
        return None

SPAM_WORDS = ("casino", "gambling", "betting", "slot", "sabong", "poker", "roulette", "jackpot", "bangladeshi")

FEEDS = [
    ("Philippine Daily Inquirer", direct("newsinfo.inquirer.net", "feed")),
    ("Rappler", direct(W + "rappler.com", "feed/")),
    ("Philstar Headlines", direct(W + "philstar.com", "rss/headlines")),
    ("GMA News", direct("://gmanetwork.com", "gno/rss/news/nation/feed.xml")),
    ("MindaNews", direct("mindanews.com", "feed/")),
    ("SunStar Davao", direct(W + "sunstar.com.ph", "api/v1/collections/davao.rss")),
    ("BusinessWorld", direct(W + "bworldonline.com", "feed/")),
    ("Inquirer Business", direct("business.inquirer.net", "feed")),
    ("Philstar Business", direct(W + "philstar.com", "rss/business")),
    ("YugaTech", direct(W + "yugatech.com", "feed/")),
    ("Unbox PH", direct("unbox.ph", "feed/")),
    ("The Verge", direct(W + "theverge.com", "rss/index.xml")),
    ("Spin.ph", direct(W + "spin.ph", "feed")),
    ("Tiebreaker Times", direct("tiebreakertimes.com.ph", "feed/")),
    ("Inquirer Lifestyle", direct("lifestyle.inquirer.net", "feed")),
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
    added = 0

    for entry in parsed.entries:
        if added >= 4:
            break
        raw_title = entry.get("title", "No Title")
        low_title = raw_title.lower()
        if any(w in low_title for w in SPAM_WORDS):
            continue

        title = html.escape(raw_title)
        link = entry.get("link", "")

        full_text = None
        if link:
            try:
                art_resp = requests.get(link, headers=HEADERS, timeout=12)
                if art_resp.status_code == 200:
                    full_text = trafilatura.extract(art_resp.text, include_comments=False)
            except Exception:
                pass

        if not full_text:
            raw_feed_html = ""
            if entry.get("content"):
                raw_feed_html = entry["content"][0].get("value", "")
            if not raw_feed_html:
                raw_feed_html = entry.get("summary", entry.get("description", ""))
            if raw_feed_html:
                full_text = trafilatura.extract(raw_feed_html, include_comments=False) or re.sub(r'<[^>]+>', ' ', raw_feed_html)

        if not full_text or len(full_text.strip()) < 30:
            continue

        body_html = format_paragraphs(full_text, raw_title)
        items_html += f"<h3>{title}</h3>{body_html}<hr/>"
        added += 1

    if added > 0:
        c = epub.EpubHtml(title=name, file_name=f"section_{idx}.xhtml", lang="en")
        c.content = f"<html><body>{items_html}</body></html>"
        book.add_item(c)
        chapters.append(c)

pepper_html = get_pepper_recipes()
if pepper_html:
    c = epub.EpubHtml(title="Pepper.ph", file_name="section_pepper.xhtml", lang="en")
    c.content = f"<html><body>{pepper_html}</body></html>"
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
