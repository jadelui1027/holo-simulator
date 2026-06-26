#!/usr/bin/env python3
import urllib.request, urllib.error, json
codes = ['6QCNY','3P552','11QBS','2QKVA','6QUSY','12CS8','7M4A4']
payload_variants = [
    lambda code: json.dumps({'id': code}).encode('utf-8'),
    lambda code: json.dumps({'code': code}).encode('utf-8'),
    lambda code: json.dumps({'deck_code': code}).encode('utf-8'),
    lambda code: json.dumps({'view_code': code}).encode('utf-8'),
    lambda code: json.dumps({}).encode('utf-8'),
]

for code in codes:
    url = f'https://decklog.bushiroad.com/system/app/api/view/{code}'
    print('\n==', code, 'POST trials ==')
    for i, make_payload in enumerate(payload_variants, 1):
        data = make_payload(code)
        try:
            headers = {
                'User-Agent':'Mozilla/5.0',
                'Accept':'application/json',
                'Content-Type':'application/json',
                'Referer': f'https://decklog.bushiroad.com/view/{code}'
            }
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=15) as resp:
                b = resp.read()
                ct = resp.headers.get('Content-Type','')
                print(' variant', i, 'status', getattr(resp,'status',None),'ct',ct,'len',len(b))
                if len(b)<1000:
                    print('  body:', b.decode('utf-8', errors='replace')[:400].replace('\n',' '))
        except urllib.error.HTTPError as e:
            print(' variant', i, 'HTTP', e.code)
        except Exception as e:
            print(' variant', i, 'ERR', e)
