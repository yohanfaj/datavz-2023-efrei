import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from wordcloud import WordCloud

#####################
# DATA PREPARATION  #
#####################

# We load the data from the API
url = "https://www.data.gouv.fr/api/1/datasets/films-ayant-realise-plus-dun-million-dentrees/"
response = requests.get(url)
data = response.json()
df_dict = pd.read_excel(data["resources"][0]["extras"]["check:url"], sheet_name=None, skiprows=5,
                        header=1)

# For some sheets,we have to explicitly rename the ranking column
for sheet_name, df in df_dict.items():
    if "Unnamed: 0" in df.columns:
        df.rename(columns={df.columns[0]: "rang"}, inplace=True)

# We drop useless sheets, and concatenate all the remaining ones
df_dict.pop("Sommaire")
df_dict.pop("ESRI_MAPINFO_SHEET")
df = pd.concat(df_dict.values(), ignore_index=True)

# We convert "sortie" to datetime and without the hour
df["sortie"] = pd.to_datetime(df["sortie"], format="%d/%m/%Y")

# ENCODING OF NATIONALITIES
# We convert all nationalities to uppercase
df["nationalité"] = df["nationalité"].str.upper()

# We map all nationalities to a code
nationality_mapping = {
    'ETATS UNIS': 'US',
    'USA': 'US',
    'US': 'US',

    'GRANDE BRETAGNE': 'GB',
    'GB': 'GB',
    'FRANCE': 'FR',
    'FR': 'FR',

    'CANADA': 'CA',
    'CA': 'CA',
    'AUSTRALIE': 'AU',
    'AU': 'AU',
    'COREE DU SUD': 'KS',
    'KS': 'KS',

    'ITALIE': 'IT',
    'IT': 'IT',
    'MAROC': 'MA',
    'NOUVELLE ZELANDE': 'NZ',
    'ALLEMAGNE': 'DE',
    'DE': 'DE',
    'BELGIQUE': 'BE',
    'BE': 'BE',

    'LUXEMBOURG': 'LUX',
    'LUX': 'LUX',
    'REPUBLIQUE TCHEQUE': 'CZ',
    'HONGRIE': 'HU',
    'ESPAGNE': 'ES',
    'ROUMANIE': 'RO',
    'SUEDE': 'SE',
    'SUISSE': 'CH',
    'PAYS-BAS': 'NL'
}


# We apply the mapping to encode the nationalities
def encode_nationality(value):
    # Split values by '/' and map each component
    countries = value.split('/')
    countries = [nationality_mapping.get(country.strip(), country) for country in countries]
    return ' / '.join(countries)


# We replace all nationalities
df['nationalité'] = df['nationalité'].apply(encode_nationality)

# We rename the entrées column
df.rename(columns={"entrées (millions)": "entrées"}, inplace=True)

# We copy the dataframe to keep the original one and present it in the home page
df_original = df.copy()

# We now need to work on duplicate movies
# Indeed, some successful movies, released by the end of the year, are featured twice in the dataset:
# one time in the year of release, and one time in the following year.
# For example, Avatar was released in December 2009, so it has performed both in 2009 and 2010.
# As such, I have decided to consider this type of movie only in its year of release, but with its cumulated entries.

# To do so, we group the dataframe by title and sum the entries
df = df.groupby("titre").agg({"entrées": "sum", "nationalité": "first", 'sortie': "first"}) \
    .sort_values(by="entrées", ascending=False).reset_index()


###########################################################################################################


########################################
# PREPARATION OF EACH PERIOD DATAFRAME #
########################################

# 2000s DataFrame
df_2000s = df[df["sortie"].dt.year.between(2000, 2009)].groupby("titre").agg(
    {"entrées": "sum", "nationalité": "first", 'sortie': "first"}) \
    .sort_values(by="entrées", ascending=False).reset_index()

# 2010s DataFrame
df_2010s = df[df["sortie"].dt.year.between(2010, 2019)].groupby("titre").agg(
    {"entrées": "sum", "nationalité": "first", 'sortie': "first"}) \
    .sort_values(by="entrées", ascending=False).reset_index()

