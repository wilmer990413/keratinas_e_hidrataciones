import json, sys
from app import create_app
app = create_app()
with app.test_client() as client:
    resp = client.get('/api/caja/resumen?fecha=2026-11-22')
    print('STATUS', resp.status_code)
    try:
        data = resp.get_json()
        print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
    except Exception as e:
        print('Error parsing JSON', e)
        sys.stdout.buffer.write(resp.data)
