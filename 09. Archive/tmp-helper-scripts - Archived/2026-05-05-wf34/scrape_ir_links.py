import requests, re
from bs4 import BeautifulSoup
urls={'AMD':'https://ir.amd.com/news-events/press-releases','ETN':'https://www.eaton.com/us/en-us/company/news-insights/news-releases.html','SMCI':'https://ir.supermicro.com/news-events/press-releases'}
for t,u in urls.items():
 print('\n---',t,u)
 try:
  r=requests.get(u,timeout=20,headers={'User-Agent':'Mozilla/5.0'})
  print('status',r.status_code,'len',len(r.text))
  soup=BeautifulSoup(r.text,'html.parser')
  for a in soup.find_all('a',href=True)[:200]:
   txt=' '.join(a.get_text(' ',strip=True).split())
   href=a['href']
   if any(term.lower() in (txt+' '+href).lower() for term in ['earnings','quarter','results','financial','q1','q3','2026']):
    print(txt[:160], href)
 except Exception as e: print(type(e).__name__, e)