# 2020s DataFrame
df_2020s = df[df["sortie"].dt.year.between(2020, pd.to_datetime("now").year)].groupby("titre").agg(
    {"entrées": "sum", "nationalité": "first", 'sortie': "first"}) \
    .sort_values(by="entrées", ascending=False).reset_index()


##########################
# VISUALIZATION FUNCTIONS
##########################

def plot_all_movies(data, title):
    fig = px.bar(data, x="titre", y="entrées", title=title)
    fig.update_layout(
        width=1200,
        height=800,
        xaxis_title="Movie",
        yaxis_title="Entries")
    st.plotly_chart(fig)


def plot_entrees_evolution(data, title):
    fig = px.histogram(data, x="sortie", y="entrées", title=title)
    fig.update_layout(
        width=1200,
        height=800,
        xaxis_title="Year",
        yaxis_title="Entries")
    fig.update_traces(marker=dict(line=dict(color='black', width=1.5)))
    st.plotly_chart(fig)


def plot_nb_movies_evolution(data, decade, title):
    # We first count the number of movies released in a specific decade
    if decade == "all-time":
        nb_movies = data["sortie"].dt.year.value_counts().sort_index()
    elif decade == 2020:
        nb_movies = data["sortie"][data["sortie"].dt.year.between(decade, pd.to_datetime("now").year)] \
            .dt.year.value_counts().sort_index()
    else:
        nb_movies = data["sortie"][
            data["sortie"].dt.year.between(decade, decade + 9)].dt.year.value_counts().sort_index()

    # We plot the histogram of the number of released movies in the decade
    fig = px.bar(nb_movies, x=nb_movies.index, y=nb_movies.values,
                 title=title)
    fig.update_layout(
        width=1200,
        height=800,
        xaxis_title="Year",
        yaxis_title="Number of movies")
    fig.update_traces(marker=dict(line=dict(color='black', width=1.5)))
    st.plotly_chart(fig)


def plot_nationalites_distribution(data, title):
    # We want to display the 10 highest distribution of nationalities
    top_10_nat = data.groupby("nationalité").agg({"entrées": "sum"}).sort_values(by="entrées", ascending=False).head(10)

    # We plot the pie chart
    fig = px.pie(top_10_nat, values="entrées", names=top_10_nat.index, title=title)
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(
        width=1200,
        height=800)
    st.plotly_chart(fig)


def plot_movies_word_cloud(data):
    # We remove the articles and the most common words
    movies = data["titre"].str.replace("(LES)", "").str.replace("(LE) ", "").str.replace("(LA) ", ""). \
        str.replace("LES", "").str.replace("DU", "").str.replace("DE", "").str.replace("DES", "").str.replace("LE", "") \
        .str.replace("LA", "").str.replace("L'", "").str.replace("AU", "").str.replace("UN", "").str.replace("ET ","").str.strip()

    # We create the word cloud
    wordcloud = WordCloud(width=600, height=400, background_color='white', min_font_size=10).generate(
        ' '.join(movies))
    st.image(wordcloud.to_image())


#################################################################################################################
#################################################################################################################


#########################
# STREAMLIT PAGINATION #
#########################

st.set_page_config(layout="wide")

st.sidebar.title("MENU NAVIGATION")
page = st.sidebar.selectbox(
    "Choose a period :",
    ("HOME",
     "ALL TIME",
     "2000s",
     "2010s",
     "2020s")
)

st.sidebar.markdown("""----------------------------------""")

st.sidebar.markdown("""
A project proposed by **Yohan Fajerman**, M1 BIA student at *Efrei Paris* :owl:
\nYou can find me on [LinkedIn](https://www.linkedin.com/in/yohan-fajerman/)
and [GitHub](https://github.com/yohanfaj/) ! :computer:
\n__*#datavz2023efrei*__
""")

st.sidebar.image("logo_efrei.png", width=200)

#########################
# STREAMLIT HOME PAGE   #
#########################

