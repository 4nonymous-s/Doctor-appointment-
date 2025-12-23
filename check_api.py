"""
Simple helper to check the local Flask API endpoints.
Run from PowerShell (or any shell) with:

  python check_api.py

This avoids quoting/REPL issues that happen when pasting one-liners into the Python REPL.
"""
import http.client
import json

HOST = '127.0.0.1'
PORT = 5000

def fetch(path):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=10)
    try:
        conn.request('GET', path)
        r = conn.getresponse()
        body = r.read()
        try:
            text = body.decode('utf-8')
        except Exception:
            text = repr(body)
        return r.status, r.getheader('Content-Type'), text
    finally:
        conn.close()

if __name__ == '__main__':
    paths = ['/api/hospitals', '/api/hospital/1/doctors', '/']
    for p in paths:
        print('\nRequesting', p)
        try:
            status, ctype, body = fetch(p)
            print('Status:', status)
            print('Content-Type:', ctype)
            # print first 800 chars of body
            print('Body (first 800 chars):')
            print(body[:800])
        except Exception as e:
            print('Error requesting', p, '-', e)

    print('\nDone. If you see SyntaxError in your terminal, make sure you are NOT inside the Python REPL (exit with exit() or Ctrl+Z then Enter) and run `python check_api.py` from PowerShell.')
