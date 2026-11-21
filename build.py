import datetime, os, html
import requests
import feedparser
import trafilatura
from ebooklib import epub

GITHUB_USER = "residentevil789"
REPO_NAME = "daily-news"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*"
}

S = chr(47)

def gnews(query):
    host = "news." + "google." + "com"
    return f"https:{S}{S}{host}{S}rss{S}search?q={query}&hl=en-PH&gl=PH&ceid=PH:en"

def direct(host, path):
    return f"https:{S}{S}{host}{S}{path}"

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
    ("YugaTech", direct("://yugatech.com", "feed/")),
    ("Unbox PH", direct("unbox.ph", "feed/")),
    ("The Verge", direct("://theverge.com", "rss/index.xml")),

    # Sports
    ("Spin.ph", gnews("site:spin.ph+when:1d")),
    ("Tiebreaker Times", direct("tiebreakertimes.com.ph", "feed/")),

    # Lifestyle & Culture
    ("Pepper.ph", gnews("site:pepper.ph+when:7d")),
    ("Inquirer Lifestyle", gnews("site:lifestyle.inquirer.net+when:2d")),

    # World Headlines
    ("BBC World", direct("feeds.bbci.co.uk", "news/world/rss.xml")),
    ("Al Jazeera", direct("://aljazeera.com", "xml/rss/all.xml")),
]

now_mnl = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
today_str = now_mnl.strftime("%Y-%m-%d")
nice_date = now_mnl.strftime("%b %d, %Y")

book = epub.EpubBook()
book.set_identifier(f"daily-digest-{today_str}")
book.set_title(f"Daily Digest - {nice_date}")
book.set_language("en")
book.add_author("Daily News Bot")

debug_lines = [f"Run time (MNL): {now_mnl.strftime('%Y-%m-%d %H:%M:%S')}"]
chapters = []

for idx, (name, url) in enumerate(FEEDS):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        parsed = feedparser.parse(resp.content)
        debug_lines.append(f"{name}: HTTP {resp.status_code}, entries={len(parsed.entries)}")
    except Exception as e:
        debug_lines.append(f"{name}: ERROR {e}")
        parsed = feedparser.parse("")

    if not parsed.entries:
        continue

    items_html = f"<h1>{html.escape(name)}</h1>"
    for entry in parsed.entries[:4]:
        title = html.escape(entry.get("title", "No Title"))
        link = entry.get("link", "")

        full_text = None
        if link and "google.com" not in link:
            try:
                art_resp = requests.get(link, headers=HEADERS, timeout=12)
                if art_resp.status_code == 200:
                    full_text = trafilatura.extract(art_resp.text, include_comments=False)
            except Exception:
                pass

        if full_text:
            paragraphs = "".join(f"<p>{html.escape(p)}</p>" for p in full_text.split("\n") if p.strip())
        else:
            summary = entry.get("summary", entry.get("description", "No content available."))
            paragraphs = f"<div>{summary}</div>"

        items_html += f"<h2>{title}</h2>{paragraphs}<hr/>"

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

with open("docs/debug.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(debug_lines))

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