if page == "HOME":
    st.toast("Home page !", icon="🍿")
    st.title("Analysis of Movies with more than 1 Million Entries in France :popcorn:")

    st.markdown(""" 
     ### From data delivered by the CNC and available on [data.gouv.fr](https://www.data.gouv.fr/fr/datasets/films-ayant-realise-plus-dun-million-dentrees/) :flag-fr:
     The studied dataset consists of movies that have made more than 1 million entries in France **each year 
     from today to 2003**, and ranked in **order of entries**:
    """)
    st.write(df)

    st.markdown("""
    _N.B. : Note that this dataset also contains three millionaire movies released before 2003:_
    """)
    st.write(df[df["sortie"] < pd.to_datetime("2003")])

    st.markdown("""
    #### Through the analysis, we will call movies that have made more than 1M entries in France under the term of *"millionaire movies"*.
    ### Use the menu navigation on the left to choose an analysis of different time periods.
    """)


############################################################################################################


#######################
# ALL TIME ANALYSIS  #
#######################

if page == "ALL TIME":
    st.toast("All Time Movies !", icon="🍿")
    st.title("All Time Millionaire Movies in France")
    st.write("A dataset of {} movies, ranked by number of entries: ".format(df.shape[0]))
    st.write(df)

    st.header("We plot all these movies.")
    st.subheader("You can interact with the graph to focus on a specific region.")

    # ALL TIME PLOT
    plot_all_movies(df, "All Time Millionaire Movies in France")


    # EVOLUTION OF ENTRIES THROUGH THE YEARS
    st.markdown("""----------------------------------""")
    st.header("How does the number of entries evolve through the 21st century?")
    st.bar_chart(df["sortie"].dt.year.value_counts().sort_index())

    st.markdown("""
    The years 2009, 2011, 2014, 2017 and 2018 have known the best entries in France **(+120M !)**.
    \n However because of the pandemic, 2020 and 2021 are ones of the worst years.
    \n We will focus more on these in the decade analysis. :wink:
    """)

    # NUMBER OF MOVIES PER YEAR
    st.header("How many millionaire movies are released each year?")
    plot_nb_movies_evolution(df, "all-time", "Number of movies that have made more than 1 million entries per year")

    st.markdown("""
    We can notice that **the number of millionaire movies per year influence the number of entries**: 
    * The most successful years has seen around **50 millionaire movies**,
    * Some of the worst successful years barely reach **half of this number**.
    """)


    # NUMBER OF MILLIONAIRE MOVIES PER DECADE
    st.header("And how many per decade?")
    nb_decade_movies = pd.DataFrame([df_2000s.shape[0], df_2010s.shape[0], df_2020s.shape[0]],
                                    index=["2000s", "2010s", "2020s"], columns=["Number of movies"])
    st.bar_chart(nb_decade_movies)

    st.markdown("""
    The most exciting years in terms of quantity of millionaire movies are **the 2010s** with **{} movies**!
    \nThis result may however be a bit biased :
    * The 2000s data lacks almost 3 years, from 2000 to 2003
    * For the 2020s, as we have only 3 years of data for this decade (with already **{} movies**).
    As such, the 2010s is for sure the most complete decade.
    """.format(df_2010s.shape[0], df_2020s.shape[0]))


    # NATIONALITIES OF MILLIONAIRE MOVIES
    st.markdown("""----------------------------------""")
    st.header("What are the countries' films that have made the most entries in France?")
    plot_nationalites_distribution(df, "Nationalities of All Time Millionaire Movies")

    st.markdown("""
    The United States cumulate more than **a billion entries** in France through the 21st century. :exploding_head:
    \nAs for French movies (individual or collaborating with other countries), they account for
     **more than 575 million entries**. :flag-fr:
    """)


############################################################################################################


####################
# 2000s ANALYSIS  #
####################

