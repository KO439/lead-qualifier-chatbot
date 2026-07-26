# Chatbot IA de qualification de leads — Version de départ



Architecture multi-agents (conversationnel / extraction / scoring) avec
API 100% gratuite (Groq), sans besoin de carte bancaire.

## Installation

```bash
cd lead_qualifier_chatbot
python -m venv venv
source venv/bin/activate      # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration (gratuite)

1. Créer un compte sur https://console.groq.com (gratuit, pas de CB requise)
2. Aller dans "API Keys" → créer une clé
3. Copier `.env.example` en `.env` et coller votre clé :

```bash
cp .env.example .env
```

Puis éditer `.env` :
```
GROQ_API_KEY=gsk_votre_vraie_cle
GROQ_MODEL=llama-3.3-70b-versatile
```

## Tester rapidement en ligne de commande

```bash
python test_conversation.py
```

Discutez avec le bot comme un client, tapez `quit` à la fin pour voir le
score de qualification calculé.

## Lancer l'API complète

```bash
uvicorn main:app --reload
```

Puis ouvrez http://127.0.0.1:8000/docs pour tester l'API interactivement
(Swagger UI généré automatiquement par FastAPI).

- `POST /chat` → envoyer un message, recevoir la réponse + score en direct
- `GET /leads` → voir tous les leads enregistrés, triés par score

## Structure du projet

```
lead_qualifier_chatbot/
├── main.py                       # API FastAPI, orchestre les agents
├── database.py                   # Base SQLite (sessions, scores, historique)
├── test_conversation.py          # Test en CLI sans interface web
├── agents/
│   ├── conversational_agent.py   # Dialogue naturel avec le visiteur
│   ├── extraction_agent.py       # Extraction JSON structurée
│   └── scoring_agent.py          # Scoring BANT + justification explicable
├── data/                         # Base de données SQLite générée ici
├── requirements.txt
└── .env.example
```

## Comment ça marche (logique des 3 agents)

1. **Agent conversationnel** : reçoit l'historique, répond naturellement en
   essayant subtilement de connaître le besoin du client.
2. **Agent d'extraction** : après chaque échange, relit toute la conversation
   et sort un JSON structuré (produit recherché, budget, délai, contact,
   intention, urgence).
3. **Agent de scoring** : applique une grille de points (méthode BANT) sur
   ce JSON pour calculer un score /100 et une catégorie (chaud/tiède/froid),
   avec une justification explicable ligne par ligne.

Le score se met à jour en temps réel à chaque message, ce qui permet de
suivre l'évolution de la qualification pendant la conversation.

## RAG — recommandation de produits (ajouté)

Le bot peut maintenant chercher dans un vrai catalogue produits et suggérer
des articles pertinents pendant la conversation, grâce à ChromaDB (base
vectorielle 100% locale et gratuite, aucune clé API supplémentaire requise).

### Indexer le catalogue (à faire une fois, avant de tester)

```bash
python scripts/index_catalog.py
```

Cette commande lit `data/products_catalog.json` (10 produits d'exemple :
laptops, smartphones, accessoires) et les indexe dans une base vectorielle
locale stockée dans `data/chroma_db/`.

### Comment ça marche

1. À chaque message du visiteur, le système cherche les produits du
   catalogue les plus proches sémantiquement de sa demande
   (`rag/catalog.py` → `search_products`)
2. Ces produits sont injectés dans le prompt de l'agent conversationnel,
   qui les suggère naturellement s'ils sont pertinents (jamais de liste
   forcée si rien ne correspond)
3. Le premier appel télécharge un petit modèle d'embeddings local
   (all-MiniLM-L6-v2, ~90 Mo, une seule fois) — normal que la première
   requête soit un peu plus lente.

### Adapter à votre entreprise

Remplacez le contenu de `data/products_catalog.json` par le vrai catalogue
(même structure : id, nom, description, prix, categorie), puis relancez
`python scripts/index_catalog.py` pour ré-indexer.

## Widget web + page de démo e-commerce (ajouté)

Une vraie interface web est maintenant disponible : une page de démo boutique
tech avec un widget de chat flottant en bas à droite, connecté en direct à
votre API. Le score de qualification s'affiche en temps réel dans le widget
(petite barre de progression + catégorie chaud/tiède/froid).

### Lancer la démo

```bash
uvicorn main:app --reload
```

Puis ouvrez dans votre navigateur :
```
http://127.0.0.1:8000/static/index.html
```

Cliquez sur la bulle de chat en bas à droite et discutez avec Léa. Le score
se met à jour après chaque message.

### Comment ça marche

- `static/index.html` contient toute la page (HTML/CSS/JS en un seul
  fichier, pas de build nécessaire)
- Le widget appelle `POST /chat` sur votre API à chaque message envoyé
- CORS est activé côté API (`main.py`) pour que le navigateur soit autorisé
  à contacter le serveur
- Chaque visiteur a un `session_id` généré aléatoirement au chargement de
  la page, ce qui permet à l'API de suivre plusieurs conversations en
  parallèle (visible dans `GET /leads`)

### Adapter à votre site

Pour l'intégrer plus tard sur un vrai site e-commerce, il suffit de copier
le bloc `<button id="chat-toggle">`, `<div id="chat-panel">` et le
`<script>` correspondant dans n'importe quelle page HTML existante, et de
changer `API_URL` par l'adresse de votre serveur une fois déployé (ex: une
URL Railway/Render au lieu de `http://127.0.0.1:8000`).

