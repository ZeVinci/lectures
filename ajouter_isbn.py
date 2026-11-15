"""Ajoute un ISBN à chaque livre de lectures.json, en interrogeant Open Library.

Utilisation (dans le dossier du site) :
    python ajouter_isbn.py            # traite les livres qui n'ont pas encore d'ISBN
    python ajouter_isbn.py --tout     # refait tous les livres

Pour chaque livre, le script :
  1. cherche l'œuvre par titre + auteur ;
  2. parmi ses éditions, prend de préférence une édition dans la langue où tu l'as lu ;
  3. écrit "isbn" (ISBN-13 si possible) et "isbn_verifier": true quand le résultat
     est incertain (aucune édition dans ta langue de lecture, ou titre trouvé différent).

Une copie de sauvegarde lectures.json.bak est créée avant toute écriture.
Le script s'arrête proprement avec Ctrl+C : ce qui a déjà été trouvé est enregistré.
Il ne nécessite que Python 3 (aucune bibliothèque à installer).
"""
import json, shutil, sys, time, unicodedata, urllib.parse, urllib.request

FICHIER = "lectures.json"
UA = {"User-Agent": "historique-lectures/1.0 (usage personnel)"}
LANG_OL = {"français": "fre", "anglais": "eng", "italien": "ita", "allemand": "ger"}
PAUSE = 1.0  # secondes entre deux appels, pour respecter Open Library


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def simple(s):
    s = unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()
    return "".join(c for c in s if c.isalnum() or c == " ").split()


def proche(a, b):
    """Vrai si les deux titres partagent l'essentiel de leurs mots."""
    wa, wb = set(simple(a)), set(simple(b))
    return bool(wa and wb) and len(wa & wb) / min(len(wa), len(wb)) >= 0.6


def premier_auteur(auteur):
    return auteur.split(",")[0].split("/")[0].split(" et ")[0].strip()


def chercher(livre):
    q = {"title": livre["titre"], "author": premier_auteur(livre["auteur"]),
         "fields": "key,title", "limit": "3"}
    docs = get("https://openlibrary.org/search.json?" + urllib.parse.urlencode(q)).get("docs", [])
    time.sleep(PAUSE)
    if not docs:  # second essai : titre seul
        q.pop("author")
        docs = get("https://openlibrary.org/search.json?" + urllib.parse.urlencode(q)).get("docs", [])
        time.sleep(PAUSE)
    if not docs:
        return None, True
    oeuvre = docs[0]
    eds = get(f"https://openlibrary.org{oeuvre['key']}/editions.json?limit=200").get("entries", [])
    time.sleep(PAUSE)
    langue = LANG_OL.get(livre["langue_lue"])

    def isbn(e):
        return (e.get("isbn_13") or e.get("isbn_10") or [None])[0]

    avec_isbn = [e for e in eds if isbn(e)]
    dans_ma_langue = [e for e in avec_isbn
                      if any(l.get("key", "").endswith("/" + str(langue)) for l in e.get("languages", []))]
    choix = (dans_ma_langue or avec_isbn or [None])[0]
    if not choix:
        return None, True
    incertain = not dans_ma_langue or not proche(livre["titre"], oeuvre.get("title", ""))
    return isbn(choix), incertain


def main():
    tout = "--tout" in sys.argv
    with open(FICHIER, encoding="utf-8") as f:
        data = json.load(f)
    shutil.copy(FICHIER, FICHIER + ".bak")
    livres = [b for b in data["livres"] if tout or not b.get("isbn")]
    print(f"{len(livres)} livres à traiter (environ {len(livres) * 3 * PAUSE / 60:.0f} min)…")
    trouves = incertains = 0
    try:
        for i, b in enumerate(livres, 1):
            try:
                isbn, incertain = chercher(b)
            except Exception as e:  # réseau, quota… on passe au suivant
                print(f"  [{i}] erreur pour « {b['titre']} » : {e}")
                time.sleep(5)
                continue
            if isbn:
                b["isbn"] = isbn
                trouves += 1
                if incertain:
                    b["isbn_verifier"] = True
                    incertains += 1
                else:
                    b.pop("isbn_verifier", None)
            print(f"  [{i}/{len(livres)}] {b['titre'][:50]:50} → {isbn or 'non trouvé'}{' (à vérifier)' if isbn and incertain else ''}")
    except KeyboardInterrupt:
        print("\nInterrompu, enregistrement de ce qui a été trouvé…")
    with open(FICHIER, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"Terminé : {trouves} ISBN ajoutés, dont {incertains} à vérifier. Sauvegarde : {FICHIER}.bak")


if __name__ == "__main__":
    main()