if page == "2000s":
    st.toast("2000s Movies !", icon="🍿")
    st.title("2000's Millionaire Movies in France")
    st.write("A dataset of {} movies, ranked by number of entries: ".format(df_2000s.shape[0]))
    st.write(df_2000s)

    st.header("We plot all these movies.")
    st.subheader("You can interact with the graph to focus on a specific region.")

    # 2000s PLOT
    plot_all_movies(df_2000s, "2000's Millionaire Movies in France")


    # ENTRIES & NUMBER OF MOVIES HISTOGRAMS
    st.markdown("""----------------------------------""")
    st.header("How does the number of entries, and the number of released millionaire movies, evolve through the 2000s?")

    col1, col2 = st.columns([0.6, 0.4])
    with col1:
        plot_entrees_evolution(df_2000s, "Evolution of the entries through the years in the 2000s")
    with col2:
        plot_nb_movies_evolution(df_2000s, 2000,
                                 "Number of movies that have made more than 1 million entries per year in the 2000s")

    st.markdown("""
    The best years of the 2000s are **Semester 1 of 2004, Semester 1 of 2006, and Semester 2 of 2009**: **+60M entries 
    cumulated for each one!**
    
    \nBesides, the 2000s is full of millionaire films: with the exception of 2007, there are **more than 40 movies per 
    year reaching +1M entries**.
    \nHere are the best performing movies released by this time:
    """)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(
            df[(df["sortie"] >= pd.to_datetime("2003-12-01")) & (df["sortie"] <= pd.to_datetime("2004-06-30"))].head(3))
    with col2:
        st.write(
            df[(df["sortie"] >= pd.to_datetime("2005-12-01")) & (df["sortie"] <= pd.to_datetime("2006-06-30"))].head(3))
    with col3:
        st.write(
            df[(df["sortie"] >= pd.to_datetime("2009-06-01")) & (df["sortie"] <= pd.to_datetime("2009-12-31"))].head(3))


    # WORD CLOUD OF 2000s MOVIES
    st.markdown("""----------------------------------""")
    st.header("\nWhat are the most common words / themes of the 2000s movies?")
    plot_movies_word_cloud(df_2000s)

    st.markdown("""
    The main 2000s franchise are *Asterix, Arthur & The Minimoys, Harry Potter, Pirates of the Caribbean, Madagascar,
     Matrix, and Shrek.*
    \n We also have movies with the themes of **"SECRET", "JOUR", "VIE", and "MONDE"** in their titles: 
    """)

    col1, col2 = st.columns(2)
    with col1:
        st.write(df_2000s[df_2000s["titre"].str.contains("SECRET")].sort_values("titre"))
    with col2:
        st.write(df_2000s[df_2000s["titre"].str.contains("JOUR")].sort_values("titre"))

    col3, col4 = st.columns(2)
    with col3:
        st.write(df_2000s[df_2000s["titre"].str.contains("VIE")].sort_values("titre"))
    with col4:
        st.write(df_2000s[df_2000s["titre"].str.contains("MONDE")].sort_values("titre"))

    st.markdown("There are also some **franchise's chapters** of movies in the 2000s:")
    st.write(df_2000s[df_2000s["titre"].str.contains("CHAPITRE")].sort_values("titre"))


    # DISTRIBUTION OF 2000S NATIONALITIES
    st.markdown("""----------------------------------""")
    st.header("\nWhat are the countries' films that have made the most entries in France in the 2000s?")
    plot_nationalites_distribution(df_2000s, "Nationalities of 2000s Millionaire Movies")

    st.markdown("""
    Overall, United States and France trust the charts : **+500M tickets cumulated!**
    \nYet there is a significant part of popular **Great Britain** movies, with around **60M tickets**. :flag-gb:
    \nThis may be possible thanks to the popularity of the *Harry Potter* saga: 
    """)
    st.write(df_2000s[df_2000s["nationalité"] == "GB"].head())


    # CULT MOVIES OF THE 2000s
    st.markdown("""----------------------------------""")
    st.header("\nFinally, what are the cult movies of the 2000s? :popcorn:")
    st.subheader("French Movies :flag-fr:")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.video("https://youtu.be/OycTfchnopU?si=6HsktRogw5kbN1Ar")
    with col2:
        st.video("https://youtu.be/U6TRsXveaoM?si=lLlu4PJjdQpNcAQ4")
    with col3:
        st.video("https://youtu.be/qJeKKd0gPiU?si=NQZS-25cXe2EjJEA")

    st.subheader("International Movies :earth_africa:")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.video("https://youtu.be/5PSNL1qE6VY?si=7jz1xX9uQ9qX5O4l")
    with col2:
        st.video("https://youtu.be/CLncEeVf4ks?si=UuJLDtvCcZaSL4Pr")
    with col3:
        st.video("https://youtu.be/6-NGPgX-uYA?si=CjOxbDrvum8yHdgZ")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.video("https://youtu.be/kYzz0FSgpSU?si=sUKdkwwu6zKlCejo")
    with col2:
        st.video("https://youtu.be/CwXOrWvPBPk?si=CMtEKMa0eX7ZCXxW")
    with col3:
        st.video("https://youtu.be/orAqhC-Hp_o?si=eR1mQ6v0JXs3Ztvt")


