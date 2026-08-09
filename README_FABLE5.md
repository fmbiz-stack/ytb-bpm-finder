# Emblèmes BO2 — dossier de travail complet

Tout ce qu'il faut pour continuer le projet sans contexte extérieur. Rien ici ne
dépend d'une conversation précédente.

---

## Par où commencer

1. **`ENVOI_EMBLEMES.md`** — à lire en premier. Instructions de traitement du lot
   d'emblèmes capturés : dédoublonnage, filtre de calibre, contenu explicite, et
   le piège de sélection à éviter absolument.
2. **`EMBLEM_AI_BRIEF.md`** — le brief d'origine. Format, contraintes, prior art,
   modes d'échec, directions candidates. Le contexte de fond.
3. **`emblem_export/`** — le lot lui-même (voir §« À faire côté humain » si le
   dossier est absent).

---

## Contenu

| | |
|---|---|
| `ENVOI_EMBLEMES.md` | traitement du lot capturé |
| `EMBLEM_AI_BRIEF.md` | brief d'origine, format et architecture |
| `bo2_shapes_by_id/` | **les 261 formes**, nommées `<id>_<catégorie>_<nom>.png`, + `shapes.csv` |
| `emblem_export/` | le lot d'emblèmes capturés : `.json` + `.bin` + `.png` par emblème, + `index.json` |
| `export_captures.py` | l'outil qui produit `emblem_export/` |
| `bo2-emblem-toolkit/` | le toolkit complet : proxy de capture/injection, parser, renderer calibré, carte des IDs |

Le toolkit tourne tel quel : `pip3 install Pillow`, puis `python3 run.py`. Sa
seule dépendance est Pillow.

---

## État des lieux

**Le format est résolu.** 1408 octets, 32 couches de 44 octets : `shapeId`
uint16, puis 9 float32 (R, G, B, A, posX, posY, scaleX, scaleY, rotation), puis
`outlined` et `flipped`. L'échelle est un **exposant** (échelle réelle = `2^v`),
la position une fraction du canvas, +Y vers le bas, index 0 au fond.

**Deux sources de fichiers, deux formats de conteneur :**

- fichiers Plutonium (PC) : 1745–1746 octets, header variable + les **1408
  derniers octets**, little-endian
- captures console (ce lot) : en-têtes HTTP, `\r\n\r\n`, puis les 1408 octets.
  Le byte order **varie selon la console** — PS3 big-endian, PS4/PS5
  little-endian. Il est indiqué par fichier dans le `.json`.

**Clamps mesurés :** exposant d'échelle **±6,0** (jusqu'à 64× le canvas),
position **±1,0**. Confirmé par deux chemins indépendants — mesure directe sur
les fichiers, et l'erreur de rasterisation du renderer à
`(2^6 × 220 × √2)² ≈ 396 M px`.

**Technique experte mesurée (n=5, à rejouer sur ce lot) :** 32 couches saturées
(médiane), 2–8 tons (médiane 5), ~35 % des couches en carving, 89 % des couches
issues des primitives `tools`. Ordre de construction observé : fond → masses →
traits → carving → lueurs.

---

## Trois problèmes connus, à ne pas confondre avec de la donnée corrompue

### 1. Deux IDs de formes sont faux

`057` et `096` sont **la même image** dans `bo2_shapes_by_id/` — les deux ont été
mappés sur « Interruption » en amont — et la forme **« Hail Mary » est absente du
jeu de fichiers**, aucun ID ne pointe dessus. 261 fichiers, 260 formes distinctes.

Non résoluble sans vérification en jeu. **Traiter 57 et 96 comme non fiables.**
Un ID faux produit un rendu faux, donc une correspondance forme↔ID incorrecte
apprise sans qu'aucune erreur ne se déclenche.

### 2. Des formes disparaissent de certains rendus

Observé : Half Column (ID 172) absente du rendu de l'emblème « Jesus Christ », et
des formes manquantes dans la bouche et la barbe d'un emblème Batman — alors
qu'elles sont bien présentes dans les octets.

Deux hypothèses ont été testées et **écartées** : le placement hors-canvas (le
compositing clippe correctement, il ne jette pas) et le chemin `outlined` (il
produit bien des pixels à toutes les échelles testées). La cause reste
non identifiée.

Pour la localiser, chaque `.json` porte maintenant `visible_alone` par couche et
`layers_not_visible_alone` au niveau de l'emblème : la liste des couches qui ne
dessinent **rien** quand on les rend seules. Une couche recouverte par une couche
ultérieure n'est pas signalée — c'est du carving, c'est voulu.

**La vérité est dans le `.bin` et le `.json`, jamais dans le `.png`.**

### 3. Les emblèmes ambitieux ne se rendent pas à pleine taille

Le renderer matérialise chaque couche à `2^exposant × taille de sortie`. À
l'exposant 6, ça demande un bitmap de 16k pixels de large pour une sortie de
256 px — Pillow le refuse comme decompression bomb.

Le renderer choisit désormais une taille de sortie compatible avec la plus
grande couche (`safe_render_size`), donc ces emblèmes sortent en petite
vignette au lieu d'échouer. `png_rendered_at` indique la taille retenue.

⚠️ **Conséquence méthodologique :** ne jamais filtrer le lot sur « est-ce que ça
rend » ou « est-ce que c'est joli » en regardant les PNG. Les emblèmes qui
peinent au rendu sont exactement ceux qui poussent l'échelle à la borne, donc les
plus sophistiqués. Un filtre visuel écarterait le haut du panier et biaiserait
toutes les statistiques vers le basique. Filtrer sur les couches, jamais sur
l'image.

---

## À faire côté humain

Si `emblem_export/` est absent ou à rafraîchir, sur la machine qui a fait les
captures :

```bash
python3 export_captures.py
```

Il trouve les captures tout seul (`~/Library/Application Support/BO2EmblemToolkit/saved`
sur macOS, à côté de l'exécutable sur Windows, `saved/` à la racine si lancé
depuis les sources). Sinon `--saved <chemin>`.

Capturer plus d'emblèmes : lancer le toolkit, passer en mode **Capture**, et
ouvrir les profils d'autres joueurs sur la console. Chaque emblème affiché est
enregistré automatiquement.