## Dashboard analytique (ajouté)

Une page pour l'équipe commerciale, qui affiche tous les leads récoltés
avec leurs scores, plus des statistiques agrégées.

### Ouvrir le dashboard

Avec le serveur lancé (`uvicorn main:app --reload` ou `python -m uvicorn
main:app --reload`), allez sur :
```
http://127.0.0.1:8000/static/dashboard.html
```

Vous y trouverez :
- Le nombre total de leads, répartis chaud/tiède/froid, et le score moyen
- Les produits les plus demandés (agrégés depuis les conversations)
- Un tableau détaillé de chaque lead (score, produit, budget, contact)

La page se rafraîchit automatiquement toutes les 10 secondes.

## Jeu de tests (ajouté)

`tests/test_scenarios.py` contient 8 scénarios de conversation type
(client pressé, curieux, réclamation, comparateur de prix...) avec une
catégorie attendue pour chacun. Le script fait tourner les agents
d'extraction et de scoring dessus et affiche un taux de cohérence global.

### Lancer les tests

```bash
python tests/test_scenarios.py
```

Ça affiche, pour chaque scénario, le score obtenu, la catégorie, la
justification, et si le résultat correspond à ce qui était attendu — avec
un pourcentage de cohérence global à la fin.

**C'est la pièce la plus importante pour la partie "évaluation" de votre
rapport** : ça transforme "mon chatbot marche" en une preuve chiffrée
et reproductible. Vous pouvez copier le tableau de résultats directement
dans votre rapport, et ajouter vos propres scénarios pour couvrir plus de
cas (ex : plusieurs langues, fautes d'orthographe, messages très courts).

### Itération : du scoring naïf au scoring calibré

Premier passage des tests : **62% de cohérence** (5/8 scénarios corrects).
Les échecs ont révélé deux défauts précis :

1. Le délai d'achat comptait de façon binaire (présent/absent) : "cette
   semaine" et "dans 3 mois" valaient exactement le même nombre de points,
   ce qui faisait mal classer les leads sans urgence réelle.
2. Les budgets vagues ("pas cher", "abordable" sans chiffre) étaient
   traités comme un vrai budget chiffré, gonflant artificiellement le score.

**Corrections apportées** (`agents/scoring_agent.py` v2) :
- Le délai est maintenant pondéré par `niveau_urgence` (haute = 25 pts,
  moyenne = 12 pts, basse = 5 pts, inconnue = 0 pt) au lieu d'un score fixe.
- L'agent d'extraction (`agents/extraction_agent.py`) n'extrait plus de
  budget si aucun chiffre concret n'est mentionné.
- L'intention "comparaison_prix" est mieux valorisée (10 pts) : comparer
  des prix avec un produit précis en tête est un vrai signal commercial.

Relancez `python tests/test_scenarios.py` pour voir le nouveau taux de
cohérence. **Cette itération (avant/après, avec les chiffres) est un
excellent exemple à documenter dans votre rapport** : elle montre une
vraie démarche d'ingénierie pilotée par les tests, pas juste "ça a l'air
de marcher".

## Prochaines étapes pour aller plus loin (à faire progressivement)

1. **Bascule vers un modèle local (Ollama)** si vous voulez montrer une
   solution 100% auto-hébergée (argument confidentialité des données).
2. **Déploiement en ligne** (Render/Railway, gratuit) pour avoir une URL
   publique à montrer à votre encadrante sans lancer le serveur localement.
3. **Authentification simple** sur le dashboard si vous le rendez public
   (mot de passe basique, pour ne pas exposer les leads à tout le monde).

## Notes pour le rapport de stage

- Le scoring est **explicable** (chaque point est justifié) : bon argument
  éthique/transparence à mentionner.
- L'architecture est **modulaire** : chaque agent est un fichier séparé,
  facile à faire évoluer ou remplacer (ex: changer de LLM sans tout casser).
- Tout est **gratuit et sans dépendance à un CRM externe**, adapté à votre
  contexte de stage actuel, avec un chemin clair vers une intégration
  future (RAG, CRM, widget web).