############################################################################################################

####################
# 2010s ANALYSIS  #
####################

if page == "2010s":
    st.toast("2010s Movies !", icon="🍿")
    st.title("2010's Millionaire Movies in France")
    st.write("A dataset of {} movies, ranked by number of entries: ".format(df_2010s.shape[0]))
    st.write(df_2010s)

    st.header("We plot all these movies.")
    st.subheader("You can interact with the graph to focus on a specific region.")

    # 2010s PLOT
    plot_all_movies(df_2010s, "2010's Millionaire Movies in France")


    # ENTRIES & NUMBER OF MOVIES HISTOGRAMS
    st.markdown("""----------------------------------""")
    st.header("How does the number of entries, and the number of released millionaire movies, evolve through the 2010s?")

    col1, col2 = st.columns([0.6, 0.4])
    with col1:
        plot_entrees_evolution(df_2010s, "Evolution of the entries through the years in the 2010s")
    with col2:
        plot_nb_movies_evolution(df_2010s, 2010,
                                 "Number of movies that have made more than 1 million entries per year in the 2010s")

    st.markdown("""
    While the 2010s are in a really good shape, with years reaching 50M to 60M cumulated entries, the second semester of 2011
    reaches a whopping **75M entries** by itself!
    \n2011 is also a year that has seen a great number of millionaire movies, like 2016 and 2017, with **53 movies**.
    The 2 best years in terms of quantity are actually 2013 & 2014, with respectively **56 and 55 movies**.
    \nHere are the best performing movies released by these years:
    """)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(
            df[(df["sortie"] >= pd.to_datetime("2011-06-01")) & (df["sortie"] <= pd.to_datetime("2011-12-31"))].head(3))
    with col2:
        st.write(
            df[(df["sortie"] >= pd.to_datetime("2013-01-01")) & (df["sortie"] <= pd.to_datetime("2013-12-31"))].head(3))
    with col3:
        st.write(
            df[(df["sortie"] >= pd.to_datetime("2014-01-01")) & (df["sortie"] <= pd.to_datetime("2014-12-31"))].head(3))


    # WORD CLOUD OF 2010s MOVIES
    st.markdown("""----------------------------------""")
    st.header("\nWhat are the most common words / themes of the 2010s movies?")
    plot_movies_word_cloud(df_2010s)

    st.markdown("""
    \nSome of the main franchises of the 2010s are *Avengers, Star Wars, La Reine des Neiges, Les Schtroumpfs,
    Les Animaux Fantastiques, Hunger Games, and Fast & Furious*.
    """)

    st.markdown("""
    \nAlso within the 2010s movies _(and by considering the cut of some articles in the word cloud)_,
     we retrieve the themes of **"MONDE", "AVENTURE", "VOYAGE", "SECRET" and "DERNIER"**:
    """)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(df_2010s[df_2010s["titre"].str.contains("MONDE")].sort_values("titre"))
    with col2:
        st.write(df_2010s[df_2010s["titre"].str.contains("AVENTURE")].sort_values("titre"))
    with col3:
        st.write(df_2010s[df_2010s["titre"].str.contains("VOYAGE")].sort_values("titre"))

    col4, col5 = st.columns(2)
    with col4:
        st.write(df_2010s[df_2010s["titre"].str.contains("DERNIER")].sort_values("titre"))
    with col5:
        st.write(df_2010s[df_2010s["titre"].str.contains("SECR")].sort_values("titre"))

    st.markdown("""
    \nLike in the 2000s, there are also some **franchise's chapters** of movies in the 2010s:
    """)
    st.write(df_2010s[df_2010s["titre"].str.contains("CHAPITRE")].sort_values("titre"))
    st.markdown("We can notice here that the *Narnia* and *Twilight* sagas are continuing in the 2010s.")


    # DISTRIBUTION OF 2010S NATIONALITIES
    st.markdown("""----------------------------------""")
    st.header("\nWhat are the countries' films that have made the most entries in France in the 2010s?")
    plot_nationalites_distribution(df_2010s, "Nationalities of 2010s Millionaire Movies")

    st.markdown("""
    Again, the vast majority of entries are performed by **American & French** movies (almost **1B** tickets 
    cumulated! :exploding_head:).
    \nStill **British** movies perfoms well with **89M** entries, thanks to the *Harry Potter* & *James Bond saga* :flag-gb:
    """)
    st.write(df_2010s[df_2010s["nationalité"] == "GB"].head())

    st.markdown("""
    Moreover, there is a quite significant part of **Franco-Belgian** movies, cumulating more than **56M** entries.
    These movies are mainly *comedies* co-produced by the two countries. :flag-be:
    """)
    st.write(df_2010s[df_2010s["nationalité"] == "FR / BE"].head())


    # CULT MOVIES OF THE 2010s
    st.markdown("""----------------------------------""")
    st.header("\nFinally, what are the cult movies of the 2010s? :popcorn:")

    st.subheader("French Movies :flag-fr:")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.video("https://youtu.be/cXu2MhWYUuE?si=9oN9qntjCBT-ArsI")
    with col2:
        st.video("https://youtu.be/xONVqPzEqRM?si=Qrl-abrgiHBl2wkp")
    with col3:
        st.video("https://youtu.be/QerOPic11Tk?si=kndSZrKfgkVgx6Dd")
    with col4:
        st.video("https://youtu.be/tEgw97vpkDM?si=YKvp5SD1ppIlxa5q")

    st.subheader("International Movies :earth_africa:")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.video("https://youtu.be/TcMBFSGVi1c?si=eAvRIxIyeSPqnEj4")
    with col2:
        st.video("https://youtu.be/sGbxmsDFVnE?si=OjChoPQy8H0wOs6P")
    with col3:
        st.video("https://youtu.be/TbQm5doF_Uc?si=ePurD4TY70Hx1jTn")

    col4, col5, col6 = st.columns(3)
    with col4:
        st.video("https://youtu.be/zzCZ1W_CUoI?si=w4yVqE5IKtkI1ZR2")
    with col5:
        st.video("https://youtu.be/6kw1UVovByw?si=tmfokhbUi9QrdEuY")
    with col6:
        st.video("https://youtu.be/mObK5XD8udk?si=BW6hnJ1AfKy0tliu")


