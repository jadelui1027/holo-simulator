#!/usr/bin/env python3
import urllib.request, urllib.error, json, os
codes = ['6QCNY','3P552','11QBS','2QKVA','6QUSY','12CS8','7M4A4']
out = {}
for code in codes:
    url = f'https://decklog.bushiroad.com/system/app/api/view/{code}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = getattr(resp, 'status', None)
            headers = dict(resp.getheaders())
            data = resp.read()
            ct = resp.headers.get('Content-Type','')
            entry = {'_status': status, '_headers': headers, '_length': len(data)}
            if 'application/json' in ct:
                try:
                    entry['json'] = json.loads(data.decode('utf-8'))
                except Exception:
                    entry['_raw'] = data.decode('utf-8', errors='replace')
            else:
                entry['_raw'] = data.decode('utf-8', errors='replace')
            j = entry
    except urllib.error.HTTPError as e:
        j = {'_error': f'HTTP {e.code}', '_status': getattr(e, 'code', None)}
    except Exception as e:
        j = {'_error': str(e)}
    out[code] = j

with open('tools/api_probe_results.json','w',encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('Wrote tools/api_probe_results.json')
