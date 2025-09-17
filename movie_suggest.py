# movie_app.py
import streamlit as st
import pandas as pd
import re, difflib, os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from streamlit_option_menu import option_menu

st.set_page_config(page_title="🎬 MovieSense", page_icon="🎥", layout="wide")

# -----------------------
# Load data
# -----------------------
@st.cache_data
def load_data(path="movie_dataset_500_real_posters (1).csv"):
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    for col in ['MovieTitle','Genre','Year','Rating','PosterURL']:
        df[col] = df.get(col, pd.NA)

    df['MovieTitle'] = df['MovieTitle'].astype(str).str.strip()
    df['Genre'] = df['Genre'].astype(str).fillna("").str.strip()
    df['Year'] = pd.to_numeric(df['Year'], errors='coerce').astype('Int64')
    df['Rating_num'] = pd.to_numeric(df['Rating'], errors='coerce')

    cols = ['MovieTitle','Genre','Year'] + (['Overview'] if 'Overview' in df else [])
    df['Combined'] = df[cols].astype(str).agg(' '.join, axis=1)
    return df

df = load_data()

# -----------------------
# Genres + similarity
# -----------------------
def build_genres(df):
    genres = set()
    for g in df['Genre'].dropna():
        tokens = [t.strip().lower() for t in re.split(r'[,\|/;]', str(g)) if t.strip()]
        genres.update(tokens)
    return genres

GENRES = build_genres(df)

@st.cache_data
def build_similarity(series):
    vect = TfidfVectorizer(stop_words="english", max_features=20000)
    mat = vect.fit_transform(series)
    return cosine_similarity(mat)

SIM_MATRIX = build_similarity(df['Combined'])

# -----------------------
# Helpers
# -----------------------
def dedupe(df_sub):
    return (df_sub.sort_values("Rating_num", ascending=False, na_position="last")
                  .drop_duplicates("MovieTitle"))

def match_genre(q):
    q = q.lower().strip()
    if q in GENRES: return q
    close = difflib.get_close_matches(q, list(GENRES), n=1, cutoff=0.6)
    return close[0] if close else next((g for g in GENRES if q in g), None)

def get_index(title):
    q = title.lower().strip()
    matches = df[df['MovieTitle'].str.lower().str.contains(q, na=False)]
    if not matches.empty: return matches.index[0]
    close = difflib.get_close_matches(title, df['MovieTitle'], n=1, cutoff=0.6)
    return df[df['MovieTitle']==close[0]].index[0] if close else None

def recommend(query, top_n=10):
    if query.isdigit():   # year
        res = df[df['Year']==int(query)]
    elif (g := match_genre(query)):  # genre
        res = df[df['Genre'].str.lower().str.contains(g, na=False)]
    elif (idx := get_index(query)) is not None:  # title
        sim_scores = sorted(enumerate(SIM_MATRIX[idx]), key=lambda x: x[1], reverse=True)
        res = df.iloc[[i for i,_ in sim_scores[1:top_n+1]]]
    else:
        return pd.DataFrame()
    return dedupe(res)[['MovieTitle','Genre','Year','Rating','PosterURL']]

def show_movie(r):
    col1,col2 = st.columns([1,3])
    with col1:
        if pd.notna(r['PosterURL']) and str(r['PosterURL']).startswith("http"):
            st.image(r['PosterURL'], width=150)
        else: st.text("Poster not available")
    with col2:
        st.markdown(f"### {r['MovieTitle']} ({r['Year']})")
        st.write(f"**Genre:** {r['Genre']} | **Rating:** {r['Rating']}")

# -----------------------
# Sidebar menu
# -----------------------
def menu():
    with st.sidebar:
        return option_menu("MovieSense", ["Home","Recommendation","Dataset","About"],
                           icons=["house","search","table","info-circle"], menu_icon="film")

page = menu()

# -----------------------
# Pages
# -----------------------
if page=="Home":
    st.title("🎬 MovieSense")
    st.markdown("Use **Recommendation** to search by title, genre, or year.")
    for _,r in df.drop_duplicates("MovieTitle").head(6).iterrows():
        show_movie(r); st.markdown("---")

elif page=="Recommendation":
    q = st.text_input("Search (title / genre / year)")
    if st.button("Search") and q:
        recs = recommend(q)
        st.subheader(f"Results for: {q}")
        if recs.empty: st.warning("No movies found.")
        else:
            for _,r in recs.iterrows(): show_movie(r); st.markdown("---")

elif page=="Dataset":
    show_df = df[['MovieTitle','Genre','Year','Rating','PosterURL']].drop_duplicates("MovieTitle")
    st.dataframe(show_df, use_container_width=True)
    st.download_button("Download CSV", show_df.to_csv(index=False), "movies_clean.csv")

elif page=="About":
    st.markdown("""
    **MovieSense** is a student project:  
    - Content-based recommender (TF-IDF + cosine similarity)  
    - Search by title, genre (fuzzy), or year  
    - Deduplicates by rating  
    - UI built with Streamlit  
    """)
