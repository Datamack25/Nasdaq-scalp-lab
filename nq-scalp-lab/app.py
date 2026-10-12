"""NQ Scalp Lab – point d'entrée et navigation.

Lancer : streamlit run app.py

Les pages sont dans le dossier « views » (et non « pages ») : avec un dossier « pages »,
Streamlit réactive son ancienne navigation automatique quand on ouvre directement l'URL
d'une page. Les noms de fichiers sont en ASCII pour rester lisibles sous Windows ;
titres et icônes sont définis ici.
"""
import streamlit as st

PAGES = [
    st.Page("views/0_cockpit.py", title="Cockpit", icon="🎯", default=True),
    st.Page("views/1_plan_de_seance.py", title="Plan de séance", icon="📍"),
    st.Page("views/2_bougies_mmm.py", title="Bougies MMM", icon="🕯️"),
    st.Page("views/3_ict_warren.py", title="ICT & Warren", icon="🧱"),
    st.Page("views/4_intermarche.py", title="Intermarché", icon="🌐"),
    st.Page("views/5_macro_news.py", title="Macro & News", icon="📰"),
    st.Page("views/6_meilleur_jour_heure.py", title="Meilleur jour & heure", icon="⏰"),
    st.Page("views/7_labo_statistique.py", title="Labo statistique", icon="🔬"),
    st.Page("views/8_previsions.py", title="Prévisions", icon="🔮"),
    st.Page("views/9_risque_apex_journal.py", title="Risque Apex & Journal", icon="🛡️"),
    st.Page("views/10_methode.py", title="Méthode & bonnes pratiques", icon="📘"),
]

st.navigation(PAGES).run()
