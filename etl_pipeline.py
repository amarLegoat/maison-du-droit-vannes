import argparse
import json
import os
import re
import sys
import pandas as pd
from openpyxl.utils import get_column_letter

from db_adapter import UniversalDB, resolve_db_url, resolve_supabase_key

RULES_PATH = "regles_nettoyage.json"
AUDIT_XLSX_PATH = "Rapport_Qualite_ETL.xlsx"
PG_DDL_PATH = "maison_droit_postgresql.sql"

CONTEXT_COLS = [
    'N°', 'Mode', 'Durée', 'Sexe', 'Age', 'Vient pr', 'Sit° Fam', 'Enfts',
    'Modèle fam.', 'Prof°', 'Ress. 1', 'Dem.1', 'Dem.2', 'Dem.3',
    'Sol.1', 'Sol.2', 'Sol.3', 'Origine', 'Domicile', 'Partenaire'
]

SQLITE_DDL_SCHEMA = """
CREATE TABLE IF NOT EXISTS mode_entretien (
    code_mode VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_mode VARCHAR(50) NOT NULL
);
CREATE TABLE IF NOT EXISTS duree (
    code_duree VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_duree VARCHAR(50) NOT NULL
);
CREATE TABLE IF NOT EXISTS sexe (
    code_sexe VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_sexe VARCHAR(50) NOT NULL
);
CREATE TABLE IF NOT EXISTS tranche_age (
    code_age VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_age VARCHAR(50) NOT NULL
);
CREATE TABLE IF NOT EXISTS vient_pour (
    code_vient_pour VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_vient_pour VARCHAR(50) NOT NULL
);
CREATE TABLE IF NOT EXISTS situation_familiale (
    code_sit_fam VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_sit_fam VARCHAR(100) NOT NULL
);
CREATE TABLE IF NOT EXISTS modele_familial (
    code_modele_fam VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_modele_fam VARCHAR(50) NOT NULL
);
CREATE TABLE IF NOT EXISTS profession (
    code_prof VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_prof VARCHAR(100) NOT NULL
);
CREATE TABLE IF NOT EXISTS ressource (
    code_ressource VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_ressource VARCHAR(100) NOT NULL
);
CREATE TABLE IF NOT EXISTS lieu_permanence (
    id_lieu INTEGER PRIMARY KEY AUTOINCREMENT,
    nom_lieu VARCHAR(100) NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS partenaire (
    id_partenaire INTEGER PRIMARY KEY AUTOINCREMENT,
    nom_partenaire VARCHAR(100) NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS categorie_origine (
    code_cat_origine VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_cat_origine VARCHAR(100) NOT NULL
);
CREATE TABLE IF NOT EXISTS origine_contact (
    code_origine VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_origine VARCHAR(100) NOT NULL,
    code_cat_origine VARCHAR(10) NOT NULL,
    FOREIGN KEY (code_cat_origine) REFERENCES categorie_origine(code_cat_origine)
);
CREATE TABLE IF NOT EXISTS epci (
    id_epci INTEGER PRIMARY KEY AUTOINCREMENT,
    nom_epci VARCHAR(100) NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS commune (
    id_commune INTEGER PRIMARY KEY AUTOINCREMENT,
    code_insee VARCHAR(10),
    nom_commune VARCHAR(100) NOT NULL UNIQUE,
    departement VARCHAR(10),
    id_epci INTEGER,
    FOREIGN KEY (id_epci) REFERENCES epci(id_epci)
);
CREATE TABLE IF NOT EXISTS quartier (
    id_quartier INTEGER PRIMARY KEY AUTOINCREMENT,
    code_quartier VARCHAR(20) NOT NULL UNIQUE,
    nom_quartier VARCHAR(100) NOT NULL,
    est_qpv SMALLINT NOT NULL DEFAULT 0,
    id_commune INTEGER NOT NULL,
    FOREIGN KEY (id_commune) REFERENCES commune(id_commune)
);
CREATE TABLE IF NOT EXISTS domaine_droit (
    code_domaine VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_domaine VARCHAR(100) NOT NULL
);
CREATE TABLE IF NOT EXISTS nature_demande (
    code_demande VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_demande VARCHAR(100) NOT NULL,
    code_domaine VARCHAR(10) NOT NULL,
    FOREIGN KEY (code_domaine) REFERENCES domaine_droit(code_domaine)
);
CREATE TABLE IF NOT EXISTS categorie_reponse (
    code_cat_reponse VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_cat_reponse VARCHAR(100) NOT NULL
);
CREATE TABLE IF NOT EXISTS type_reponse (
    code_reponse VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_reponse VARCHAR(100) NOT NULL,
    code_cat_reponse VARCHAR(10) NOT NULL,
    FOREIGN KEY (code_cat_reponse) REFERENCES categorie_reponse(code_cat_reponse)
);
CREATE TABLE IF NOT EXISTS entretien (
    id_entretien INTEGER PRIMARY KEY AUTOINCREMENT,
    num_fiche_annuel INTEGER,
    date_entretien DATE,
    annee INTEGER,
    mois INTEGER,
    date_estimee SMALLINT DEFAULT 1,
    nb_enfants_charge INTEGER,
    code_mode VARCHAR(10),
    code_duree VARCHAR(10),
    code_sexe VARCHAR(10),
    code_age VARCHAR(10),
    code_vient_pour VARCHAR(10),
    code_sit_fam VARCHAR(10),
    code_modele_fam VARCHAR(10),
    code_prof VARCHAR(10),
    code_ressource VARCHAR(10),
    code_origine VARCHAR(10),
    id_commune INTEGER,
    id_quartier INTEGER,
    id_lieu INTEGER,
    id_partenaire INTEGER,
    FOREIGN KEY (code_mode) REFERENCES mode_entretien(code_mode),
    FOREIGN KEY (code_duree) REFERENCES duree(code_duree),
    FOREIGN KEY (code_sexe) REFERENCES sexe(code_sexe),
    FOREIGN KEY (code_age) REFERENCES tranche_age(code_age),
    FOREIGN KEY (code_vient_pour) REFERENCES vient_pour(code_vient_pour),
    FOREIGN KEY (code_sit_fam) REFERENCES situation_familiale(code_sit_fam),
    FOREIGN KEY (code_modele_fam) REFERENCES modele_familial(code_modele_fam),
    FOREIGN KEY (code_prof) REFERENCES profession(code_prof),
    FOREIGN KEY (code_ressource) REFERENCES ressource(code_ressource),
    FOREIGN KEY (code_origine) REFERENCES origine_contact(code_origine),
    FOREIGN KEY (id_commune) REFERENCES commune(id_commune),
    FOREIGN KEY (id_quartier) REFERENCES quartier(id_quartier),
    FOREIGN KEY (id_lieu) REFERENCES lieu_permanence(id_lieu),
    FOREIGN KEY (id_partenaire) REFERENCES partenaire(id_partenaire)
);
CREATE TABLE IF NOT EXISTS concerner (
    id_entretien INTEGER NOT NULL,
    code_demande VARCHAR(10) NOT NULL,
    ordre_demande INTEGER NOT NULL,
    PRIMARY KEY (id_entretien, code_demande),
    FOREIGN KEY (id_entretien) REFERENCES entretien(id_entretien) ON DELETE CASCADE,
    FOREIGN KEY (code_demande) REFERENCES nature_demande(code_demande)
);
CREATE TABLE IF NOT EXISTS apporter (
    id_entretien INTEGER NOT NULL,
    code_reponse VARCHAR(10) NOT NULL,
    ordre_reponse INTEGER NOT NULL,
    PRIMARY KEY (id_entretien, code_reponse),
    FOREIGN KEY (id_entretien) REFERENCES entretien(id_entretien) ON DELETE CASCADE,
    FOREIGN KEY (code_reponse) REFERENCES type_reponse(code_reponse)
);
CREATE TABLE IF NOT EXISTS anomalie_import (
    id_anomalie INTEGER PRIMARY KEY AUTOINCREMENT,
    annee INTEGER,
    onglet VARCHAR(30),
    ligne_excel INTEGER,
    cellule_excel VARCHAR(15),
    num_fiche INTEGER,
    colonne VARCHAR(50),
    valeur_brute VARCHAR(200),
    commentaire TEXT,
    type_anomalie VARCHAR(100),
    action_prise VARCHAR(200),
    statut VARCHAR(30) DEFAULT 'A_VERIFIER_CLIENT'
);
"""

