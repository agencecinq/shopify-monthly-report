# Rapport mensuel Shopify

Un plugin Claude qui transforme les données d'une boutique Shopify en rapport
mensuel complet : une présentation PowerPoint aux couleurs de la boutique, qui
se termine par un plan des 90 prochains jours à objectifs chiffrés.

Il est fait pour le marchand, pas pour l'analyste. Il choisit les chapitres qui
ont du sens pour cette boutique-là, fait ressortir ce qui sort de l'ordinaire,
et dit sur quoi travailler ensuite, en chiffres vérifiables.

[English](README.md)

![Le plan des 90 jours](docs/plan.png)

## Ce qui le distingue

**Il s'adapte à la boutique.** Avant de collecter le moindre chiffre, il établit
la structure du catalogue, les canaux de vente, les pays, la présence
d'abonnements ou d'un point de vente, et si les clients reviennent. Une boutique
de consommables voit son chapitre Clients en deuxième position ; une boutique
d'équipement voit Acquisition. Un catalogue de 15 produits est détaillé jusqu'aux
tailles et aux couleurs ; un catalogue de 2 000 références est présenté par
gamme.

**Il priorise sans conseiller.** Le plan classe les chantiers par ce qu'ils
pèsent en euros, fixe un objectif pour chacun et calcule le gain : « ramener le
taux de remboursement de 10,0 % à 8,0 % récupère 900 € par mois au volume
actuel ». Chaque objectif est un niveau que la boutique a déjà atteint dans les
six derniers mois, donc atteignable par construction.

**Il n'énonce jamais de cause.** Aucune slide ne dit pourquoi un chiffre a
bougé, et aucune ne prescrit de remède. Aucun benchmark sectoriel nulle part :
tout repose sur ce qu'un poste coûte, sur la boutique comparée à elle-même, et
sur les seuils que le marchand a déclarés.

**Il se souvient.** Le contexte et le plan sont stockés dans un métachamp de la
boutique. Le rapport du mois suivant ouvre sur une slide de suivi qui confronte
chaque jalon à ce qui a été mesuré.

## Prérequis

- Le **connecteur Shopify** dans Claude. C'est la seule dépendance obligatoire.
- Python 3.9+ avec `python-pptx` et `Pillow`.

Les connecteurs email, analytics et publicité sont facultatifs. Absents, les
chapitres correspondants n'apparaissent pas, sans trou ni « non disponible ».

## Installation

Téléchargez le plugin depuis les
[Releases](https://github.com/agencecinq/shopify-monthly-report/releases) et
installez-le dans l'app Claude desktop, ou clonez le dépôt.

```bash
git clone https://github.com/agencecinq/shopify-monthly-report.git
pip install python-pptx Pillow
```

## Utilisation

Demandez-le en une phrase :

- « Fais-moi le rapport du mois dernier »
- « Les chiffres de septembre en présentation »
- « Un récap du trimestre pour mon associé »
- « Sur quoi je dois me concentrer ? »

Sans précision, le rapport porte sur le dernier mois calendaire complet.

La première fois sur une boutique, six questions sont posées une par une : qui
lit le rapport, ce que vend la boutique, l'objectif de chiffre d'affaires sur
l'année, si les coûts d'achat sont renseignés, quel taux de retour est jugé
acceptable, et quels canaux exclure. Les réponses vivent dans un métachamp de la
boutique : aucun fichier à conserver. Ensuite, une seule question par mois.

## Ce que contient le rapport

![Ce qui ressort ce mois-ci](docs/highlights.png)

Couverture, sommaire, l'essentiel du mois, ce qui ressort, le plan du mois
dernier, les 90 prochains jours, puis les chapitres : **Ventes** (évolution
quotidienne, historique 24 mois, détail, canaux), **Acquisition** (tunnel,
sources, pays et appareils), **Produits** (top ventes, gammes, déclinaisons,
stock, retours), **Clients**, **Rentabilité**, **Marketing**, et une slide de
méthode qui dit d'où vient chaque chiffre.

Chaque chapitre porte une ligne qui explique ce que la métrique mesure et
comment la lire. Les chapitres sans données ne sont pas générés.

## Langues

L'anglais et le français sont fournis. Utilisez `--lang fr`, `--lang en`, ou
renseignez `meta.lang` dans les données.

Le formatage des nombres et des devises suit la langue, pas seulement les mots :
le français écrit `35 396 €` et l'anglais `€35,396`.

Pour ajouter une langue, copiez
`skills/shopify-monthly-report/i18n/en.json`, traduisez les valeurs, gardez les
clés, et ajustez le bloc `_format`. Les contributions sont bienvenues. Une clé
manquante dans une traduction retombe sur l'anglais plutôt que d'afficher une
clé brute dans la présentation de quelqu'un.

## Essayer sans boutique Shopify

Le dépôt fournit un exemple complet sur une boutique fictive :

```bash
cd skills/shopify-monthly-report/scripts
python3 build_report.py --data ../../../examples/report.example.json \
  --lang fr -o rapport.pptx
```

Ce fichier sert aussi de référence pour le contrat de données, documenté dans
[`report-schema.md`](skills/shopify-monthly-report/references/report-schema.md).

## Fonctionnement

Claude collecte les données et écrit un `report.json` ; trois scripts Python en
font la présentation. Le découpage compte : tout ce qui doit être reproductible
est dans les scripts, pas dans la sortie du modèle.

| Fichier | Rôle |
|---|---|
| `scripts/brand.py` | Déduit une palette lisible du thème Shopify, gère les trois familles de thèmes et corrige les contrastes |
| `scripts/highlights.py` | Calcule les constats de saillance à partir de règles chiffrées |
| `scripts/priorities.py` | Construit le plan 90 jours : classement, objectifs, jalons |
| `scripts/build_report.py` | Assemble la présentation |
| `scripts/i18n.py` | Langue et formatage des nombres |

Les constats et les objectifs sont calculés, jamais rédigés par le modèle. C'est
ce qui les rend reproductibles d'un mois sur l'autre et d'une boutique à
l'autre, et ce qui empêche le rapport de dériver vers le conseil.

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md). Traductions, nouvelles règles de
saillance et prise en charge d'autres sources analytics sont les bienvenues.

## Licence

MIT, voir [LICENSE](LICENSE). Développé par
[Agence CINQ](https://agencecinq.com).
