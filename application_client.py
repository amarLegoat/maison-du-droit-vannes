import io
import os
from datetime import date
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from db_adapter import UniversalDB, resolve_supabase_key
from etl_pipeline import init_schema_and_nomenclatures

st.set_page_config(
    page_title="Maison du Droit de Vannes — Point Justice",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1E3A5F 0%, #2B547E 100%);
        padding: 1.2rem 1.5rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 1.2rem;
    }
    .main-header h1 { color: white; font-size: 1.7rem; margin: 0; }
    .main-header p { color: #DCE6F1; margin: 0.2rem 0 0 0; font-size: 0.95rem; }
    div[data-testid="metric-container"] {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        padding: 0.8rem 1rem;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

MOIS_LABELS = {
    1: "01 - Janvier", 2: "02 - Février", 3: "03 - Mars", 4: "04 - Avril",
    5: "05 - Mai", 6: "06 - Juin", 7: "07 - Juillet", 8: "08 - Août",
    9: "09 - Septembre", 10: "10 - Octobre", 11: "11 - Novembre", 12: "12 - Décembre"
}

# Repli optionnel si aucun fichier .streamlit/secrets.toml ou variable d'environnement n'est défini
FALLBACK_SUPABASE_URL = ""
FALLBACK_SUPABASE_KEY = ""


def get_client_db_config():
    url = ""
    key = ""
    try:
        if "SUPABASE_URL" in st.secrets:
            url = str(st.secrets["SUPABASE_URL"]).strip()
        elif "DATABASE_URL" in st.secrets:
            url = str(st.secrets["DATABASE_URL"]).strip()
        if "SUPABASE_KEY" in st.secrets:
            key = str(st.secrets["SUPABASE_KEY"]).strip()
    except Exception:
        pass

    if not url:
        url = (os.environ.get("SUPABASE_URL") or os.environ.get("DATABASE_URL") or FALLBACK_SUPABASE_URL or "").strip()
    if not key:
        key = resolve_supabase_key(FALLBACK_SUPABASE_KEY)
    if not url:
        url = "sqlite:///maison_droit.db"
    return url, key


CLIENT_DB_URL, CLIENT_SUPABASE_KEY = get_client_db_config()


def get_db():
    db = UniversalDB(CLIENT_DB_URL, supabase_key=CLIENT_SUPABASE_KEY)
    init_schema_and_nomenclatures(db)
    return db


def _build_joined_dataframes(db: UniversalDB):
    if db.is_https_supabase:
        ent_rows = db.https.select_all("entretien")
        if not ent_rows:
            empty_ent = pd.DataFrame(columns=[
                "id_entretien", "num_fiche_annuel", "date_entretien", "annee", "mois", "mois_label",
                "nb_enfants_charge", "code_mode", "mode", "duree", "sexe", "code_age", "age",
                "vient_pour", "situation_familiale", "modele_familial", "profession",
                "code_ressource", "ressource", "code_origine", "origine", "cat_origine",
                "commune", "epci", "code_quartier", "quartier", "est_qpv", "lieu_permanence", "partenaire"
            ])
            empty_dem = pd.DataFrame(columns=["id_entretien", "ordre_demande", "code_demande", "libelle_demande", "code_domaine", "libelle_domaine"])
            empty_rep = pd.DataFrame(columns=["id_entretien", "ordre_reponse", "code_reponse", "libelle_reponse", "code_cat_reponse", "libelle_cat_reponse"])
            anom_rows = db.https.select_all("anomalie_import", order_by="id_anomalie.asc")
            return empty_ent, empty_dem, empty_rep, pd.DataFrame(anom_rows)

        df_ent = pd.DataFrame(ent_rows)
        modes_m = {r["code_mode"]: r["libelle_mode"] for r in db.https.select_all("mode_entretien")}
        durees_m = {r["code_duree"]: r["libelle_duree"] for r in db.https.select_all("duree")}
        sexes_m = {r["code_sexe"]: r["libelle_sexe"] for r in db.https.select_all("sexe")}
        ages_m = {r["code_age"]: r["libelle_age"] for r in db.https.select_all("tranche_age")}
        vp_m = {r["code_vient_pour"]: r["libelle_vient_pour"] for r in db.https.select_all("vient_pour")}
        sf_m = {r["code_sit_fam"]: r["libelle_sit_fam"] for r in db.https.select_all("situation_familiale")}
        mf_m = {r["code_modele_fam"]: r["libelle_modele_fam"] for r in db.https.select_all("modele_familial")}
        prof_m = {r["code_prof"]: r["libelle_prof"] for r in db.https.select_all("profession")}
        ress_m = {r["code_ressource"]: r["libelle_ressource"] for r in db.https.select_all("ressource")}
        orig_rows = db.https.select_all("origine_contact")
        cat_orig_m = {r["code_cat_origine"]: r["libelle_cat_origine"] for r in db.https.select_all("categorie_origine")}
        orig_m = {r["code_origine"]: r["libelle_origine"] for r in orig_rows}
        orig_cat_link = {r["code_origine"]: cat_orig_m.get(r.get("code_cat_origine")) for r in orig_rows}

        epci_m = {r["id_epci"]: r["nom_epci"] for r in db.https.select_all("epci")}
        com_rows = db.https.select_all("commune")
        com_m = {r["id_commune"]: r["nom_commune"] for r in com_rows}
        com_epci_m = {r["id_commune"]: epci_m.get(r.get("id_epci")) for r in com_rows}

        quart_rows = db.https.select_all("quartier")
        q_code_m = {r["id_quartier"]: r["code_quartier"] for r in quart_rows}
        q_nom_m = {r["id_quartier"]: r["nom_quartier"] for r in quart_rows}
        q_qpv_m = {r["id_quartier"]: int(r.get("est_qpv") or 0) for r in quart_rows}

        lieu_m = {r["id_lieu"]: r["nom_lieu"] for r in db.https.select_all("lieu_permanence")}
        part_m = {r["id_partenaire"]: r["nom_partenaire"] for r in db.https.select_all("partenaire")}

        df_ent["mode"] = df_ent["code_mode"].map(modes_m)
        df_ent["duree"] = df_ent["code_duree"].map(durees_m)
        df_ent["sexe"] = df_ent["code_sexe"].map(sexes_m)
        df_ent["age"] = df_ent["code_age"].map(ages_m)
        df_ent["vient_pour"] = df_ent["code_vient_pour"].map(vp_m)
        df_ent["situation_familiale"] = df_ent["code_sit_fam"].map(sf_m)
        df_ent["modele_familial"] = df_ent["code_modele_fam"].map(mf_m)
        df_ent["profession"] = df_ent["code_prof"].map(prof_m)
        df_ent["ressource"] = df_ent["code_ressource"].map(ress_m)
        df_ent["origine"] = df_ent["code_origine"].map(orig_m)
        df_ent["cat_origine"] = df_ent["code_origine"].map(orig_cat_link)
        df_ent["commune"] = df_ent["id_commune"].map(com_m)
        df_ent["epci"] = df_ent["id_commune"].map(com_epci_m)
        df_ent["code_quartier"] = df_ent["id_quartier"].map(q_code_m)
        df_ent["quartier"] = df_ent["id_quartier"].map(q_nom_m)
        df_ent["est_qpv"] = df_ent["id_quartier"].map(q_qpv_m).fillna(0).astype(int)
        df_ent["lieu_permanence"] = df_ent["id_lieu"].map(lieu_m)
        df_ent["partenaire"] = df_ent["id_partenaire"].map(part_m)
        df_ent["mois_label"] = df_ent["mois"].map(MOIS_LABELS)

        conc_rows = db.https.select_all("concerner")
        nd_rows = db.https.select_all("nature_demande")
        dd_m = {r["code_domaine"]: r["libelle_domaine"] for r in db.https.select_all("domaine_droit")}
        nd_lib_m = {r["code_demande"]: r["libelle_demande"] for r in nd_rows}
        nd_dom_code_m = {r["code_demande"]: r["code_domaine"] for r in nd_rows}
        if conc_rows:
            df_dem = pd.DataFrame(conc_rows)
            df_dem["libelle_demande"] = df_dem["code_demande"].map(nd_lib_m)
            df_dem["code_domaine"] = df_dem["code_demande"].map(nd_dom_code_m)
            df_dem["libelle_domaine"] = df_dem["code_domaine"].map(dd_m)
        else:
            df_dem = pd.DataFrame(columns=["id_entretien", "ordre_demande", "code_demande", "libelle_demande", "code_domaine", "libelle_domaine"])

        app_rows = db.https.select_all("apporter")
        tr_rows = db.https.select_all("type_reponse")
        cr_m = {r["code_cat_reponse"]: r["libelle_cat_reponse"] for r in db.https.select_all("categorie_reponse")}
        tr_lib_m = {r["code_reponse"]: r["libelle_reponse"] for r in tr_rows}
        tr_cat_code_m = {r["code_reponse"]: r["code_cat_reponse"] for r in tr_rows}
        if app_rows:
            df_rep = pd.DataFrame(app_rows)
            df_rep["libelle_reponse"] = df_rep["code_reponse"].map(tr_lib_m)
            df_rep["code_cat_reponse"] = df_rep["code_reponse"].map(tr_cat_code_m)
            df_rep["libelle_cat_reponse"] = df_rep["code_cat_reponse"].map(cr_m)
        else:
            df_rep = pd.DataFrame(columns=["id_entretien", "ordre_reponse", "code_reponse", "libelle_reponse", "code_cat_reponse", "libelle_cat_reponse"])

        df_anom = pd.DataFrame(db.https.select_all("anomalie_import", order_by="id_anomalie.asc"))
        return df_ent, df_dem, df_rep, df_anom

    q_ent = """
    SELECT 
        e.id_entretien, e.num_fiche_annuel, e.date_entretien, e.annee, e.mois, e.nb_enfants_charge,
        m.code_mode, m.libelle_mode AS mode,
        d.libelle_duree AS duree,
        s.libelle_sexe AS sexe,
        a.code_age, a.libelle_age AS age,
        vp.libelle_vient_pour AS vient_pour,
        sf.libelle_sit_fam AS situation_familiale,
        mf.libelle_modele_fam AS modele_familial,
        p.libelle_prof AS profession,
        r.code_ressource, r.libelle_ressource AS ressource,
        o.code_origine, o.libelle_origine AS origine,
        co.libelle_cat_origine AS cat_origine,
        c.nom_commune AS commune,
        ep.nom_epci AS epci,
        q.code_quartier, q.nom_quartier AS quartier,
        COALESCE(q.est_qpv, 0) AS est_qpv,
        l.nom_lieu AS lieu_permanence,
        pt.nom_partenaire AS partenaire
    FROM entretien e
    LEFT JOIN mode_entretien m ON e.code_mode = m.code_mode
    LEFT JOIN duree d ON e.code_duree = d.code_duree
    LEFT JOIN sexe s ON e.code_sexe = s.code_sexe
    LEFT JOIN tranche_age a ON e.code_age = a.code_age
    LEFT JOIN vient_pour vp ON e.code_vient_pour = vp.code_vient_pour
    LEFT JOIN situation_familiale sf ON e.code_sit_fam = sf.code_sit_fam
    LEFT JOIN modele_familial mf ON e.code_modele_fam = mf.code_modele_fam
    LEFT JOIN profession p ON e.code_prof = p.code_prof
    LEFT JOIN ressource r ON e.code_ressource = r.code_ressource
    LEFT JOIN origine_contact o ON e.code_origine = o.code_origine
    LEFT JOIN categorie_origine co ON o.code_cat_origine = co.code_cat_origine
    LEFT JOIN commune c ON e.id_commune = c.id_commune
    LEFT JOIN epci ep ON c.id_epci = ep.id_epci
    LEFT JOIN quartier q ON e.id_quartier = q.id_quartier
    LEFT JOIN lieu_permanence l ON e.id_lieu = l.id_lieu
    LEFT JOIN partenaire pt ON e.id_partenaire = pt.id_partenaire
    """
    df_ent = db.read_df(q_ent)
    if len(df_ent) > 0:
        df_ent["mois_label"] = df_ent["mois"].map(MOIS_LABELS)

    df_dem = db.read_df("""
        SELECT c.id_entretien, c.ordre_demande, nd.code_demande, nd.libelle_demande,
               dd.code_domaine, dd.libelle_domaine
        FROM concerner c
        JOIN nature_demande nd ON c.code_demande = nd.code_demande
        JOIN domaine_droit dd ON nd.code_domaine = dd.code_domaine
    """)
    df_rep = db.read_df("""
        SELECT a.id_entretien, a.ordre_reponse, tr.code_reponse, tr.libelle_reponse,
               cr.code_cat_reponse, cr.libelle_cat_reponse
        FROM apporter a
        JOIN type_reponse tr ON a.code_reponse = tr.code_reponse
        JOIN categorie_reponse cr ON tr.code_cat_reponse = cr.code_cat_reponse
    """)
    df_anom = db.read_df("SELECT * FROM anomalie_import ORDER BY id_anomalie")
    return df_ent, df_dem, df_rep, df_anom


@st.cache_data(ttl=30)
def load_data(db_url_key, supa_key):
    db = UniversalDB(db_url_key, supabase_key=supa_key)
    init_schema_and_nomenclatures(db)
    ent, dem, rep, anom = _build_joined_dataframes(db)
    db.close()
    return ent, dem, rep, anom


try:
    df_ent, df_dem, df_rep, df_anom = load_data(CLIENT_DB_URL, CLIENT_SUPABASE_KEY)
except Exception:
    st.error("Impossible d'accéder aux données pour le moment. Veuillez réessayer.")
    st.stop()

st.markdown("""
<div class="main-header">
    <h1>⚖️ Maison du Droit de Vannes — Point Justice</h1>
    <p>Suivi des entretiens, Bilans territoriaux & financeurs, Saisie quotidienne & Analyse des profils</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.header(" Filtres d'analyse")

annees_dispo = sorted(df_ent["annee"].dropna().astype(int).unique().tolist()) if len(df_ent) > 0 else [2024]
sel_annees = st.sidebar.multiselect("Année(s)", annees_dispo, default=annees_dispo)

bilan_preset = st.sidebar.selectbox(
    "Bilan prédéfini (Financeurs)",
    [
        "Tous les entretiens",
        "Quartiers Prioritaires (QPV Vannes)",
        "Jeunes (-25 ans)",
        "Public CAF (Familles avec enfant(s))",
        "Ville de Vannes",
        "Permanences PJ AQTA",
        "Territoire AQTA (Habitants)",
        "Permanences PJ Questembert",
        "Territoire Questembert Communauté",
    ],
)

epci_options = ["Tous"] + sorted(df_ent["epci"].dropna().unique().tolist())
sel_epci = st.sidebar.selectbox("Territoire (EPCI)", epci_options)

lieu_options = ["Tous"] + sorted(df_ent["lieu_permanence"].dropna().unique().tolist())
sel_lieu = st.sidebar.selectbox("Lieu de permanence", lieu_options)

mode_options = sorted(df_ent["mode"].dropna().unique().tolist())
sel_modes = st.sidebar.multiselect("Mode d'entretien", mode_options, default=mode_options)

mois_options = sorted(df_ent["mois"].dropna().unique().tolist())
sel_mois = st.sidebar.multiselect(
    "Mois",
    mois_options,
    default=mois_options,
    format_func=lambda m: MOIS_LABELS.get(m, str(m)),
)

df_f = df_ent.copy()
if len(df_f) > 0:
    if sel_annees:
        df_f = df_f[df_f["annee"].isin(sel_annees)]
    if bilan_preset == "Quartiers Prioritaires (QPV Vannes)":
        df_f = df_f[df_f["est_qpv"] == 1]
    elif bilan_preset == "Jeunes (-25 ans)":
        df_f = df_f[df_f["code_age"].isin(["1", "2"])]
    elif bilan_preset == "Public CAF (Familles avec enfant(s))":
        df_f = df_f[df_f["nb_enfants_charge"].fillna(0) >= 1]
    elif bilan_preset == "Ville de Vannes":
        df_f = df_f[df_f["commune"] == "Vannes"]
    elif bilan_preset == "Permanences PJ AQTA":
        df_f = df_f[df_f["lieu_permanence"] == "PJ AQTA"]
    elif bilan_preset == "Territoire AQTA (Habitants)":
        df_f = df_f[df_f["epci"].astype(str).str.contains("AQTA", na=False)]
    elif bilan_preset == "Permanences PJ Questembert":
        df_f = df_f[df_f["lieu_permanence"] == "PJ Questembert"]
    elif bilan_preset == "Territoire Questembert Communauté":
        df_f = df_f[df_f["epci"].astype(str).str.contains("Questembert", na=False)]

    if sel_epci != "Tous":
        df_f = df_f[df_f["epci"] == sel_epci]
    if sel_lieu != "Tous":
        df_f = df_f[df_f["lieu_permanence"] == sel_lieu]
    if sel_modes:
        df_f = df_f[df_f["mode"].isin(sel_modes)]
    if sel_mois:
        df_f = df_f[df_f["mois"].isin(sel_mois)]

ids_filtres = set(df_f["id_entretien"]) if len(df_f) > 0 else set()
dem_f = df_dem[df_dem["id_entretien"].isin(ids_filtres)] if len(df_dem) > 0 else df_dem
rep_f = df_rep[df_rep["id_entretien"].isin(ids_filtres)] if len(df_rep) > 0 else df_rep

tab_dash, tab_saisie, tab_afc, tab_export, tab_qualite = st.tabs([
    " Tableau de bord dataviz",
    " Saisie entretien",
    " Profils des appelants AFC",
    " Export Excel",
    f" Journal d'audit ETL ({len(df_anom)})",
])

with tab_dash:
    nb_ent = len(df_f)
    nb_dem = len(dem_f)
    ratio_dem = (nb_dem / nb_ent) if nb_ent > 0 else 0
    pct_femmes = (df_f["sexe"].eq("Femme").mean() * 100) if nb_ent > 0 else 0
    pct_qpv = (df_f["est_qpv"].eq(1).mean() * 100) if nb_ent > 0 else 0
    pct_tot = (nb_ent / len(df_ent) * 100) if len(df_ent) > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Entretiens qualifiés", f"{nb_ent:,}".replace(",", " "), f"{pct_tot:.1f}% du total")
    k2.metric("Demandes enregistrées", f"{nb_dem:,}".replace(",", " "), f"{ratio_dem:.2f} dem. / entretien")
    k3.metric("Part des femmes", f"{pct_femmes:.1f} %")
    k4.metric("Public résidant en QPV", f"{pct_qpv:.1f} %", f"{int(df_f['est_qpv'].sum()) if nb_ent > 0 else 0} entretiens")

    st.divider()

    if nb_ent > 0:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Évolution mensuelle des entretiens")
            mensuel = (
                df_f.groupby(["mois", "mois_label", "mode"], as_index=False)
                .size()
                .rename(columns={"size": "Entretiens"})
            )
            fig_mois = px.bar(
                mensuel,
                x="mois_label",
                y="Entretiens",
                color="mode",
                barmode="stack",
                color_discrete_sequence=px.colors.qualitative.Set2,
                labels={"mois_label": "Mois", "mode": "Mode"},
            )
            fig_mois.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig_mois, use_container_width=True)

        with col2:
            st.subheader("Répartition par domaine de droit")
            dom_counts = (
                dem_f.groupby("libelle_domaine", as_index=False)
                .size()
                .rename(columns={"size": "Demandes"})
                .sort_values("Demandes", ascending=True)
            )
            fig_dom = px.bar(
                dom_counts,
                x="Demandes",
                y="libelle_domaine",
                orientation="h",
                text="Demandes",
                color="Demandes",
                color_continuous_scale="Blues",
                labels={"libelle_domaine": ""},
            )
            fig_dom.update_layout(height=360, showlegend=False, coloraxis_showscale=False, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig_dom, use_container_width=True)

        col3, col4 = st.columns(2)
        with col3:
            st.subheader("Profil sociodémographique (Âge & Ressources)")
            sub_c1, sub_c2 = st.columns(2)
            age_df = df_f[df_f["code_age"] != "nc"].groupby("age", as_index=False).size()
            fig_age = px.pie(
                age_df,
                names="age",
                values="size",
                hole=0.45,
                title="Tranches d'âge",
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig_age.update_layout(height=320, margin=dict(l=5, r=5, t=35, b=5), legend=dict(orientation="h", y=-0.2))
            sub_c1.plotly_chart(fig_age, use_container_width=True)

            ress_df = (
                df_f[df_f["code_ressource"] != "11"]
                .groupby("ressource", as_index=False)
                .size()
                .sort_values("size", ascending=True)
                .tail(7)
            )
            fig_ress = px.bar(
                ress_df,
                x="size",
                y="ressource",
                orientation="h",
                title="Principales ressources",
                labels={"size": "Usagers", "ressource": ""},
            )
            fig_ress.update_traces(marker_color="#2B547E")
            fig_ress.update_layout(height=320, margin=dict(l=5, r=5, t=35, b=5))
            sub_c2.plotly_chart(fig_ress, use_container_width=True)

        with col4:
            st.subheader("Origine territoriale (EPCI & Quartiers QPV)")
            epci_df = (
                df_f.groupby("epci", as_index=False)
                .size()
                .rename(columns={"size": "Entretiens"})
                .sort_values("Entretiens", ascending=True)
            )
            fig_epci = px.bar(
                epci_df,
                x="Entretiens",
                y="epci",
                orientation="h",
                text="Entretiens",
                labels={"epci": ""},
            )
            fig_epci.update_traces(marker_color="#3B7A57")
            fig_epci.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig_epci, use_container_width=True)

        st.subheader(" Exploration détaillée : Natures de demandes & Réponses apportées")
        d_col1, d_col2 = st.columns(2)
        with d_col1:
            domaines_list = ["Tous les domaines"] + sorted(dem_f["libelle_domaine"].dropna().unique().tolist())
            sel_dom_detail = st.selectbox("Filtrer les sous-demandes par domaine :", domaines_list)
            sub_dem = dem_f if sel_dom_detail == "Tous les domaines" else dem_f[dem_f["libelle_domaine"] == sel_dom_detail]
            top_nat = (
                sub_dem.groupby("libelle_demande", as_index=False)
                .size()
                .rename(columns={"size": "Occurrences"})
                .sort_values("Occurrences", ascending=False)
                .head(10)
            )
            st.dataframe(top_nat, use_container_width=True, hide_index=True)

        with d_col2:
            top_rep = (
                rep_f.groupby(["libelle_cat_reponse", "libelle_reponse"], as_index=False)
                .size()
                .rename(columns={"libelle_cat_reponse": "Catégorie", "libelle_reponse": "Réponse / Orientation", "size": "Occurrences"})
                .sort_values("Occurrences", ascending=False)
                .head(10)
            )
            st.dataframe(top_rep, use_container_width=True, hide_index=True)
    else:
        st.info("Aucune donnée disponible pour la sélection en cours.")

with tab_saisie:
    st.subheader("Enregistrer un nouvel entretien")
    db = get_db()
    if db.is_https_supabase:
        modes_ref = {r["code_mode"]: r["libelle_mode"] for r in db.https.select_all("mode_entretien")}
        durees_ref = {r["code_duree"]: r["libelle_duree"] for r in db.https.select_all("duree")}
        sexes_ref = {r["code_sexe"]: r["libelle_sexe"] for r in db.https.select_all("sexe")}
        ages_ref = {r["code_age"]: r["libelle_age"] for r in db.https.select_all("tranche_age")}
        vp_ref = {r["code_vient_pour"]: r["libelle_vient_pour"] for r in db.https.select_all("vient_pour")}
        sf_ref = {r["code_sit_fam"]: r["libelle_sit_fam"] for r in db.https.select_all("situation_familiale")}
        mf_ref = {r["code_modele_fam"]: r["libelle_modele_fam"] for r in db.https.select_all("modele_familial")}
        prof_ref = {r["code_prof"]: r["libelle_prof"] for r in db.https.select_all("profession")}
        ress_ref = {r["code_ressource"]: r["libelle_ressource"] for r in db.https.select_all("ressource")}
        orig_ref = {r["code_origine"]: f"{r['code_origine']} - {r['libelle_origine']}" for r in db.https.select_all("origine_contact", order_by="code_origine.asc")}
        com_ref = {r["id_commune"]: r["nom_commune"] for r in db.https.select_all("commune", order_by="nom_commune.asc")}
        quart_ref = {r["id_quartier"]: r["nom_quartier"] for r in db.https.select_all("quartier")}
        lieu_ref = {r["id_lieu"]: r["nom_lieu"] for r in db.https.select_all("lieu_permanence")}
        part_ref = {r["id_partenaire"]: r["nom_partenaire"] for r in db.https.select_all("partenaire")}
        dd_m = {r["code_domaine"]: r["libelle_domaine"] for r in db.https.select_all("domaine_droit")}
        dem_ref = {
            r["code_demande"]: f"{r['code_demande']} - {r['libelle_demande']} ({dd_m.get(r.get('code_domaine'), '')})"
            for r in db.https.select_all("nature_demande", order_by="code_demande.asc")
        }
        cr_m = {r["code_cat_reponse"]: r["libelle_cat_reponse"] for r in db.https.select_all("categorie_reponse")}
        rep_ref = {
            r["code_reponse"]: f"{r['code_reponse']} - {r['libelle_reponse']} ({cr_m.get(r.get('code_cat_reponse'), '')})"
            for r in db.https.select_all("type_reponse", order_by="code_reponse.asc")
        }
        max_num = int(df_ent["num_fiche_annuel"].max()) + 1 if len(df_ent) > 0 and df_ent["num_fiche_annuel"].notna().any() else 1
    else:
        modes_ref = dict(db.fetchall("SELECT code_mode, libelle_mode FROM mode_entretien"))
        durees_ref = dict(db.fetchall("SELECT code_duree, libelle_duree FROM duree"))
        sexes_ref = dict(db.fetchall("SELECT code_sexe, libelle_sexe FROM sexe"))
        ages_ref = dict(db.fetchall("SELECT code_age, libelle_age FROM tranche_age"))
        vp_ref = dict(db.fetchall("SELECT code_vient_pour, libelle_vient_pour FROM vient_pour"))
        sf_ref = dict(db.fetchall("SELECT code_sit_fam, libelle_sit_fam FROM situation_familiale"))
        mf_ref = dict(db.fetchall("SELECT code_modele_fam, libelle_modele_fam FROM modele_familial"))
        prof_ref = dict(db.fetchall("SELECT code_prof, libelle_prof FROM profession"))
        ress_ref = dict(db.fetchall("SELECT code_ressource, libelle_ressource FROM ressource"))
        orig_ref = dict(db.fetchall("SELECT code_origine, code_origine || ' - ' || libelle_origine FROM origine_contact ORDER BY code_origine"))
        com_ref = dict(db.fetchall("SELECT id_commune, nom_commune FROM commune ORDER BY nom_commune"))
        quart_ref = dict(db.fetchall("SELECT id_quartier, nom_quartier FROM quartier"))
        lieu_ref = dict(db.fetchall("SELECT id_lieu, nom_lieu FROM lieu_permanence"))
        part_ref = dict(db.fetchall("SELECT id_partenaire, nom_partenaire FROM partenaire"))
        dem_ref = dict(db.fetchall("SELECT nd.code_demande, nd.code_demande || ' - ' || nd.libelle_demande || ' (' || dd.libelle_domaine || ')' FROM nature_demande nd JOIN domaine_droit dd ON nd.code_domaine = dd.code_domaine ORDER BY nd.code_demande"))
        rep_ref = dict(db.fetchall("SELECT tr.code_reponse, tr.code_reponse || ' - ' || tr.libelle_reponse || ' (' || cr.libelle_cat_reponse || ')' FROM type_reponse tr JOIN categorie_reponse cr ON tr.code_cat_reponse = cr.code_cat_reponse ORDER BY tr.code_reponse"))
        max_num = db.fetchone("SELECT COALESCE(MAX(num_fiche_annuel), 0) + 1 FROM entretien")[0]
    db.close()

    with st.form("form_nouvel_entretien", clear_on_submit=True):
        st.markdown("**1. Cadre de l'entretien**")
        c1, c2, c3, c4, c5 = st.columns(5)
        f_num = c1.number_input("N° de fiche", min_value=1, value=int(max_num), step=1)
        f_date = c2.date_input("Date de l'entretien", value=date.today())
        f_mode = c3.selectbox("Mode d'entretien *", list(modes_ref.keys()), format_func=lambda k: modes_ref[k])
        f_duree = c4.selectbox("Durée", list(durees_ref.keys()), format_func=lambda k: durees_ref[k])
        f_lieu = c5.selectbox("Lieu de permanence", list(lieu_ref.keys()), format_func=lambda k: lieu_ref[k])

        st.markdown("**2. Profil de l'usager & Territoire**")
        u1, u2, u3, u4 = st.columns(4)
        f_sexe = u1.selectbox("Sexe / Type usager", list(sexes_ref.keys()), format_func=lambda k: sexes_ref[k])
        f_age = u2.selectbox("Tranche d'âge", list(ages_ref.keys()), index=2, format_func=lambda k: ages_ref[k])
        f_vp = u3.selectbox("Vient pour", list(vp_ref.keys()), format_func=lambda k: vp_ref[k])
        f_com = u4.selectbox(
            "Commune de domicile",
            list(com_ref.keys()),
            index=list(com_ref.values()).index("Vannes") if "Vannes" in com_ref.values() else 0,
            format_func=lambda k: com_ref[k],
        )

        u5, u6, u7, u8 = st.columns(4)
        quart_choices = [None] + list(quart_ref.keys())
        f_quart = u5.selectbox("Quartier QPV (si Vannes)", quart_choices, format_func=lambda k: "Aucun / Hors QPV" if k is None else quart_ref[k])
        f_sf = u6.selectbox("Situation familiale", list(sf_ref.keys()), format_func=lambda k: sf_ref[k])
        f_enfts = u7.number_input("Nb enfants à charge", min_value=0, max_value=15, value=0, step=1)
        f_mf = u8.selectbox("Modèle familial", list(mf_ref.keys()), index=3, format_func=lambda k: mf_ref[k])

        u9, u10, u11, u12 = st.columns(4)
        f_prof = u9.selectbox("Profession", list(prof_ref.keys()), index=5, format_func=lambda k: prof_ref[k])
        f_ress = u10.selectbox("Ressource principale", list(ress_ref.keys()), format_func=lambda k: ress_ref[k])
        f_orig = u11.selectbox("Repérage du dispositif (Origine)", list(orig_ref.keys()), format_func=lambda k: orig_ref[k])
        part_choices = [None] + list(part_ref.keys())
        f_part = u12.selectbox("Partenaire présent (optionnel)", part_choices, format_func=lambda k: "Aucun (Juriste Point Justice)" if k is None else part_ref[k])

        st.markdown("**3. Nature(s) de la demande & Réponse(s) apportée(s)**")
        d_sel1, d_sel2 = st.columns(2)
        f_dems = d_sel1.multiselect(
            "Demande(s) par ordre de priorité *",
            list(dem_ref.keys()),
            default=["1b"],
            format_func=lambda k: dem_ref[k],
        )
        f_reps = d_sel2.multiselect(
            "Réponse(s) / Orientation(s) apportée(s) *",
            list(rep_ref.keys()),
            default=["1"],
            format_func=lambda k: rep_ref[k],
        )

        submitted = st.form_submit_button("✅ Enregistrer l'entretien", type="primary")
        if submitted:
            if not f_dems or not f_reps:
                st.error("Veuillez sélectionner au moins une demande et une réponse.")
            else:
                db = get_db()
                payload = {
                    "num_fiche_annuel": int(f_num),
                    "date_entretien": f_date.isoformat(),
                    "annee": f_date.year,
                    "mois": f_date.month,
                    "date_estimee": 0,
                    "nb_enfants_charge": int(f_enfts),
                    "code_mode": f_mode,
                    "code_duree": f_duree,
                    "code_sexe": f_sexe,
                    "code_age": f_age,
                    "code_vient_pour": f_vp,
                    "code_sit_fam": f_sf,
                    "code_modele_fam": f_mf,
                    "code_prof": f_prof,
                    "code_ressource": f_ress,
                    "code_origine": f_orig,
                    "id_commune": f_com,
                    "id_quartier": f_quart,
                    "id_lieu": f_lieu,
                    "id_partenaire": f_part,
                }
                if db.is_https_supabase:
                    new_id = db.https.insert_one_returning("entretien", payload, "id_entretien")
                    db.https.insert_many("concerner", [{"id_entretien": new_id, "code_demande": cd, "ordre_demande": i} for i, cd in enumerate(f_dems, 1)])
                    db.https.insert_many("apporter", [{"id_entretien": new_id, "code_reponse": cr, "ordre_reponse": i} for i, cr in enumerate(f_reps, 1)])
                else:
                    new_id = db.insert_returning_id("""
                        INSERT INTO entretien (
                            num_fiche_annuel, date_entretien, annee, mois, date_estimee, nb_enfants_charge,
                            code_mode, code_duree, code_sexe, code_age, code_vient_pour,
                            code_sit_fam, code_modele_fam, code_prof, code_ressource, code_origine,
                            id_commune, id_quartier, id_lieu, id_partenaire
                        ) VALUES (?,?,?,?,0,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id_entretien
                    """, (
                        int(f_num), f_date.isoformat(), f_date.year, f_date.month, int(f_enfts),
                        f_mode, f_duree, f_sexe, f_age, f_vp,
                        f_sf, f_mf, f_prof, f_ress, f_orig,
                        f_com, f_quart, f_lieu, f_part
                    ))
                    for idx_d, code_d in enumerate(f_dems, 1):
                        db.execute("INSERT INTO concerner VALUES (?,?,?)", (new_id, code_d, idx_d))
                    for idx_r, code_r in enumerate(f_reps, 1):
                        db.execute("INSERT INTO apporter VALUES (?,?,?)", (new_id, code_r, idx_r))
                    db.commit()
                db.close()
                st.cache_data.clear()
                st.success(f"Entretien n°{f_num} enregistré.")
                st.rerun()

with tab_afc:
    st.subheader("Analyse Factorielle des Correspondances (AFC) : Profils des appelants")
    var_profil = st.selectbox(
        "Variable de profil à croiser avec les Domaines de droit :",
        ["age", "ressource", "profession", "epci"],
        format_func=lambda x: {
            "age": "Tranche d'âge de l'usager",
            "ressource": "Type de ressource principale",
            "profession": "Catégorie socioprofessionnelle",
            "epci": "Territoire (EPCI)",
        }[x],
    )

    if len(df_f) > 0 and len(dem_f) > 0:
        df_merge_afc = dem_f.merge(df_f[["id_entretien", var_profil]], on="id_entretien")
        df_merge_afc = df_merge_afc[~df_merge_afc[var_profil].isin(["Non renseigné"])].dropna()

        ct = pd.crosstab(df_merge_afc[var_profil], df_merge_afc["libelle_domaine"])
        if ct.shape[0] >= 3 and ct.shape[1] >= 3:
            N = ct.values.sum()
            P = ct.values / N
            r = P.sum(axis=1, keepdims=True)
            c_vec = P.sum(axis=0, keepdims=True)
            S = (P - r @ c_vec) / np.sqrt(r @ c_vec)
            U, s_vals, Vt = np.linalg.svd(S, full_matrices=False)
            eig = s_vals ** 2
            inertia = eig / eig.sum() * 100

            row_coords = (U[:, :2] * s_vals[:2]) / np.sqrt(r)
            col_coords = (Vt[:2, :].T * s_vals[:2]) / np.sqrt(c_vec.T)

            fig_afc = go.Figure()
            fig_afc.add_trace(go.Scatter(
                x=row_coords[:, 0], y=row_coords[:, 1],
                mode="markers+text",
                text=ct.index.tolist(),
                textposition="top center",
                marker=dict(size=12, color="#1E3A5F", symbol="circle"),
                name="Profils usagers",
            ))
            fig_afc.add_trace(go.Scatter(
                x=col_coords[:, 0], y=col_coords[:, 1],
                mode="markers+text",
                text=ct.columns.tolist(),
                textposition="bottom center",
                marker=dict(size=12, color="#D9534F", symbol="diamond"),
                name="Domaines de droit",
            ))
            fig_afc.add_hline(y=0, line_dash="dash", line_color="grey", opacity=0.5)
            fig_afc.add_vline(x=0, line_dash="dash", line_color="grey", opacity=0.5)
            fig_afc.update_layout(
                title=f"Plan factoriel AFC (Axes 1 & 2 = {inertia[0]+inertia[1]:.1f}% de l'inertie totale)",
                xaxis_title=f"Axe 1 ({inertia[0]:.1f}%)",
                yaxis_title=f"Axe 2 ({inertia[1]:.1f}%)",
                height=520,
            )
            st.plotly_chart(fig_afc, use_container_width=True)

            with st.expander("Voir le tableau de contingence croisé (effectifs)"):
                st.dataframe(ct, use_container_width=True)
        else:
            st.warning("Pas assez de modalités après filtrage pour calculer le plan factoriel.")
    else:
        st.info("Aucune donnée disponible pour calculer l'AFC.")

with tab_export:
    st.subheader("Export Excel (.xlsx) des données et synthèses")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_f.to_excel(writer, sheet_name="Entretiens", index=False)
        dem_f.to_excel(writer, sheet_name="Demandes", index=False)
        rep_f.to_excel(writer, sheet_name="Reponses", index=False)
        if len(dem_f) > 0:
            (
                dem_f.groupby("libelle_domaine", as_index=False)
                .size()
                .rename(columns={"size": "Nb_Demandes"})
                .to_excel(writer, sheet_name="Synthese_Domaines", index=False)
            )
        if len(df_f) > 0:
            (
                df_f.groupby(["epci", "commune"], as_index=False)
                .size()
                .rename(columns={"size": "Nb_Entretiens"})
                .to_excel(writer, sheet_name="Synthese_Territoires", index=False)
            )

    st.download_button(
        label=" Télécharger l'export Excel (.xlsx)",
        data=output.getvalue(),
        file_name="Bilan_Maison_du_Droit_Vannes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )

    if len(df_f) > 0:
        st.dataframe(df_f.head(50), use_container_width=True, hide_index=True)

with tab_qualite:
    st.subheader("️ Journal d'audit ETL : Valeurs atypiques détectées")
    if len(df_anom) > 0:
        a1, a2 = st.columns(2)
        with a1:
            st.markdown("**Synthèse par champ et valeur constatée**")
            synth_a = (
                df_anom.groupby(["colonne", "valeur_brute", "type_anomalie"], as_index=False)
                .size()
                .rename(columns={"size": "Occurrences"})
                .sort_values("Occurrences", ascending=False)
            )
            st.dataframe(synth_a, use_container_width=True, hide_index=True)

        with a2:
            st.markdown("**Détail des lignes à vérifier**")
            filtre_col_a = st.selectbox("Filtrer par champ :", ["Toutes"] + sorted(df_anom["colonne"].unique().tolist()))
            sub_a = df_anom if filtre_col_a == "Toutes" else df_anom[df_anom["colonne"] == filtre_col_a]
            cols_disp = [c for c in ["onglet", "cellule_excel", "num_fiche", "colonne", "valeur_brute", "commentaire"] if c in sub_a.columns]
            st.dataframe(sub_a[cols_disp], use_container_width=True, hide_index=True)

        csv_bytes = df_anom.to_csv(sep=";", index=False).encode("utf-8-sig")
        st.download_button(
            label=" Télécharger le suivi des valeurs atypiques (.csv)",
            data=csv_bytes,
            file_name="valeurs_atypiques_a_verifier.csv",
            mime="text/csv",
            type="primary",
        )
    else:
        st.info("Aucune valeur atypique en attente de vérification.")