NOMENCLATURES_DATA = {
    "mode_entretien": (
        "code_mode",
        [{"code_mode": c, "libelle_mode": l} for c, l in [
            ('1', 'RDV'), ('2', 'Sans RDV'), ('3', 'Téléphonique'), ('4', 'Courrier'), ('5', 'Mail')
        ]]
    ),
    "duree": (
        "code_duree",
        [{"code_duree": c, "libelle_duree": l} for c, l in [
            ('1', '- 15 min'), ('2', '15 à 30 min'), ('3', '30 à 45 min'), ('4', '45 à 60 min'), ('5', '+ de 60 min')
        ]]
    ),
    "sexe": (
        "code_sexe",
        [{"code_sexe": c, "libelle_sexe": l} for c, l in [
            ('1', 'Homme'), ('2', 'Femme'), ('3', 'Couple'), ('4', 'Professionnel')
        ]]
    ),
    "tranche_age": (
        "code_age",
        [{"code_age": c, "libelle_age": l} for c, l in [
            ('1', '- 18 ans'), ('2', '18-25 ans'), ('3', '26-40 ans'), ('4', '41-60 ans'), ('5', '+ 60 ans'), ('nc', 'Non renseigné')
        ]]
    ),
    "vient_pour": (
        "code_vient_pour",
        [{"code_vient_pour": c, "libelle_vient_pour": l} for c, l in [
            ('1', 'Soi'), ('2', 'Conjoint'), ('3', 'Parent'), ('4', 'Enfant'), ('5', 'Personne morale'), ('6', 'Autre'), ('7', 'Non renseigné')
        ]]
    ),
    "situation_familiale": (
        "code_sit_fam",
        [{"code_sit_fam": c, "libelle_sit_fam": l} for c, l in [
            ('1', 'Célibataire'), ('2', 'Concubin'), ('3', 'Pacsé'), ('4', 'Marié'),
            ('5', 'Séparé/divorcé (précision non indiquée)'),
            ('5a', 'Séparé/divorcé - Sans enf. à charge'),
            ('5b', 'Séparé/divorcé - Avec enf. en garde alternée'),
            ('5c', 'Séparé/divorcé - Avec enf. en garde principale'),
            ('5d', 'Séparé/divorcé - Avec enf. en droit de visite/hbgt'),
            ('5e', 'Séparé/divorcé - Parent isolé'),
            ('5f', 'Séparés sous le même toit'),
            ('6a', 'Veuf/ve - Sans enf. à charge'),
            ('6b', 'Veuf/ve - Avec enf. à charge'),
            ('7', 'Non renseigné')
        ]]
    ),
    "modele_familial": (
        "code_modele_fam",
        [{"code_modele_fam": c, "libelle_modele_fam": l} for c, l in [
            ('1', 'Famille traditionnelle'), ('2', 'Famille monoparentale'), ('3', 'Famille recomposée'), ('0', 'Non applicable / Sans enfant')
        ]]
    ),
    "profession": (
        "code_prof",
        [{"code_prof": c, "libelle_prof": l} for c, l in [
            ('1', 'Scolaire / étudiant / formation'), ('2', 'Pêcheur / agriculteur'), ('3', "Chef d'entreprise"),
            ('4', 'Libéral'), ('5', 'Secteur santé / social'), ('6', 'Employé'), ('7', 'Ouvrier'),
            ('8', 'Cadre'), ('9', 'Retraité'), ('10', "En recherche d'emploi"), ('11', 'Sans profession'), ('12', 'Non renseigné')
        ]]
    ),
    "ressource": (
        "code_ressource",
        [{"code_ressource": c, "libelle_ressource": l} for c, l in [
            ('1', 'Salaire'), ('2', 'Revenus pro.'), ('3', 'Retraite / réversion'), ('4', 'Allocations chômage'),
            ('5', 'RSA'), ('6', 'AAH / invalidité'), ('7', 'IJSS'), ('8', "Bourse d'études"),
            ('9', 'Sans revenu'), ('10', 'Autre'), ('11', 'Non renseigné')
        ]]
    ),
    "lieu_permanence": (
        "nom_lieu",
        [{"nom_lieu": n} for n in ('Maison du Droit Vannes', 'PJ AQTA', 'PJ Questembert')]
    ),
    "partenaire": (
        "nom_partenaire",
        [{"nom_partenaire": n} for n in ('Avocat', 'Avocat mineur', 'Conciliateur de justice', 'Notaire', 'Défenseur des Droits')]
    ),
    "categorie_origine": (
        "code_cat_origine",
        [{"code_cat_origine": c, "libelle_cat_origine": l} for c, l in [
            ('1', 'Communication'), ('2', 'Déjà venu'), ('3', 'Par un professionnel du droit'),
            ('4', 'Par une administration'), ('5', 'Secteur santé / social'), ('6', 'Par une association'),
            ('7', 'Organismes privés'), ('8', 'Action collective'), ('9', '3949 (NUAD)')
        ]]
    ),
    "origine_contact": (
        "code_origine",
        [{"code_origine": c, "libelle_origine": l, "code_cat_origine": cat} for c, l, cat in [
            ('1a', 'Bouche à oreille', '1'), ('1b', 'Internet', '1'), ('1c', 'Presse', '1'),
            ('2a', 'Déjà venu - Suite problématique', '2'), ('2b', 'Déjà venu - Autre problématique', '2'),
            ('3a', 'Tribunaux', '3'), ('3b', 'Police / gendarmerie', '3'), ('3c', 'Professionnel du droit', '3'),
            ('4a', 'CAF', '4'), ('4b', 'DIRECCTE / DDETS', '4'), ('4c', 'Maison France Services', '4'),
            ('4d', 'Mairie / EPCI', '4'), ('4e', 'Autre administration', '4'), ('4f', 'Autre administration (4f)', '4'),
            ('5a', 'Assistante sociale', '5'), ('5b', 'Éducateur / autre travailleur social', '5'),
            ('5c', 'Professionnel de santé', '5'), ('5d', 'Professionnel jeunesse', '5'), ('5e', 'RIPAM', '5'), ('5f', 'Autre santé / social', '5'),
            ('6a', 'France Victimes', '6'), ('6b', 'Associations de consommateurs', '6'), ('6c', 'ADIL', '6'),
            ('6d', 'UDAF', '6'), ('6e', "Association d'accès au droit", '6'), ('6f', 'Autre association', '6'),
            ('7a', 'Protection juridique', '7'), ('7b', 'Autre organisme privé', '7'),
            ('8', 'Action collective', '8'),
            ('9', '3949 (NUAD)', '9'), ('9a', '3949 / NUAD (9a)', '9'), ('9b', 'Autre dispositif national (9b)', '9')
        ]]
    ),
    "domaine_droit": (
        "code_domaine",
        [{"code_domaine": c, "libelle_domaine": l} for c, l in [
            ('1', 'Droit de la famille / des personnes'),
            ('2', 'Droit du logement'),
            ('3', 'Droit de la consommation'),
            ('4', 'Autres domaines du droit civil'),
            ('5', 'Droit du travail / affaires / associations'),
            ('6', 'Droit de la protection sociale'),
            ('7', 'Droit pénal'),
            ('8', 'Droit administratif'),
            ('9', 'Démarches et formalités')
        ]]
    ),
    "nature_demande": (
        "code_demande",
        [{"code_demande": c, "libelle_demande": l, "code_domaine": dom} for c, l, dom in [
            ('1a', 'Union', '1'), ('1b', 'Séparation / divorce', '1'), ('1c', 'PA / PC', '1'),
            ('1d', 'Droit de garde', '1'), ('1e', 'Autorité parentale', '1'), ('1f', 'Filiation / adoption', '1'),
            ('1g', 'Régimes matrimoniaux', '1'), ('1h', 'Protection des majeurs', '1'), ('1i', 'État civil', '1'),
            ('1j', 'Successions', '1'), ('1k', 'Assistance éducative', '1'),
            ('2a', 'Litiges locatifs', '2'), ('2b', 'Expulsion', '2'), ('2c', "Achat / vente d'un bien", '2'),
            ('2d', 'Copropriété', '2'), ('2e', 'Droit des biens', '2'), ('2f', 'Construction / urbanisme', '2'),
            ('2g', 'Conflit de voisinage', '2'), ('2h', 'Autre logement', '2'),
            ('3a', 'Crédit / reconnaissance de dette', '3'), ('3b', 'Téléphonie / internet', '3'),
            ('3c', 'Prestation de service', '3'), ('3d', 'Banque / Assurance', '3'),
            ('3e', 'Surendettement', '3'), ('3f', 'Autre consommation', '3'),
            ('4a', 'Responsabilité', '4'), ('4b', "Voies d'exécution", '4'), ('4c', 'Procédure civile', '4'),
            ('4d', 'Erreur médicale', '4'), ('4e', 'Accident VTM', '4'), ('4f', 'Autre droit civil', '4'), ('4g', 'Autre droit civil (4g)', '4'),
            ('5a', 'Exécution du contrat de travail', '5'), ('5b', 'Rupture du contrat de travail', '5'),
            ('5c', 'Droit des affaires / sociétés', '5'), ('5d', 'Droit associatif', '5'), ('5e', 'Autre droit du travail / affaires', '5'),
            ('6a', 'Aides sociales', '6'), ('6b', 'Sécurité sociale', '6'), ('6c', 'Retraite', '6'),
            ('6d', 'Cotisations sociales', '6'), ('6e', 'Autre protection sociale', '6'),
            ('7a', 'Auteur / mis en cause', '7'), ('7b', 'Victime', '7'), ('7c', 'Violences faites aux femmes', '7'),
            ('7d', 'Discriminations', '7'), ('7e', 'Procédure pénale', '7'), ('7f', 'Autre droit pénal', '7'),
            ('8a', 'Litige avec une administration', '8'), ('8b', 'Statuts de la fonction publique', '8'),
            ('8c', 'Droit des étrangers', '8'), ('8d', 'Autre droit administratif', '8'),
            ('9a', 'Terminologie juridique', '9'), ('9b', 'Aide juridictionnelle', '9'), ('9c', 'Autre démarche / formalité', '9')
        ]]
    ),
    "categorie_reponse": (
        "code_cat_reponse",
        [{"code_cat_reponse": c, "libelle_cat_reponse": l} for c, l in [
            ('1', 'Information'), ('2', 'Aide aux démarches'), ('3', 'Aide à la rédaction'),
            ('4', 'Orientation professionnel du droit'), ('5', 'Orientation MARD'),
            ('6', 'Orientation administration'), ('7', 'Orientation association'),
            ('8', 'Orientation santé / social'), ('9', 'Orientation organisme privé')
        ]]
    ),
    "type_reponse": (
        "code_reponse",
        [{"code_reponse": c, "libelle_reponse": l, "code_cat_reponse": cat} for c, l, cat in [
            ('1', 'Information', '1'),
            ('2a', 'Saisine justice internet', '2'), ('2b', 'Aide CAF (ASF)', '2'), ('2c', 'Autre démarche', '2'),
            ('3a', 'Courrier', '3'), ('3b', 'Requête', '3'), ('3c', 'Autre rédaction', '3'),
            ('4a', 'Avocat', '4'), ('4b', 'Avocat mineur', '4'), ('4c', 'Notaire', '4'),
            ('4d', 'Huissier / Commissaire de justice', '4'), ('4e', 'Tribunal', '4'),
            ('4f', 'Police / gendarmerie', '4'), ('4g', 'Autre professionnel du droit', '4'),
            ('5a', 'Conciliateur de justice', '5'), ('5b', 'Délégué du Défenseur des Droits', '5'),
            ('5c', 'Médiation familiale', '5'), ('5d', 'Médiation administrative', '5'),
            ('5e', 'Médiation consommation', '5'), ('5f', 'Médiation banque / assurance', '5'),
            ('6a', 'Mairie / EPCI', '6'), ('6b', 'DIRECCTE / DDETS', '6'), ('6c', 'CAF', '6'),
            ('6d', 'Maison France Services', '6'), ('6e', 'Préfecture', '6'), ('6f', 'Impôts', '6'), ('6g', 'Autre administration', '6'),
            ('7a', 'Aide aux victimes', '7'), ('7b', 'Accès au Droit', '7'), ('7c', 'ADIL', '7'),
            ('7d', 'Association de consommateurs', '7'), ('7e', 'Autre association', '7'),
            ('8a', 'Travailleur social', '8'), ('8b', 'Professionnel de santé', '8'),
            ('8c', 'Professionnel jeunesse', '8'), ('8d', 'Autre santé / social', '8'),
            ('9a', 'Protection juridique', '9'), ('9b', 'Autre organisme privé', '9')
        ]]
    ),
}