############################################################################################################


####################
#  2020s ANALYSIS  #
####################

if page == "2020s":
    st.toast("2020s Movies !", icon="🍿")
    st.title("2020's Millionaire Movies in France")
    st.write("A dataset of {} movies, ranked by number of entries: ".format(df_2020s.shape[0]))
    st.write(df_2020s)

    st.warning("""
    :warning: This analysis was performed in *October 2023*, with only 3 years of data.
    \nAs such, **the 2020s dataset is not complete yet!**, and the results of the analysis may *vary* as time goes!
     :warning:""")

    st.header("We plot all these movies.")
    st.subheader("You can interact with the graph to focus on a specific region.")

    # 2020s PLOT
    plot_all_movies(df_2020s, "2020's Millionaire Movies in France")


    # ENTRIES & NUMBER OF MOVIES HISTOGRAMS
    st.markdown("""----------------------------------""")
    st.header("How does the number of entries, and the number of released millionaire movies, evolve through the 2020s?")

    col1, col2 = st.columns([0.7, 0.3])
    with col1:
        plot_entrees_evolution(df_2020s, "Evolution of the entries through the years in the 2020s")
    with col2:
        plot_nb_movies_evolution(df_2020s, 2020,
                                 "Number of movies that have made more than 1 million entries per year in the 2020s")

    st.markdown("""
    At the time of the analysis (10/2023, 3 years of data), the entries in the 2000s are really bad, barely reaching
    over 40M cumulated entries in a semester at its maximum.
    This is entirely correlated with the *COVID-19 crisis*: :mask:
    * In 2020, while the first three months as well as the summer may have seen some entries, the year does not exceed
    **20M entries**
    * The first semester of 2021 is even worse with only **3M entries*, surely because of the *2nd lockdown* in France 
    (From Winter 2020 to Spring 2021).
    * Since the 2nd semester of 2021, entries in cinema are slowly recovering, from **30M to 40M tickets**, while
    still being a bit behind the 2010s scores.
    """)

    st.markdown("""
    \nThe cumulated entries are also linked to the number of millionaire movies each year.
    In 2020, due to the *pandemic*, only **13 movies released in cinema** have reached the 1M entries.
    In 2021 & 2022, these numbers improve progressively, with respectively **24 and 25 movies**.
    """)


    # WORD CLOUD OF 2020s MOVIES
    st.markdown("""----------------------------------""")
    st.header("\nWhat are the most common words / themes of the 2020s movies?")
    plot_movies_word_cloud(df_2020s)

    st.markdown("""
    At the time of the analysis (10/2023, 3 years of data), the main franchises of the early 2020s are 
    *Sonic, Batman, Avatar, Top Gun, Les Minions, and Kaamelott*.
    """)

    st.markdown("""
    \nWe also retrieve in the movies' titles the theme of **"BLACK", "ANMAUX", "FANTASTIQUE", "VOYAGE" and "JOURS"**:
    """)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(df_2020s[df_2020s["titre"].str.contains("BLACK")].sort_values("titre"))
    with col2:
        st.write(df_2020s[df_2020s["titre"].str.contains("ANIMAUX")].sort_values("titre"))
    with col3:
        st.write(df_2020s[df_2020s["titre"].str.contains("FANTASTIQUE")].sort_values("titre"))

    col4, col5 = st.columns(2)
    with col4:
        st.write(df_2020s[df_2020s["titre"].str.contains("VOYAGE")].sort_values("titre"))
    with col5:
        st.write(df_2020s[df_2020s["titre"].str.contains("JOUR")].sort_values("titre"))


    # DISTRIBUTION OF 2020S NATIONALITIES
    st.markdown("""----------------------------------""")
    st.header("\nWhat are the countries' films that have made the most entries in France in the 2020s?")
    plot_nationalites_distribution(df_2020s, "Nationalities of 2020s Millionaire Movies")

    st.markdown("""
    At the time of the analysis (10/2023, 3 years of data), **France & the United States** are once again
    the main represented nationalities in the early 2020s, cumulating together **around 100M entries**.
    \n**Great Britain**'s movies performances, as they reach **more than 17M tickets** with **only
    6 millionaire movies**! This is possible thanks to well-known sagas *(James Bond, Jurassic World, Batman)*
    as well as **Christopher Nolan**'s films (*Tenet*, and certainly *Oppenheimer* for 2023). :flag-gb:
    """)
    st.write(df_2020s[df_2020s["nationalité"] == "GB"])


    # CULT MOVIES OF THE 2020s
    st.markdown("""----------------------------------""")
    st.header("\nFinally, what are the cult movies of the 2020s? :popcorn:")
    st.subheader("Although it might be a bit early to call them cult...")

    st.subheader("French Movies :flag-fr:")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.video("https://youtu.be/NoUEzrss6ww?si=g1Q2zooypgWQ9GLn")
    with col2:
        st.video("https://youtu.be/J6sEwKbMdHw?si=9PxqGXgvdDa3l0oA")
    with col3:
        st.video("https://youtu.be/G_peA3q3Q9w?si=pFcNWAJPnhGQDEYr")

    st.subheader("International Movies :earth_africa:")
    st.write(df_2020s[df_2020s["nationalité"] == "US"])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.video("https://youtu.be/d9MyW72ELq0?si=n5wyyD3WMvNEzubW")
    with col2:
        st.video("https://youtu.be/giXco2jaZ_4?si=OeTfO9ovY--YF_YL")
    with col3:
        st.video("https://youtu.be/8g18jFHCLXk?si=2ZQp7Z8oRt6pQ5jO")

    col4, col5, col6 = st.columns(3)
    with col4:
        st.video("https://youtu.be/JfVOs4VSpmA?si=ipb4Ois1RwLZUy-Y")
    with col5:
        st.video("https://youtu.be/mqqft2x_Aa4?si=L348FZKpXC5AeYvB")
    with col6:
        st.video("https://youtu.be/bK6ldnjE3Y0?si=ipm_mkQtZr--17_D")
