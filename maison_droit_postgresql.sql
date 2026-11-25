-- ============================================================================
-- MPD PostgreSQL (SGBDR Open Source Client-Serveur) — Maison du Droit de Vannes
-- Compatible : PostgreSQL 14+ (Supabase, Neon, Alwaysdata, serveur local)
-- ============================================================================

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
    id_lieu SERIAL PRIMARY KEY,
    nom_lieu VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS partenaire (
    id_partenaire SERIAL PRIMARY KEY,
    nom_partenaire VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS categorie_origine (
    code_cat_origine VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_cat_origine VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS origine_contact (
    code_origine VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_origine VARCHAR(100) NOT NULL,
    code_cat_origine VARCHAR(10) NOT NULL REFERENCES categorie_origine(code_cat_origine)
);

CREATE TABLE IF NOT EXISTS epci (
    id_epci SERIAL PRIMARY KEY,
    nom_epci VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS commune (
    id_commune SERIAL PRIMARY KEY,
    code_insee VARCHAR(10),
    nom_commune VARCHAR(100) NOT NULL UNIQUE,
    departement VARCHAR(10),
    id_epci INTEGER REFERENCES epci(id_epci)
);

CREATE TABLE IF NOT EXISTS quartier (
    id_quartier SERIAL PRIMARY KEY,
    code_quartier VARCHAR(20) NOT NULL UNIQUE,
    nom_quartier VARCHAR(100) NOT NULL,
    est_qpv SMALLINT NOT NULL DEFAULT 0,
    id_commune INTEGER NOT NULL REFERENCES commune(id_commune)
);

CREATE TABLE IF NOT EXISTS domaine_droit (
    code_domaine VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_domaine VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS nature_demande (
    code_demande VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_demande VARCHAR(100) NOT NULL,
    code_domaine VARCHAR(10) NOT NULL REFERENCES domaine_droit(code_domaine)
);

CREATE TABLE IF NOT EXISTS categorie_reponse (
    code_cat_reponse VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_cat_reponse VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS type_reponse (
    code_reponse VARCHAR(10) NOT NULL PRIMARY KEY,
    libelle_reponse VARCHAR(100) NOT NULL,
    code_cat_reponse VARCHAR(10) NOT NULL REFERENCES categorie_reponse(code_cat_reponse)
);

CREATE TABLE IF NOT EXISTS entretien (
    id_entretien SERIAL PRIMARY KEY,
    num_fiche_annuel INTEGER,
    date_entretien DATE,
    annee INTEGER,
    mois INTEGER,
    date_estimee SMALLINT DEFAULT 1,
    nb_enfants_charge INTEGER,
    code_mode VARCHAR(10) REFERENCES mode_entretien(code_mode),
    code_duree VARCHAR(10) REFERENCES duree(code_duree),
    code_sexe VARCHAR(10) REFERENCES sexe(code_sexe),
    code_age VARCHAR(10) REFERENCES tranche_age(code_age),
    code_vient_pour VARCHAR(10) REFERENCES vient_pour(code_vient_pour),
    code_sit_fam VARCHAR(10) REFERENCES situation_familiale(code_sit_fam),
    code_modele_fam VARCHAR(10) REFERENCES modele_familial(code_modele_fam),
    code_prof VARCHAR(10) REFERENCES profession(code_prof),
    code_ressource VARCHAR(10) REFERENCES ressource(code_ressource),
    code_origine VARCHAR(10) REFERENCES origine_contact(code_origine),
    id_commune INTEGER REFERENCES commune(id_commune),
    id_quartier INTEGER REFERENCES quartier(id_quartier),
    id_lieu INTEGER REFERENCES lieu_permanence(id_lieu),
    id_partenaire INTEGER REFERENCES partenaire(id_partenaire)
);

CREATE TABLE IF NOT EXISTS concerner (
    id_entretien INTEGER NOT NULL REFERENCES entretien(id_entretien) ON DELETE CASCADE,
    code_demande VARCHAR(10) NOT NULL REFERENCES nature_demande(code_demande),
    ordre_demande INTEGER NOT NULL,
    PRIMARY KEY (id_entretien, code_demande)
);

CREATE TABLE IF NOT EXISTS apporter (
    id_entretien INTEGER NOT NULL REFERENCES entretien(id_entretien) ON DELETE CASCADE,
    code_reponse VARCHAR(10) NOT NULL REFERENCES type_reponse(code_reponse),
    ordre_reponse INTEGER NOT NULL,
    PRIMARY KEY (id_entretien, code_reponse)
);

CREATE TABLE IF NOT EXISTS anomalie_import (
    id_anomalie SERIAL PRIMARY KEY,
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

-- Index décisionnels pour accélérer les bilans financeurs et tableaux de bord
CREATE INDEX IF NOT EXISTS idx_entretien_annee_mois ON entretien(annee, mois);
CREATE INDEX IF NOT EXISTS idx_entretien_commune ON entretien(id_commune);
CREATE INDEX IF NOT EXISTS idx_entretien_quartier ON entretien(id_quartier);
CREATE INDEX IF NOT EXISTS idx_entretien_lieu ON entretien(id_lieu);
