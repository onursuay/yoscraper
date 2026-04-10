"""
Railway deploy sırasında GOOGLE_SERVICE_ACCOUNT_JSON env variable'ından
credentials/service_account.json dosyasını oluşturur.
"""
import os
import json
import sys

sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

print(f"[setup] GOOGLE_SERVICE_ACCOUNT_JSON uzunluk: {len(sa_json)} karakter")

if not sa_json:
    print("[setup] UYARI: GOOGLE_SERVICE_ACCOUNT_JSON env variable boş veya yok, atlanıyor.")
    sys.exit(0)

try:
    sa_data = json.loads(sa_json)
except json.JSONDecodeError as e:
    print(f"[setup] HATA: JSON parse edilemedi: {e}")
    print(f"[setup] İlk 100 karakter: {sa_json[:100]}")
    sys.exit(0)

os.makedirs("credentials", exist_ok=True)
with open("credentials/service_account.json", "w") as f:
    json.dump(sa_data, f, indent=2)

print(f"[setup] ✓ credentials/service_account.json oluşturuldu. project_id: {sa_data.get('project_id')}")
