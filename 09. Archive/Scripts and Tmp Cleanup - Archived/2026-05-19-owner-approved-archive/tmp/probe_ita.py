from pathlib import Path
text=Path('tmp/ita-ishares-holdings.csv').read_text('utf-8',errors='ignore')
terms=['formattedValue":"$','formattedValue":"0.','Net Assets','Aerospace & Defense','Dow Jones U.S. Select Aerospace & Defense Index','0.40','Expense Ratio','Management Fee']
for term in terms:
    print('\nTERM',term)
    start=0
    for k in range(8):
        i=text.find(term,start)
        print(i)
        if i==-1: break
        print(text[i-250:i+500])
        start=i+1
