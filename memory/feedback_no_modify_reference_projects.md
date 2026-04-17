---
name: Referans proje dosyaları değiştirilemez
description: Referans olarak verilen proje klasörlerindeki hiçbir dosyaya dokunulmamalı
type: feedback
---

Referans proje klasörlerinde (voice_agent, YoAi_Project vb.) hiçbir zaman değişiklik yapılmamalıdır.

**Why:** Kullanıcı bu projeleri sadece tasarım/işlevsellik referansı olarak gösterir; kaynak kodları dokunulmaz kalmalıdır.

**How to apply:** Herhangi bir referans proje yolu verildiğinde sadece okuma (Read/Glob/Grep) yapılır, Edit/Write kesinlikle kullanılmaz.
