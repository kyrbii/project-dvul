# Ruff & Reviewdog

## Lokal

Ruff installieren:
```bash
pip install ruff
```

Code prüfen und fixen **vor jedem Commit**:
```bash
ruff check --fix .   # Lint-Fehler automatisch beheben
ruff format .        # Code formatieren
```

Danach normal committen und pushen:
```bash
git add .
git commit -m "fix: ruff errors"
git push
```

---

## Auf GitHub (Reviewdog)

Reviewdog läuft automatisch bei jedem **Pull Request** — ihr müsst nichts manuell tun.

1. Pull Request öffnen
2. Unter **"Files changed"** erscheinen Kommentare direkt an der betroffenen Zeile
3. Fehler lokal beheben (siehe oben)
4. Erneut pushen — Kommentare verschwinden

