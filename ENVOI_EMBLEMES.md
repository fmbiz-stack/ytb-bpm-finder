# Lot d'emblèmes capturés — instructions de traitement

Suite au rapport « Résultats & solution ». Tes conclusions tiennent, rien à
revoir. Ce document accompagne un **nouveau lot de données** : des emblèmes
capturés sur console via le proxy, bien plus nombreux que les 5 fichiers
Plutonium de départ.

C'est la moisson de corpus que tu identifiais comme la voie de fermeture sur le
tiers portrait. Elle commence ici.

---

## 1. Ce que contient le lot

Produit par `export_captures.py`. Pour chaque emblème, trois fichiers de même nom :

| | |
|---|---|
| `<nom>.json` | les couches décodées : `shape`, `shape_name` résolu, RGBA, x/y, sx/sy, rotation, `outlined`, `flipped` — plus `layers_used`, `max_scale_exponent`, `byte_order` |
| `<nom>.bin` | les octets bruts d'origine, intacts |
| `<nom>.png` | le rendu — **à traiter comme indicatif, pas comme vérité** (voir §3) |

Plus un `index.json` qui liste tout sans les couches.

⚠️ **Format différent des 5 fichiers Plutonium.** Ceux-ci viennent du réseau, pas
du disque : `.bin` = en-têtes HTTP suivis du payload de 1408 octets. Pas de
header Plutonium, pas de nom `Emblem_<n>`. Le séparateur est `\r\n\r\n`, le
payload est ce qui suit. Le byte order est indiqué par fichier dans le JSON —
détecté, pas supposé, parce qu'une capture PS3 est big-endian là où PS4/PS5 sont
little-endian.

---

## 2. Trois filtres à appliquer avant analyse

### a. Dédoublonner

Il y aura des doublons, beaucoup. Le proxy enregistre **chaque requête de slot**
que la console émet, et la console redemande les mêmes emblèmes en boucle en
naviguant. Le même emblème apparaîtra sous plusieurs groupes et plusieurs slots.

Déduplique sur les **1408 octets du payload** (hash), pas sur le nom de fichier
ni sur le PNG. Deux captures du même emblème sont bit-identiques.

### b. Ne garder que le haut calibre

**C'est le filtre le plus important, et le lot est majoritairement du remplissage.**
Beaucoup de captures sont des emblèmes basiques — un préfab posé seul, une
silhouette de voiture, un chien, un cœur. Ils sont sans valeur pour extraire de
la technique et vont diluer toutes tes statistiques.

N'analyse que ce qui est du même calibre que les 5 fichiers de départ. Tes
propres mesures donnent le filtre objectif, bien meilleur que l'œil :

- **couches utilisées** — les experts saturent (médiane 32). En dessous de ~20,
  écarte par défaut.
- **taux de carving** — ~35 % chez les experts. Un emblème sans carving n'est
  presque jamais du haut calibre.
- **exposant d'échelle** — l'usage de grandes valeurs signale la technique de la
  forme géante coupée par le cadre.
- **part de `tools`** — 89 % chez les experts. Un emblème à 90 % de préfabs est
  un emblème basique, pas un emblème construit.

Un emblème à 4 couches dont 3 préfabs n'apprend rien. Jette sans regret.

### c. Ignorer le sujet, garder la construction

Une partie du lot sera **explicite ou de mauvais goût** — la communauté BO2 est
ce qu'elle est, et capturer au hasard ramène ce qui traîne. Attends-toi à en
voir.

Ça n'a aucune importance ici. Le sujet représenté n'entre dans aucune de tes
mesures : ce qui compte, ce sont les couches, les échelles, le carving, l'ordre
de construction. Un emblème vulgaire mais techniquement excellent est de la
**bonne donnée** — souvent la meilleure, parce que ceux qui investissent 32
couches saturées sont rarement en train de dessiner un cœur.

Traite-les si tu peux, écarte-les si tu préfères, mais ne les confonds pas avec
de la donnée de mauvaise qualité — ce n'est pas la même chose.

---

## 3. Certains rendus semblent perdre des formes

Cas concret : sur l'emblème « Jesus Christ », la forme **Half Column (ID 172)**
n'apparaît pas dans le PNG alors qu'elle est bien dans les octets.

**Ce n'est pas une donnée corrompue. C'est une limite du renderer**, et la cause
est directement liée à ta trouvaille sur les clamps.

Le renderer du toolkit met à l'échelle une couche en matérialisant tout le
bitmap à `2^exposant × taille de sortie`. À l'exposant 6,0 — la borne que tu as
mesurée — ça fait 64× le canvas. Pour une sortie 512 px, c'est une image de
32768 px que PIL refuse comme decompression bomb, et les tailles qui passent
tout juste sous la limite mettent des minutes.

**Confirmation indépendante de ton ±6,0 :** le panneau de contrôle a affiché
l'erreur `Image size (394816900 pixels) exceeds limit`. Or
`(2^6 × 220 × √2)² ≈ 396 M px` — soit exactement une couche à l'exposant 6 plus
l'expansion due à la rotation. Ton chiffre tombe juste, mesuré par deux chemins
indépendants.

**Conséquence pratique : la vérité est dans le `.json` et le `.bin`, jamais dans
le `.png`.** L'export sélectionne maintenant une taille de rendu compatible avec
la plus grande couche, donc les emblèmes extrêmes sortent en petite vignette —
`png_rendered_at` te dit à quelle taille, et `render_error` est rempli si aucun
PNG n'a pu être produit. La couche est toujours dans le JSON dans tous les cas.

### ⚠️ Le piège de sélection qui en découle

**Ne filtre jamais le lot sur « est-ce que ça rend » ou « est-ce que ça a l'air
bien » en regardant les PNG.**

Les emblèmes qui échouent au rendu sont exactement ceux qui poussent l'échelle à
la borne — c'est-à-dire **les plus sophistiqués**. Un filtre visuel écarterait
systématiquement le haut du panier et te laisserait avec les emblèmes simples,
en biaisant toutes tes statistiques dans le sens du basique.

Filtre sur les couches (§2b), jamais sur l'image.

---

## 4. Ce que j'attends de ce lot

1. **Rejouer 8.1 et 8.2 sur n bien plus grand que 5.** Tes clamps (±6,0 et ±1,0)
   et tes stats de technique (32 couches, 35 % de carving, 2–8 tons) reposent sur
   5 emblèmes. Confirme, corrige, ou resserre.
2. **Les idiomes de la direction D.** Tu en as trouvé une poignée sur 5 fichiers
   — paires outline-underlay, rampes de lueur, piles jitterées. Avec un vrai
   corpus, l'inventaire d'idiomes devient le **vocabulaire du compilateur** que
   tu recommandes. C'est probablement le rendement le plus élevé de ce lot.
3. **L'ordre de construction.** Tu as observé fond → masses → traits → carving →
   lueurs sur 5 fichiers. Est-ce que ça tient ? C'est l'ossature des passes du
   compilateur.
4. **Ce qui distingue le tiers portrait photoréaliste du tiers graphique**, en
   nombres. C'est là que tu situes le plafond à 70–80 %, et c'est là que le
   corpus a le plus de chances de le déplacer.

Si le lot est trop bruité pour valoir la peine après filtrage, dis-le
franchement plutôt que de forcer des conclusions dessus. Un « n=12 utilisables »
honnête vaut mieux qu'un n=200 pollué de silhouettes de voitures.