def load_rules(rules_path=RULES_PATH):
    if os.path.exists(rules_path):
        with open(rules_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "epci_communes": {},
        "quartiers_qpv_vannes": {},
        "normalisation_orthographe_communes": {},
        "communes_56_autres": [],
        "departements_hors_56": {},
        "corrections_syntaxiques_strictes": {"demande": {}, "reponse": {}, "origine": {}},
    }


def init_schema_and_nomenclatures(db: UniversalDB):
    """Initialise les référentiels (et les tables si SQLite/PostgreSQL direct)."""
    if db.is_https_supabase:
        for tbl, (conflict_col, rows) in NOMENCLATURES_DATA.items():
            db.https.insert_ignore_conflict(tbl, rows, on_conflict=conflict_col)
        epcis = [
            'GMVA (Golfe du Morbihan - Vannes Agglomération)',
            'AQTA (Auray Quiberon Terre Atlantique)',
            'Questembert Communauté',
            'Arc Sud Bretagne',
            'Autres communes du Morbihan (56)',
            'Hors Morbihan (Hors 56)'
        ]
        db.https.insert_ignore_conflict("epci", [{"nom_epci": e} for e in epcis], on_conflict="nom_epci")
        epci_rows = db.https.select_all("epci")
        gmva_id = next((r["id_epci"] for r in epci_rows if "GMVA" in r.get("nom_epci", "")), None)
        db.https.insert_ignore_conflict(
            "commune",
            [{"nom_commune": "Vannes", "departement": "56", "id_epci": gmva_id}],
            on_conflict="nom_commune"
        )
        com_rows = db.https.select_all("commune")
        vannes_id = next((r["id_commune"] for r in com_rows if r.get("nom_commune") == "Vannes"), None)
        if vannes_id is not None:
            db.https.insert_ignore_conflict(
                "quartier",
                [
                    {"code_quartier": "Vannes M", "nom_quartier": "Ménimur (QPV)", "est_qpv": 1, "id_commune": vannes_id},
                    {"code_quartier": "Vannes K", "nom_quartier": "Kercado (QPV)", "est_qpv": 1, "id_commune": vannes_id},
                    {"code_quartier": "Vannes B", "nom_quartier": "Bourdonnaye (QPV)", "est_qpv": 1, "id_commune": vannes_id},
                ],
                on_conflict="code_quartier"
            )
        return

    if db.is_postgres:
        if os.path.exists(PG_DDL_PATH):
            with open(PG_DDL_PATH, "r", encoding="utf-8") as f:
                pg_script = f.read()
        else:
            pg_script = SQLITE_DDL_SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        db.executescript(pg_script)
    else:
        db.executescript(SQLITE_DDL_SCHEMA)

    for tbl, (_, rows) in NOMENCLATURES_DATA.items():
        if not rows:
            continue
        cols = list(rows[0].keys())
        placeholders = ",".join(["?"] * len(cols))
        col_str = ",".join(cols)
        vals = [tuple(r[c] for c in cols) for r in rows]
        db.executemany(f"INSERT INTO {tbl} ({col_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING", vals)

    epcis = [
        'GMVA (Golfe du Morbihan - Vannes Agglomération)',
        'AQTA (Auray Quiberon Terre Atlantique)',
        'Questembert Communauté',
        'Arc Sud Bretagne',
        'Autres communes du Morbihan (56)',
        'Hors Morbihan (Hors 56)'
    ]
    db.executemany("INSERT INTO epci (nom_epci) VALUES (?) ON CONFLICT DO NOTHING", [(e,) for e in epcis])
    epci_map = dict(db.fetchall("SELECT nom_epci, id_epci FROM epci"))

    db.execute(
        "INSERT INTO commune (nom_commune, departement, id_epci) VALUES (?,?,?) ON CONFLICT DO NOTHING",
        ('Vannes', '56', epci_map['GMVA (Golfe du Morbihan - Vannes Agglomération)'])
    )
    id_vannes = db.fetchone("SELECT id_commune FROM commune WHERE nom_commune = 'Vannes'")[0]

    db.executemany(
        "INSERT INTO quartier (code_quartier, nom_quartier, est_qpv, id_commune) VALUES (?,?,?,?) ON CONFLICT DO NOTHING",
        [
            ('Vannes M', 'Ménimur (QPV)', 1, id_vannes),
            ('Vannes K', 'Kercado (QPV)', 1, id_vannes),
            ('Vannes B', 'Bourdonnaye (QPV)', 1, id_vannes),
        ]
    )
    db.commit()


