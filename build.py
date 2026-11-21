import datetime, os, html
import requests
import feedparser
import trafilatura
from ebooklib import epub

GITHUB_USER = "residentevil789"
REPO_NAME = "daily-news"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://google.com)",
    "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8"
}

FEEDS = [
    # National Breaking & Politics
    ("Philippine Daily Inquirer", "https://google.com"),
    ("Rappler", "https://google.com"),
    ("Philstar Headlines", "https://google.com"),
    ("GMA News", "https://gmanetwork.com"),

    # Davao & Mindanao Local
    ("MindaNews", "https://mindanews.com"),
    ("Edge Davao", "https://edgedavao.net"),
    ("SunStar Davao", "https://google.com"),

    # Business & PH Economy
    ("BusinessWorld", "https://google.com"),
    ("Inquirer Business", "https://google.com"),
    ("Philstar Business", "https://google.com"),

    # Tech & Gadgets
    ("YugaTech", "https://yugatech.com"),
    ("Unbox PH", "https://unbox.ph"),
    ("The Verge", "https://theverge.com"),

    # Sports
    ("Spin.ph", "https://google.com"),
    ("Tiebreaker Times", "https://tiebreakertimes.com.ph"),

    # Lifestyle & Culture
    ("Pepper.ph", "https://pepper.ph"),
    ("Inquirer Lifestyle", "https://google.com"),

    # World Headlines
    ("BBC World", "https://bbci.co.uk"),
    ("Al Jazeera", "https://aljazeera.com"),
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
    except Exception as e:
        print(f"Failed {name}: {e}")
        parsed = feedparser.parse("")

    print(f"{name}: {len(parsed.entries)} entries")
    if not parsed.entries:
        continue

    items_html = f"<h1>{html.escape(name)}</h1>"
    for entry in parsed.entries[:4]:
        title = html.escape(entry.get("title", "No Title"))
        link = entry.get("link", "")

        full_text = None
        if link and "://google.com" not in link:
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

base_url = f"https://{GITHUB_USER}.github.io/{REPO_NAME}"

opds = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://w3.org">
  <id>urn:daily-newspaper</id>
  <title>My Daily Newspaper</title>
  <updated>{today_str}T06:00:00Z</updated>
  <entry>
    <title>Daily Digest ({nice_date})</title>
    <id>urn:daily-digest:{today_str}</id>
    <updated>{today_str}T06:00:00Z</updated>
    <author><name>Daily News Bot</name></author>
    <link rel="http://opds-spec.org" href="{base_url}/{epub_filename}" type="application/epub+zip"/>
  </entry>
</feed>"""

with open("docs/opds.xml", "w", encoding="utf-8") as f:
    f.write(opds)
