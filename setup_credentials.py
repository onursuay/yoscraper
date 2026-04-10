"""
Railway deploy sırasında GOOGLE_SERVICE_ACCOUNT_JSON env variable'ından
credentials/service_account.json dosyasını oluşturur.
"""
import os
import json

sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

if sa_json:
    os.makedirs("credentials", exist_ok=True)
    with open("credentials/service_account.json", "w") as f:
        json.dump(json.loads(sa_json), f, indent=2)
    print("✓ credentials/service_account.json oluşturuldu.")
else:
    print("⚠ GOOGLE_SERVICE_ACCOUNT_JSON env variable bulunamadı.")
    print("  Railway Variables'a ekleyin: GOOGLE_SERVICE_ACCOUNT_JSON = <service_account.json içeriği>")
