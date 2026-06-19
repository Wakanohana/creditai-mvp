# CreditAI — Guide de Déploiement (15 minutes, sans coder)

> **Objectif :** obtenir deux vraies URLs publiques à mettre dans vos emails et votre pitch deck :
> - `https://creditai.vercel.app` → votre landing page
> - `https://creditai-api.up.railway.app` → votre API de démo
>
> **Coût : 0 $.** Les deux plateformes ont un plan gratuit suffisant pour un Pre-Seed.

---

## Partie 1 — Déployer la Landing Page sur Vercel (5 min)

### Étape 1.1 — Créer un compte
1. Allez sur **[vercel.com](https://vercel.com)**
2. Cliquez sur **"Sign Up"**
3. Choisissez **"Continue with GitHub"** (le plus simple — créez un compte GitHub gratuit d'abord si vous n'en avez pas, sur [github.com](https://github.com))

### Étape 1.2 — Déployer le fichier HTML
**Option A — Sans GitHub (le plus rapide) :**
1. Sur Vercel, cliquez sur **"Add New" → "Project"**
2. Faites glisser le fichier `CreditAI_LandingPage.html` directement dans la zone "Deploy"
3. Renommez le fichier en `index.html` avant de l'envoyer (important — Vercel cherche ce nom par défaut)
4. Cliquez **Deploy**
5. Vercel vous donne une URL en 30 secondes : `https://creditai-xxxx.vercel.app`

**Option B — Avec GitHub (recommandé si vous comptez itérer) :**
1. Créez un nouveau repository GitHub nommé `creditai-landing`
2. Uploadez le fichier `CreditAI_LandingPage.html` et renommez-le `index.html`
3. Dans Vercel : **"Add New" → "Project"** → sélectionnez ce repository
4. Cliquez **Deploy** (laissez tous les réglages par défaut, Vercel détecte un site statique automatiquement)

### Étape 1.3 — Personnaliser l'URL (optionnel)
Dans Vercel : **Project Settings → Domains** → vous pouvez choisir un sous-domaine du type `creditai-demo.vercel.app`, ou connecter un vrai nom de domaine si vous en achetez un (Namecheap, ~12$/an pour `.com`, ou ~30$/an pour `.ai` — très recherché en FinTech).

✅ **Résultat : votre landing page est en ligne, accessible 24/7, gratuitement.**

---

## Partie 2 — Déployer l'API sur Railway (10 min)

### Étape 2.1 — Créer un compte
1. Allez sur **[railway.app](https://railway.app)**
2. **"Login"** → **"Login with GitHub"**
3. Railway donne 5$ de crédit gratuit/mois — largement suffisant pour une démo Pre-Seed (l'API ne tournera pas en continu à fort trafic)

### Étape 2.2 — Uploader le code
**Vous avez besoin de mettre le code sur GitHub d'abord** (Railway déploie depuis un repo) :
1. Créez un repository GitHub nommé `creditai-mvp`
2. Décompressez `CreditAI_MVP_Source.zip` sur votre ordinateur
3. Uploadez tout le contenu du dossier `creditai-mvp/` dans ce repository
   *(Sur GitHub.com : bouton "Add file" → "Upload files" → glissez tous les fichiers et dossiers)*

### Étape 2.3 — Déployer depuis Railway
1. Dans Railway : **"New Project"** → **"Deploy from GitHub repo"**
2. Sélectionnez `creditai-mvp`
3. Railway détecte automatiquement `requirements.txt` et `Procfile` — il sait que c'est une app Python/FastAPI
4. Cliquez **Deploy** — patientez 2-3 minutes pendant l'installation des dépendances (scikit-learn prend un peu de temps)

### Étape 2.4 — Générer l'URL publique
1. Une fois le déploiement terminé (statut vert ✅), allez dans **Settings → Networking**
2. Cliquez **"Generate Domain"**
3. Railway vous donne une URL : `https://creditai-mvp-production.up.railway.app`

### Étape 2.5 — Vérifier que ça marche
Ouvrez dans votre navigateur :
```
https://votre-url-railway.up.railway.app/health
```
Vous devez voir :
```json
{"status": "healthy", "model_loaded": true, ...}
```

Puis testez la documentation interactive :
```
https://votre-url-railway.up.railway.app/docs
```
Vous verrez l'interface Swagger où vous pouvez tester `/score/demo` directement dans le navigateur, sans aucune ligne de code.

✅ **Résultat : votre API tourne en production, avec documentation interactive incluse.**

---

## Partie 3 — Connecter la Landing Page à la vraie API (2 min)

1. Ouvrez `CreditAI_LandingPage.html` dans un éditeur de texte simple (Notepad, TextEdit, ou VS Code)
2. Cherchez cette ligne (vers le début du `<script>`) :
   ```javascript
   const API_BASE_URL = "";
   ```
3. Remplacez par votre URL Railway :
   ```javascript
   const API_BASE_URL = "https://creditai-mvp-production.up.railway.app";
   ```
4. Re-uploadez ce fichier modifié sur Vercel (même procédure que l'étape 1.2)

*(Note : la version actuelle du simulateur tourne déjà en JavaScript pur dans le navigateur — donc même sans cette connexion, la démo visuelle fonctionne. Cette étape est utile si vous voulez prouver que l'API réelle répond, par exemple pour un investisseur technique qui veut tester `/docs` lui-même.)*

---

## Ce que vous pouvez dire dans vos emails à partir de maintenant

> *"Demo live: https://creditai.vercel.app*
> *API docs: https://creditai-mvp-production.up.railway.app/docs"*

C'est exactement le type de lien que Charles Hudson (Precursor) ou Michael Vaughan (Vera Equity) s'attendent à recevoir dans un cold email Pre-Seed.

---

## Limites à connaître (pour rester honnête avec les investisseurs)

- **Le modèle ML est entraîné sur des données synthétiques**, pas sur de vraies données bancaires. C'est normal et attendu à ce stade — dites-le si on vous le demande, ne le cachez pas. La phrase qui fonctionne : *"Le modèle actuel valide notre architecture technique ; nous le réentraînerons sur des données réelles dès nos premiers pilotes."*
- **Railway free tier peut se mettre en veille après inactivité** — si un investisseur teste le lien après plusieurs heures sans trafic, le premier appel peut prendre 10-15 secondes (cold start). C'est normal, ne paniquez pas.
- **Aucune authentification sur l'API actuellement** — ne mettez jamais de vraies données bancaires clients dessus tant que ce n'est pas sécurisé (HTTPS suffit pour une démo, mais pas pour de la production).

---

## Prochaine étape une fois en ligne

Une fois les deux URLs actives, revenez me voir : je peux vous aider à les intégrer proprement dans le Pitch Deck, le One Pager, et les emails d'outreach (remplacer les mentions textuelles par de vrais liens cliquables).
