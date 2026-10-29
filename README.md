# Rappel Vocal

Application Django de rappels pour le bureau Linux. À l'heure prévue, chaque rappel :

- affiche une **notification système** (`notify-send`) avec un son ;
- **lit le message à voix haute** en français avec [Piper](https://github.com/rhasspy/piper), entièrement hors ligne.

Les rappels peuvent être uniques, quotidiens ou hebdomadaires. Une petite API JSON permet de les piloter depuis [n8n](https://n8n.io) ou tout autre outil.

## Prérequis

| Outil | Rôle | Installation (Debian / Ubuntu / Pop!_OS) |
|---|---|---|
| Python 3.10+ | Application | `sudo apt install python3 python3-venv` |
| MySQL ou MariaDB | Base de données (SQLite possible, voir plus bas) | `sudo apt install mariadb-server libmysqlclient-dev pkg-config` |
| `notify-send` | Notification bureau | `sudo apt install libnotify-bin` |
| `paplay`, `aplay` | Son et voix | `sudo apt install pulseaudio-utils alsa-utils` |
| Piper + un modèle français | Synthèse vocale | voir ci-dessous |

### Modèle de voix Piper

```bash
mkdir -p ~/piper-models && cd ~/piper-models
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/upmc/medium/fr_FR-upmc-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/upmc/medium/fr_FR-upmc-medium.onnx.json
```

Vérification : `echo "Bonjour" | piper --model ~/piper-models/fr_FR-upmc-medium.onnx --output_raw | aplay -r 22050 -f S16_LE -t raw -`

## Installation

```bash
git clone <ce-dépôt> rappell && cd rappell
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Créer la base MySQL (une seule fois) :

```sql
CREATE DATABASE rappel_vocal CHARACTER SET utf8mb4;
CREATE USER 'admin'@'localhost' IDENTIFIED BY 'motdepasse123';
GRANT ALL ON rappel_vocal.* TO 'admin'@'localhost';
```

Puis :

```bash
python manage.py migrate
python manage.py createsuperuser   # facultatif, pour /admin/
python manage.py runserver
```

L'interface est disponible sur <http://localhost:8000>.

> Pour essayer sans MySQL : `export DB_ENGINE=sqlite` avant les commandes ci-dessus (base `db.sqlite3` dans le projet).

## Configuration

Tout se règle par variables d'environnement ; les valeurs par défaut conviennent pour un usage local.

| Variable | Défaut | Description |
|---|---|---|
| `DB_ENGINE` | `mysql` | `sqlite` pour utiliser SQLite |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | `rappel_vocal`, `admin`, `motdepasse123`, `localhost`, `3306` | Connexion MySQL |
| `PIPER_MODEL` | `~/piper-models/fr_FR-upmc-medium.onnx` | Modèle de voix |
| `RAPPEL_SCHEDULER` | `1` | `0` pour désactiver le planificateur intégré (si n8n déclenche les rappels) |
| `RAPPEL_API_TOKEN` | *(vide)* | Si défini, l'API exige `Authorization: Bearer <jeton>` |
| `N8N_URL` | `http://localhost:5678` | Lien affiché dans les paramètres |
| `DJANGO_SECRET_KEY` | clé de développement | **À changer** hors usage local |
| `DJANGO_DEBUG` | `1` | `0` en production |

## Fonctionnement

Un planificateur APScheduler démarre avec le serveur et vérifie **chaque minute** les rappels actifs arrivés à échéance :

- rappel **unique** : joué puis désactivé ;
- rappel **quotidien / hebdomadaire** : joué puis reprogrammé à sa prochaine occurrence future. Si le PC était éteint pendant plusieurs occurrences, le rappel n'est joué qu'une fois au redémarrage.

Chaque déclenchement (réussi ou en erreur) est enregistré dans l'**historique**. Le bouton ▶ d'un rappel le joue immédiatement sans changer sa planification.

Le planificateur ne démarre pas pendant `migrate`, `shell` ou `test`. Sous `runserver`, il tourne uniquement dans le processus servi (pas en double à cause du rechargement automatique).

> Les notifications et la voix sont émises par le processus Django : il doit tourner dans votre session graphique (pas en service système sans accès à l'écran et au son).

## API (n8n)

Les deux endpoints acceptent du JSON et ne demandent pas de jeton CSRF.

### `GET /api/rappels/`

Liste les rappels actifs arrivés à échéance et pas encore déclenchés.

### `POST /api/rappels/`

Crée un rappel.

```json
{
  "titre": "Réunion",
  "message": "Point d'équipe dans 5 minutes",
  "heure_rappel": "2026-11-02T09:55",
  "frequence": "once",
  "vocal": true,
  "notif_bureau": true
}
```

`heure_rappel` sans fuseau est interprétée dans le fuseau du projet (`Africa/Douala`). `frequence` vaut `once`, `daily` ou `weekly`. Réponse : `201 {"id": 12, "status": "créé"}`.

### `POST /api/notifier/`

- Avec `{"id": 12}` : déclenche ce rappel exactement comme le planificateur (historique + reprogrammation).
- Sans `id` : notification ponctuelle, ex. `{"titre": "Build terminé", "message": "Tout est vert"}`.

Exemple avec jeton :

```bash
curl -X POST http://localhost:8000/api/notifier/ \
  -H "Authorization: Bearer $RAPPEL_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"titre": "Test", "message": "Bonjour"}'
```

> Si n8n interroge `GET /api/rappels/` puis appelle `/api/notifier/`, lancez Django avec `RAPPEL_SCHEDULER=0` pour éviter que chaque rappel soit joué deux fois.

## Structure

```
config/                 Réglages Django
reminders/
  models.py             Rappel, HistoriqueNotification, logique de déclenchement
  scheduler.py          Vérification périodique (APScheduler)
  views.py              Pages web et API
  services/tts.py       Synthèse vocale Piper → aplay
  services/notifier.py  notify-send + son
templates/              Gabarits HTML
static/css/             Icônes Tabler (locales, aucun CDN)
```

## Tests

```bash
DB_ENGINE=sqlite python manage.py test reminders
```
