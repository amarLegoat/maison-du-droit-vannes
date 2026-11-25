# Solution Décisionnelle Open Source & Cloud — Maison du Droit de Vannes (SAÉ 5.VCOD.01)

## Architecture recommandée pour le client (100 % gratuite, open-source, multi-postes simultané & durable)
1. **Base de données SGBDR Client-Serveur :** **PostgreSQL** (open-source, verrouillage au niveau ligne permettant la saisie simultanée sur les 2 ordinateurs sans conflit Dropbox) hébergée gratuitement sur **Supabase** (500 Mo gratuits permanents, sauvegardes quotidiennes automatiques, pas d'effacement l'été) ou **Alwaysdata** (hébergeur français).
2. **Application Web (Saisie + ETL + Dataviz + AFC + Export Excel) :** **Python / Streamlit** (open-source) déployée gratuitement sur **Streamlit Community Cloud** (sur un compte GitHub appartenant à l'association pour garantir la pérennité après le projet) ou sur **Alwaysdata**.
3. **Compatibilité locale / POC IUT :** Si aucune URL `DATABASE_URL` PostgreSQL n'est fournie, le code bascule automatiquement sur SQLite local (`maison_droit.db`).

## Déploiement Cloud Gratuit (10 minutes)
1. Créer un projet gratuit sur **Supabase** (ou **Neon.tech** / **Alwaysdata**) et copier l'URI PostgreSQL (`postgresql://postgres:...@...:5432/postgres`).
2. Pousser ce dossier sur un dépôt GitHub de l'association.
3. Déployer `app.py` sur **Streamlit Community Cloud** en ajoutant `DATABASE_URL = "postgresql://..."` dans *Settings -> Secrets*.
4. Importer le fichier Excel 2024 depuis l'onglet **📂 Pipeline ETL & Import Excel** de l'application web.

## Lancement local (IUT / hors-ligne)
```bash
pip install -r requirements.txt
python etl_pipeline.py "24 12 Mais.Droit STATS 2024.xlsx"
streamlit run app.py
```
