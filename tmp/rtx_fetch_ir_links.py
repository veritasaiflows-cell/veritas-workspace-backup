import re
import requests

html = requests.get('https://investors.rtx.com/events/event-details/q1-2026-rtx-earnings-conference-call', timeout=30).text
links = re.findall(r'href="([^"]+)"', html)
for link in links:
    if 'static-files' in link:
        print(link)
