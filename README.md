# GestFichier — Système de gestion de fichiers d'entreprise

Logiciel professionnel sous Django pour le stockage, la gestion et le partage de fichiers en entreprise (inspiré de OneDrive Business / Dropbox Business).

**Langue de l'interface : Français** (structure i18n prête pour d'autres langues).

## Fonctionnalités principales

- **Rôles utilisateurs** : Administrateur technique, Administrateur d'entreprise, Manager de département, Employé
- **Gestion de fichiers et dossiers** : téléversement (drag & drop), téléchargement, création de dossiers, renommage, suppression douce (corbeille), restauration
- **Partage externe** : liens avec mot de passe, date d'expiration, limite de téléchargements
- **Permissions granulaires** côté serveur
- **Quota de stockage** par utilisateur
- **Journal d'activité**
- **Interface moderne Bootstrap 5**, responsive
- **Déploiement Docker** (PostgreSQL + Gunicorn)

## Stack technique

| Composant        | Technologie          |
|------------------|----------------------|
| Backend          | Python / Django 5+   |
| Base de données  | PostgreSQL           |
| Frontend         | HTML5, CSS3, JS, Bootstrap 5 |
| Serveur WSGI     | Gunicorn             |
| Fichiers statiques | WhiteNoise         |
| Conteneurisation | Docker + Compose     |

## Installation rapide avec Docker

```bash
# Cloner le dépôt
git clone <url-du-repo>
cd gestfichier

# Lancer
docker compose up --build -d

# Créer les données de démonstration
docker compose exec web python manage.py create_demo_data

# Accéder à l'application
# http://localhost:8000
```

### Comptes de démonstration

| Rôle                    | E-mail                     | Mot de passe |
|-------------------------|----------------------------|--------------|
| Admin technique         | admin@entreprise.fr        | admin1234    |
| Admin entreprise        | directeur@entreprise.fr    | demo1234     |
| Manager                 | manager@entreprise.fr      | demo1234     |
| Employé                 | employe@entreprise.fr      | demo1234     |

## Installation locale (sans Docker)

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Utiliser SQLite pour le développement
export USE_SQLITE=1
export SECRET_KEY=dev-secret-key

python manage.py migrate
python manage.py create_demo_data
python manage.py runserver
```

## Variables d'environnement

Voir `.env.example`. Principales variables :

- `SECRET_KEY` — clé secrète Django
- `DEBUG` — True/False
- `DB_*` — paramètres PostgreSQL
- `USE_SQLITE=1` — forcer SQLite (dev)

## Structure du projet

```
gestfichier/
├── accounts/          # Utilisateurs, authentification, rôles
├── companies/         # Entreprises, départements, groupes
├── files/             # Dossiers, fichiers, versions, permissions
├── shares/            # Liens de partage externes
├── activity/          # Journal des activités
├── config/            # Settings, urls, wsgi
├── templates/         # Templates HTML (français)
├── static/            # CSS / JS
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Déploiement sur Render.com

1. Créer un **Web Service** et connecter le dépôt GitHub.
2. **Environment** : Docker
3. Ajouter une base **PostgreSQL** (Render) et renseigner les variables `DB_*`.
4. Variables recommandées :
   - `SECRET_KEY` = (générer une clé)
   - `DEBUG` = False
   - `ALLOWED_HOSTS` = .onrender.com
5. Le `CMD` du Dockerfile lance Gunicorn. Les migrations peuvent être exécutées via un **Release Command** :  
   `python manage.py migrate --noinput`
6. **Note** : le stockage des fichiers (`media/`) est éphémère sur le plan gratuit. Pour la production, utiliser un stockage objet (S3, etc.) ou un disque persistant.

## Commandes utiles

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py create_demo_data
python manage.py collectstatic
python manage.py makemessages -l fr
python manage.py compilemessages
```

## Sécurité

- Mots de passe hashés (Django)
- Protection CSRF, XSS (middleware Django)
- Vérification des permissions côté serveur
- Limitation des tentatives de connexion
- Fichiers servis via l'application (pas d'accès direct non contrôlé)

## Auteur / Projet universitaire

Projet de gestion de fichiers d'entreprise — 2026.

Licence : usage éducatif.
