import re
import requests

html = requests.get('https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html', timeout=20).text
print('len', len(html))
patterns = [
    r'https://[^"\']+',
    r'/[^"\']*FedWatch[^"\']*',
    r'/[^"\']*fedwatch[^"\']*',
    r'[A-Za-z0-9_/.-]*FedWatch[A-Za-z0-9_/.-]*',
    r'[A-Za-z0-9_/.-]*fedwatch[A-Za-z0-9_/.-]*',
]
found = set()
for pattern in patterns:
    for match in re.findall(pattern, html):
        found.add(match)
for item in sorted(found)[:300]:
    print(item)