def run_etl(
    excel_source,
    db_url=None,
    supabase_key=None,
    rules_path=RULES_PATH,
    annee_cible=2024,
    mode_import="replace_year",
    export_csv_path=None,
    export_audit_path=AUDIT_XLSX_PATH,
):
    """
    Pipeline ETL universel (HTTPS Supabase port 443 / PostgreSQL direct / SQLite local) :
    - Applique uniquement les règles explicites de `regles_nettoyage.json`.
    - N'invente jamais de valeur en cas d'ambiguïté.
    - Génère automatiquement `anomalies_lignes_bizarres_<annee>.csv` avec localisation exacte (onglet, cellule, commentaire).
    """
    resolved_url = resolve_db_url(db_url)
    resolved_key = resolve_supabase_key(supabase_key)
    if export_csv_path is None:
        export_csv_path = f"anomalies_lignes_bizarres_{int(annee_cible)}.csv"

    rules = load_rules(rules_path)
    epci_communes = {epci: set(coms) for epci, coms in rules.get("epci_communes", {}).items()}
    quartiers_qpv = rules.get("quartiers_qpv_vannes", {})
    ortho_com = {k.lower(): v for k, v in rules.get("normalisation_orthographe_communes", {}).items()}
    for com_list in epci_communes.values():
        for c_canon in com_list:
            ortho_com.setdefault(c_canon.lower(), c_canon)
    for c_canon in rules.get("communes_56_autres", []):
        ortho_com.setdefault(c_canon.lower(), c_canon)
    depts_hors = rules.get("departements_hors_56", {})
    corr_strictes = rules.get("corrections_syntaxiques_strictes", {})

    if mode_import == "reset_all" and not resolved_url.startswith(("postgresql://", "https://")):
        local_path = resolved_url.replace("sqlite:///", "")
        if os.path.exists(local_path):
            os.remove(local_path)

    db = UniversalDB(resolved_url, supabase_key=resolved_key)
    init_schema_and_nomenclatures(db)

    if mode_import == "replace_year":
        if db.is_https_supabase:
            db.https.delete_where("entretien", "annee", "eq", int(annee_cible))
            db.https.delete_where("anomalie_import", "annee", "eq", int(annee_cible))
        else:
            db.execute("DELETE FROM entretien WHERE annee = ?", (int(annee_cible),))
            db.execute("DELETE FROM anomalie_import WHERE annee = ?", (int(annee_cible),))
            db.commit()
    elif mode_import == "reset_all":
        if db.is_https_supabase:
            db.https.delete_where("anomalie_import", "id_anomalie", "gte", 0)
            db.https.delete_where("entretien", "id_entretien", "gte", 0)
        else:
            db.execute("DELETE FROM anomalie_import")
            db.execute("DELETE FROM entretien")
            db.commit()

    if db.is_https_supabase:
        epci_rows = db.https.select_all("epci")
        epci_map = {r["nom_epci"]: r["id_epci"] for r in epci_rows}
        com_rows = db.https.select_all("commune")
        commune_cache = {r["nom_commune"]: r["id_commune"] for r in com_rows}
        quartier_map = {r["code_quartier"]: r["id_quartier"] for r in db.https.select_all("quartier")}
        lieu_map = {r["nom_lieu"]: r["id_lieu"] for r in db.https.select_all("lieu_permanence")}
        part_map = {r["nom_partenaire"]: r["id_partenaire"] for r in db.https.select_all("partenaire")}

        valid_modes = {r["code_mode"] for r in db.https.select_all("mode_entretien")}
        valid_durees = {r["code_duree"] for r in db.https.select_all("duree")}
        valid_sexes = {r["code_sexe"] for r in db.https.select_all("sexe")}
        valid_ages = {r["code_age"] for r in db.https.select_all("tranche_age")}
        valid_vp = {r["code_vient_pour"] for r in db.https.select_all("vient_pour")}
        valid_sf = {r["code_sit_fam"] for r in db.https.select_all("situation_familiale")}
        valid_mf = {r["code_modele_fam"] for r in db.https.select_all("modele_familial")}
        valid_prof = {r["code_prof"] for r in db.https.select_all("profession")}
        valid_ress = {r["code_ressource"] for r in db.https.select_all("ressource")}
        valid_origs = {r["code_origine"] for r in db.https.select_all("origine_contact")}
        valid_dems = {r["code_demande"] for r in db.https.select_all("nature_demande")}
        valid_reps = {r["code_reponse"] for r in db.https.select_all("type_reponse")}
    else:
        epci_map = dict(db.fetchall("SELECT nom_epci, id_epci FROM epci"))
        commune_cache = dict(db.fetchall("SELECT nom_commune, id_commune FROM commune"))
        quartier_map = dict(db.fetchall("SELECT code_quartier, id_quartier FROM quartier"))
        lieu_map = dict(db.fetchall("SELECT nom_lieu, id_lieu FROM lieu_permanence"))
        part_map = dict(db.fetchall("SELECT nom_partenaire, id_partenaire FROM partenaire"))

        valid_modes = {r[0] for r in db.fetchall("SELECT code_mode FROM mode_entretien")}
        valid_durees = {r[0] for r in db.fetchall("SELECT code_duree FROM duree")}
        valid_sexes = {r[0] for r in db.fetchall("SELECT code_sexe FROM sexe")}
        valid_ages = {r[0] for r in db.fetchall("SELECT code_age FROM tranche_age")}
        valid_vp = {r[0] for r in db.fetchall("SELECT code_vient_pour FROM vient_pour")}
        valid_sf = {r[0] for r in db.fetchall("SELECT code_sit_fam FROM situation_familiale")}
        valid_mf = {r[0] for r in db.fetchall("SELECT code_modele_fam FROM modele_familial")}
        valid_prof = {r[0] for r in db.fetchall("SELECT code_prof FROM profession")}
        valid_ress = {r[0] for r in db.fetchall("SELECT code_ressource FROM ressource")}
        valid_origs = {r[0] for r in db.fetchall("SELECT code_origine FROM origine_contact")}
        valid_dems = {r[0] for r in db.fetchall("SELECT code_demande FROM nature_demande")}
        valid_reps = {r[0] for r in db.fetchall("SELECT code_reponse FROM type_reponse")}

    anomalies_db_rows = []
    anomalies_csv_rows = []
    normalisations_log = []
    pending_concerner = []
    pending_apporter = []

    def get_or_create_commune(nom_com):
        if nom_com in commune_cache:
            return commune_cache[nom_com]
        if nom_com.startswith("Hors 56"):
            dpt = nom_com.split("(")[-1].replace(")", "")
            id_epci = epci_map.get("Hors Morbihan (Hors 56)")
        else:
            dpt = "56"
            id_epci = epci_map.get("Autres communes du Morbihan (56)")
            for epci_name, com_set in epci_communes.items():
                if nom_com in com_set:
                    id_epci = epci_map.get(epci_name, id_epci)
                    break
        if db.is_https_supabase:
            new_id = db.https.insert_one_returning(
                "commune",
                {"nom_commune": nom_com, "departement": dpt, "id_epci": id_epci},
                "id_commune"
            )
        else:
            new_id = db.insert_returning_id(
                "INSERT INTO commune (nom_commune, departement, id_epci) VALUES (?,?,?) RETURNING id_commune",
                (nom_com, dpt, id_epci)
            )
        commune_cache[nom_com] = new_id
        return new_id

    xls = pd.ExcelFile(excel_source)
    month_sheets = ['Jan', 'Fev', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
    available_months = [(idx, s) for idx, s in enumerate(month_sheets, 1) if s in xls.sheet_names]

    if not available_months:
        db.close()
        raise ValueError("Aucun onglet mensuel ('Jan' à 'Déc') trouvé dans le classeur Excel.")

    seen_nums = set()
    entretiens_count = 0
    demandes_count = 0
    reponses_count = 0

    for mois_idx, sheet in available_months:
        df = pd.read_excel(xls, sheet_name=sheet)
        if 'N°' not in df.columns:
            continue

        col_letters = {
            col_name: get_column_letter(col_i + 1)
            for col_i, col_name in enumerate(df.columns)
        }
        df['N_num'] = pd.to_numeric(df['N°'], errors='coerce')

        for idx, row in df[df['N_num'].notna()].iterrows():
            excel_row = int(idx) + 2
            num_fiche = int(row['N_num'])
            entretiens_count += 1

            def log_anom(col, val_brute, type_a, action):
                col_let = col_letters.get(col, "?")
                cell_ref = f"{col_let}{excel_row}" if col_let != "?" else f"L{excel_row}"
                val_str = "VIDE" if (val_brute is None or (isinstance(val_brute, float) and pd.isna(val_brute)) or str(val_brute).strip() == "") else str(val_brute)
                commentaire = (
                    f"Problème détecté dans l'onglet '{sheet}', ligne {excel_row}, cellule {cell_ref} "
                    f"(colonne '{col}', fiche N°{num_fiche}) : valeur '{val_str}' — {type_a}."
                )
                anomalies_db_rows.append((
                    int(annee_cible), sheet, excel_row, cell_ref, num_fiche,
                    col, val_str, commentaire, type_a, action, "A_VERIFIER_CLIENT"
                ))
                csv_entry = {
                    "ID_Anomalie": len(anomalies_csv_rows) + 1,
                    "Onglet_Mois": sheet,
                    "Ligne_Excel": excel_row,
                    "Cellule_Excel": cell_ref,
                    "Num_Fiche": num_fiche,
                    "Colonne_En_Erreur": col,
                    "Valeur_Bizarre": val_str,
                    "Commentaire": commentaire,
                    "Action_ETL_Actuelle": action,
                }
                for c_ctx in CONTEXT_COLS:
                    csv_entry[f"LigneComplexe_{c_ctx}"] = row.get(c_ctx, "")
                anomalies_csv_rows.append(csv_entry)

            if num_fiche in seen_nums:
                log_anom("N°", num_fiche, "Doublon de numéro de fiche dans l'année", "Conservé avec identifiant distinct")
            seen_nums.add(num_fiche)

            mode = str(row.get('Mode')).strip() if pd.notna(row.get('Mode')) else None
            if mode not in valid_modes:
                log_anom("Mode", mode, "Code mode manquant ou inconnu (attendu : 1 à 5)", "Stocké NULL (non deviné)")
                mode = None

            duree = str(row.get('Durée')).strip() if pd.notna(row.get('Durée')) else None
            if duree and duree not in valid_durees:
                log_anom("Durée", duree, "Code durée inconnu (attendu : 1 à 5)", "Stocké NULL (non deviné)")
                duree = None

            sexe = str(row.get('Sexe')).strip() if pd.notna(row.get('Sexe')) else None
            if sexe and sexe not in valid_sexes:
                log_anom("Sexe", sexe, "Code sexe inconnu (attendu : 1 à 4)", "Stocké NULL (non deviné)")
                sexe = None

            age_raw = str(row.get('Age')).strip() if pd.notna(row.get('Age')) else None
            if not age_raw:
                age_val = 'nc'
            elif age_raw in valid_ages:
                age_val = age_raw
            else:
                log_anom("Age", age_raw, "Code tranche d'âge hors nomenclature (attendu : 1 à 5)", "Affecté à 'nc' (Non renseigné)")
                age_val = 'nc'

            vp_raw = str(row.get('Vient pr')).strip() if pd.notna(row.get('Vient pr')) else None
            if not vp_raw:
                vp_val = '7'
            elif vp_raw in valid_vp:
                vp_val = vp_raw
            else:
                log_anom("Vient pr", vp_raw, "Code 'Vient pour' hors nomenclature (attendu : 1 à 6)", "Affecté à '7' (Non renseigné)")
                vp_val = '7'

            sf_raw = str(row.get('Sit° Fam')).strip() if pd.notna(row.get('Sit° Fam')) else None
            if not sf_raw or sf_raw == 'nc':
                sf_val = '7'
            elif sf_raw in valid_sf:
                sf_val = sf_raw
            else:
                log_anom("Sit° Fam", sf_raw, "Code situation familiale hors nomenclature", "Affecté à '7' (Non renseigné)")
                sf_val = '7'

            enfts_raw = str(row.get('Enfts')).strip() if pd.notna(row.get('Enfts')) else None
            if not enfts_raw or enfts_raw == 'nc':
                nb_enfts = None
            else:
                try:
                    nb_enfts = int(float(enfts_raw))
                except ValueError:
                    log_anom("Enfts", enfts_raw, "Valeur non numérique pour le nombre d'enfants", "Stocké NULL")
                    nb_enfts = None

            mf_raw = str(row.get('Modèle fam.')).strip() if pd.notna(row.get('Modèle fam.')) else None
            if not mf_raw or mf_raw == 'nc':
                mf_val = None
            else:
                mf_clean = mf_raw.replace('.0', '')
                if mf_clean in valid_mf:
                    mf_val = mf_clean
                else:
                    log_anom("Modèle fam.", mf_raw, "Code modèle familial hors nomenclature (attendu : 0 à 3)", "Stocké NULL")
                    mf_val = None

            prof_raw = str(row.get('Prof°')).strip() if pd.notna(row.get('Prof°')) else None
            if not prof_raw:
                prof_val = '12'
            elif prof_raw in valid_prof:
                prof_val = prof_raw
            else:
                log_anom("Prof°", prof_raw, "Code profession hors nomenclature (attendu : 1 à 12)", "Affecté à '12' (Non renseigné)")
                prof_val = '12'

            ress_raw = str(row.get('Ress. 1')).strip() if pd.notna(row.get('Ress. 1')) else None
            if not ress_raw:
                ress_val = '11'
            elif ress_raw in valid_ress:
                ress_val = ress_raw
            else:
                log_anom("Ress. 1", ress_raw, "Code ressource hors nomenclature (attendu : 1 à 11)", "Affecté à '11' (Non renseigné)")
                ress_val = '11'

            orig_raw = str(row.get('Origine')).strip() if pd.notna(row.get('Origine')) else None
            lieu_from_orig = None
            orig_val = None
            if orig_raw:
                if 'AQTA' in orig_raw:
                    lieu_from_orig = 'PJ AQTA'
                elif 'Quest' in orig_raw or 'quest' in orig_raw:
                    lieu_from_orig = 'PJ Questembert'
                mapped_orig = corr_strictes.get("origine", {}).get(orig_raw, orig_raw)
                if mapped_orig != orig_raw:
                    normalisations_log.append({"onglet": sheet, "ligne": excel_row, "colonne": "Origine", "avant": orig_raw, "apres": mapped_orig})
                if mapped_orig in valid_origs:
                    orig_val = mapped_orig
                else:
                    log_anom("Origine", orig_raw, "Code origine absent de la fiche Indicateurs", "Stocké NULL — à valider avec le client")

            part_raw = str(row.get('Partenaire')).strip() if pd.notna(row.get('Partenaire')) else None
            nom_lieu = lieu_from_orig or 'Maison du Droit Vannes'
            nom_part = None
            date_str = f"{int(annee_cible)}-{mois_idx:02d}-01"
            date_est = 1

            if part_raw:
                m = re.search(r'(\d{1,2})/(\d{1,2})', part_raw)
                if m:
                    j, mo = int(m.group(1)), int(m.group(2))
                    if 1 <= j <= 31 and 1 <= mo <= 12:
                        date_str = f"{int(annee_cible)}-{mo:02d}-{j:02d}"
                        date_est = 0
                low_p = part_raw.lower()
                if 'aqta' in low_p:
                    nom_lieu = 'PJ AQTA'
                elif 'quest' in low_p:
                    nom_lieu = 'PJ Questembert'
                elif 'avocat mineur' in low_p:
                    nom_part = 'Avocat mineur'
                elif 'avocat' in low_p:
                    nom_part = 'Avocat'
                elif 'conciliateur' in low_p:
                    nom_part = 'Conciliateur de justice'
                elif 'notaire' in low_p:
                    nom_part = 'Notaire'
                elif 'défenseur' in low_p:
                    nom_part = 'Défenseur des Droits'
                else:
                    log_anom("Partenaire", part_raw, "Libellé partenaire non reconnu", "Lieu conservé, partenaire NULL")

            dom_raw = str(row.get('Domicile')).strip() if pd.notna(row.get('Domicile')) else None
            id_com = None
            id_quart = None
            if not dom_raw:
                log_anom("Domicile", "", "Commune manquante", "Stocké NULL (non deviné)")
            else:
                key_dom = dom_raw.lower()
                if key_dom in quartiers_qpv:
                    q_info = quartiers_qpv[key_dom]
                    id_com = get_or_create_commune(q_info["commune"])
                    id_quart = quartier_map.get(q_info["code_quartier"])
                    normalisations_log.append({"onglet": sheet, "ligne": excel_row, "colonne": "Domicile", "avant": dom_raw, "apres": f"{q_info['commune']} + {q_info['code_quartier']}"})
                elif key_dom in ortho_com:
                    clean_com = ortho_com[key_dom]
                    if clean_com != dom_raw:
                        normalisations_log.append({"onglet": sheet, "ligne": excel_row, "colonne": "Domicile", "avant": dom_raw, "apres": clean_com})
                    id_com = get_or_create_commune(clean_com)
                elif key_dom in depts_hors:
                    clean_com = depts_hors[key_dom]
                    normalisations_log.append({"onglet": sheet, "ligne": excel_row, "colonne": "Domicile", "avant": dom_raw, "apres": clean_com})
                    id_com = get_or_create_commune(clean_com)
                else:
                    log_anom("Domicile", dom_raw, "Libellé commune hors référentiel standard", "Conservé tel quel pour audit client")
                    id_com = get_or_create_commune(dom_raw)

            ent_payload = {
                "num_fiche_annuel": num_fiche,
                "date_entretien": date_str,
                "annee": int(annee_cible),
                "mois": mois_idx,
                "date_estimee": date_est,
                "nb_enfants_charge": nb_enfts,
                "code_mode": mode,
                "code_duree": duree,
                "code_sexe": sexe,
                "code_age": age_val,
                "code_vient_pour": vp_val,
                "code_sit_fam": sf_val,
                "code_modele_fam": mf_val,
                "code_prof": prof_val,
                "code_ressource": ress_val,
                "code_origine": orig_val,
                "id_commune": id_com,
                "id_quartier": id_quart,
                "id_lieu": lieu_map.get(nom_lieu),
                "id_partenaire": part_map.get(nom_part) if nom_part else None,
            }

            if db.is_https_supabase:
                id_ent = db.https.insert_one_returning("entretien", ent_payload, "id_entretien")
            else:
                id_ent = db.insert_returning_id("""
                    INSERT INTO entretien (
                        num_fiche_annuel, date_entretien, annee, mois, date_estimee, nb_enfants_charge,
                        code_mode, code_duree, code_sexe, code_age, code_vient_pour,
                        code_sit_fam, code_modele_fam, code_prof, code_ressource, code_origine,
                        id_commune, id_quartier, id_lieu, id_partenaire
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id_entretien
                """, (
                    num_fiche, date_str, int(annee_cible), mois_idx, date_est, nb_enfts,
                    mode, duree, sexe, age_val, vp_val,
                    sf_val, mf_val, prof_val, ress_val, orig_val,
                    id_com, id_quart, lieu_map.get(nom_lieu), part_map.get(nom_part) if nom_part else None
                ))

            seen_dems = set()
            for ordre, col_d in enumerate(['Dem.1', 'Dem.2', 'Dem.3'], 1):
                if col_d in df.columns and pd.notna(row[col_d]):
                    d_raw = str(row[col_d]).strip()
                    d_code = corr_strictes.get("demande", {}).get(d_raw, d_raw)
                    if d_code != d_raw:
                        normalisations_log.append({"onglet": sheet, "ligne": excel_row, "colonne": col_d, "avant": d_raw, "apres": d_code})
                    if d_code in valid_dems:
                        if d_code not in seen_dems:
                            if db.is_https_supabase:
                                pending_concerner.append({"id_entretien": id_ent, "code_demande": d_code, "ordre_demande": ordre})
                            else:
                                db.execute("INSERT INTO concerner VALUES (?,?,?)", (id_ent, d_code, ordre))
                            seen_dems.add(d_code)
                            demandes_count += 1
                    else:
                        log_anom(col_d, d_raw, "Code demande inconnu (absent de la fiche Indicateurs)", "Non inséré — à valider avec le client")

            seen_sols = set()
            for ordre, col_s in enumerate(['Sol.1', 'Sol.2', 'Sol.3'], 1):
                if col_s in df.columns and pd.notna(row[col_s]):
                    s_raw = str(row[col_s]).strip()
                    s_code = corr_strictes.get("reponse", {}).get(s_raw, s_raw)
                    if s_code != s_raw:
                        normalisations_log.append({"onglet": sheet, "ligne": excel_row, "colonne": col_s, "avant": s_raw, "apres": s_code})
                    if s_code in valid_reps:
                        if s_code not in seen_sols:
                            if db.is_https_supabase:
                                pending_apporter.append({"id_entretien": id_ent, "code_reponse": s_code, "ordre_reponse": ordre})
                            else:
                                db.execute("INSERT INTO apporter VALUES (?,?,?)", (id_ent, s_code, ordre))
                            seen_sols.add(s_code)
                            reponses_count += 1
                    else:
                        log_anom(col_s, s_raw, "Code solution inconnu (absent de la fiche Indicateurs)", "Non inséré — à valider avec le client")

    if db.is_https_supabase:
        if pending_concerner:
            db.https.insert_many("concerner", pending_concerner)
        if pending_apporter:
            db.https.insert_many("apporter", pending_apporter)
        if anomalies_db_rows:
            anom_dicts = [
                {
                    "annee": r[0], "onglet": r[1], "ligne_excel": r[2], "cellule_excel": r[3],
                    "num_fiche": r[4], "colonne": r[5], "valeur_brute": r[6], "commentaire": r[7],
                    "type_anomalie": r[8], "action_prise": r[9], "statut": r[10]
                }
                for r in anomalies_db_rows
            ]
            db.https.insert_many("anomalie_import", anom_dicts)
    else:
        if anomalies_db_rows:
            db.executemany("""
                INSERT INTO anomalie_import (
                    annee, onglet, ligne_excel, cellule_excel, num_fiche,
                    colonne, valeur_brute, commentaire, type_anomalie, action_prise, statut
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, anomalies_db_rows)
        db.commit()

    db.close()

    df_csv_out = pd.DataFrame(anomalies_csv_rows)
    if export_csv_path:
        df_csv_out.to_csv(export_csv_path, sep=";", index=False, encoding="utf-8-sig")

    if export_audit_path:
        with pd.ExcelWriter(export_audit_path, engine="openpyxl") as writer:
            df_csv_out.to_excel(writer, sheet_name="Anomalies_Lignes_Bizarres", index=False)
            pd.DataFrame(normalisations_log).to_excel(writer, sheet_name="Normalisations_Appliquees", index=False)

    if db.is_https_supabase:
        moteur_label = "Supabase HTTPS API (Port 443)"
    elif db.is_postgres:
        moteur_label = "PostgreSQL Direct (Client-Serveur)"
    else:
        moteur_label = "SQLite (Local)"

    return {
        "moteur_bdd": moteur_label,
        "onglets_lus": len(available_months),
        "entretiens_importes": entretiens_count,
        "demandes_inserees": demandes_count,
        "reponses_inserees": reponses_count,
        "normalisations_deterministes": len(normalisations_log),
        "anomalies_consignees_sans_invention": len(anomalies_csv_rows),
        "fichier_csv_anomalies": export_csv_path,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline ETL HTTPS Supabase (443) / PostgreSQL / SQLite — Maison du Droit de Vannes")
    parser.add_argument("excel_file", nargs="?", default="24 12 Mais.Droit STATS 2024.xlsx", help="Chemin du fichier Excel (.xlsx)")
    parser.add_argument("--db-url", default=None, help="URL HTTPS Supabase (https://...supabase.co), postgresql://... ou sqlite:///maison_droit.db")
    parser.add_argument("--supabase-key", default=None, help="Clé API publique Supabase (anon / publishable) si URL https://")
    parser.add_argument("--annee", type=int, default=2024, help="Année des données (défaut: 2024)")
    parser.add_argument("--mode", choices=["replace_year", "append", "reset_all"], default="reset_all", help="Mode d'import")
    parser.add_argument("--csv-anomalies", default=None, help="Chemin du CSV de sortie des anomalies")
    args = parser.parse_args()

    if not os.path.exists(args.excel_file):
        print(f"Erreur : fichier introuvable -> {args.excel_file}")
        sys.exit(1)

    rapport = run_etl(
        args.excel_file,
        db_url=args.db_url,
        supabase_key=args.supabase_key,
        annee_cible=args.annee,
        mode_import=args.mode,
        export_csv_path=args.csv_anomalies,
    )
    print("=== RAPPORT D'EXÉCUTION ETL ===")
    for k, v in rapport.items():
        print(f"  - {k}: {v}")
