"""NQ Scalp Lab – point d'entrée et navigation.

Lancer : streamlit run app.py

Les fichiers des pages ont des noms ASCII (sans emoji ni accent) pour éviter les noms
illisibles après décompression sous Windows ; titres et icônes sont définis ici.
"""
import streamlit as st

PAGES = [
    st.Page("pages/0_cockpit.py", title="Cockpit", icon="🎯", default=True),
    st.Page("pages/1_plan_de_seance.py", title="Plan de séance", icon="📍"),
    st.Page("pages/2_bougies_mmm.py", title="Bougies MMM", icon="🕯️"),
    st.Page("pages/3_ict_warren.py", title="ICT & Warren", icon="🧱"),
    st.Page("pages/4_intermarche.py", title="Intermarché", icon="🌐"),
    st.Page("pages/5_macro_news.py", title="Macro & News", icon="📰"),
    st.Page("pages/6_meilleur_jour_heure.py", title="Meilleur jour & heure", icon="⏰"),
    st.Page("pages/7_labo_statistique.py", title="Labo statistique", icon="🔬"),
    st.Page("pages/8_previsions.py", title="Prévisions", icon="🔮"),
    st.Page("pages/9_risque_apex_journal.py", title="Risque Apex & Journal", icon="🛡️"),
    st.Page("pages/10_methode.py", title="Méthode & bonnes pratiques", icon="📘"),
]

st.navigation(PAGES).run()
