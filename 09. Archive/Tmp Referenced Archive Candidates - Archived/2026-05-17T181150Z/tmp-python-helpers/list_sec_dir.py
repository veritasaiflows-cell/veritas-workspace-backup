import requests,re
url='https://www.sec.gov/Archives/edgar/data/1075531/000107553126000024/'
headers={'User-Agent':'OpenClaw Veritas research contact@example.com'}
html=requests.get(url,headers=headers,timeout=20).text
for href in sorted(set(re.findall(r'href="([^"]+)"', html))):
    if 'bkng' in href.lower() or 'ex' in href.lower() or href.endswith('.htm'):
        print(href)
