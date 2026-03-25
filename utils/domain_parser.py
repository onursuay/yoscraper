import re
import tldextract

# Sik kullanilan Turkce is kelimeleri - domain segmentasyonu icin
TURKISH_WORDS = [
    # Uzun kelimeler once (greedy matching)
    "otomotiv", "elektronik", "mobilya", "muhendislik", "danismanlik",
    "pazarlama", "matbaa", "nakliyat", "sigortacilik", "muhasebe",
    "gayrimenkul", "dekorasyon", "organizasyon", "muhendis", "mimarlik",
    "peyzaj", "aluminyum", "plastik", "ambalaj", "tekstil",
    "turizm", "otelcilik", "restoran", "lokanta", "market",
    "eczane", "klinik", "hastane", "laboratuvar", "veteriner",
    "avukat", "hukuk", "noter", "denetim", "musavirlik",
    "insaat", "yapi", "boya", "zemin", "cati", "izolasyon",
    "elektrik", "tesisat", "klima", "kombi", "asansor",
    "guvenlik", "kamera", "alarm", "yangin", "itfaiye",
    "egitim", "kurs", "okul", "kreche", "anaokul",
    "medya", "reklam", "ajans", "basim", "yayin",
    "lojistik", "kargo", "tasima", "depo", "antrepo",
    "yazilim", "bilisim", "teknoloji", "bilgisayar", "internet",
    "tasarim", "grafik", "foto", "video", "produksiyon",
    "temizlik", "hijyen", "camasir", "dezenfeksiyon",
    "tarim", "sera", "tohum", "gubre", "sulama",
    "gida", "balik", "tavuk", "sut", "peynir", "ekmek", "pasta",
    "oto", "araba", "arac", "motor", "lastik", "yedek", "parca",
    "kuyumcu", "sarraf", "altin", "gumus",
    "spor", "fitness", "pilates",
    "ozel", "grup", "merkez", "plaza", "center",
    "pazar", "pazari", "magazasi", "magazalari", "dukkan",
    "satis", "servis", "bakim", "onarim", "tamir",
    "halı", "perde", "koltuk", "doseme", "kaplama",
    "celik", "demir", "metal", "bakir", "krom",
    "kimya", "boya", "vernik", "solvent",
    "makine", "makina", "imalat", "uretim", "fabrika",
    "dis", "goz", "kulak", "burun", "kalp", "beyin",
    "ticaret", "ithalat", "ihracat", "toptan", "perakende",
    "holding", "sanayi", "limited", "anonim",
    "turkiye", "istanbul", "ankara", "izmir", "bursa", "antalya",
    "adana", "konya", "gaziantep", "mersin", "kayseri",
    "san", "tic", "ltd", "sti",
]

# Uzunluga gore sirala (uzun kelimeler once eslessin)
TURKISH_WORDS.sort(key=len, reverse=True)


def segment_domain_name(name: str) -> list[str]:
    """Domain adini Turkce kelimelere ayir."""
    name = name.lower()
    words = []
    i = 0

    while i < len(name):
        matched = False
        for word in TURKISH_WORDS:
            if name[i:].startswith(word):
                words.append(word)
                i += len(word)
                matched = True
                break
        if not matched:
            # Eslesmezse bir sonraki harfe gec, kelime olarak biriktir
            if words and not isinstance(words[-1], bool):
                # Son eklenen bir parcaysa ona ekle
                if len(words[-1]) <= 2 and not any(words[-1] == w for w in TURKISH_WORDS):
                    words[-1] += name[i]
                else:
                    words.append(name[i])
            else:
                words.append(name[i])
            i += 1

    # Tek karakterli parcalari birlestir
    merged = []
    buffer = ""
    for w in words:
        if len(w) == 1 and w not in TURKISH_WORDS:
            buffer += w
        else:
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append(w)
    if buffer:
        merged.append(buffer)

    return merged


def domain_to_business_name(url: str) -> str:
    """URL'deki domainden firma adini cikar.

    Ornek: arabapazari.com -> Araba Pazari
           otolastik.com -> Oto Lastik
    """
    extracted = tldextract.extract(url)
    domain_name = extracted.domain

    if not domain_name:
        return url

    # Tire ve alt cizgi ile ayrilmis domainler (kolay durum)
    if "-" in domain_name or "_" in domain_name:
        parts = re.split(r"[-_]", domain_name)
        return " ".join(p.capitalize() for p in parts if p)

    # Rakam ayirma
    # ornegi: 3dyazici -> 3D Yazici
    parts = re.split(r"(\d+)", domain_name)
    if len(parts) > 1:
        result_parts = []
        for part in parts:
            if part.isdigit():
                result_parts.append(part)
            elif part:
                segmented = segment_domain_name(part)
                result_parts.extend(segmented)
        return " ".join(p.capitalize() if not p.isdigit() else p for p in result_parts if p)

    # Turkce kelime segmentasyonu dene
    segmented = segment_domain_name(domain_name)

    if len(segmented) > 1:
        return " ".join(w.capitalize() for w in segmented if w)

    # Fallback: dogrudan capitalize
    return domain_name.capitalize()
