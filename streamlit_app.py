import streamlit as st
import folium
from folium import FeatureGroup, LayerControl
from folium.features import DivIcon
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import os
from streamlit_folium import st_folium

# Configuration de la page
st.set_page_config(
    page_title="Carte Interactive Var et Bouches-du-Rhône",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ Carte des Itinéraires et Dépôts - Var et Bouches-du-Rhône")

# Sidebar avec informations
st.sidebar.header("Configuration")
st.sidebar.info("Cette carte montre les itinéraires et dépôts dans la région.")

@st.cache_data
def load_geographic_data():
    """Charge les données géographiques avec cache pour performance"""
    # Charger les départements
    url = "https://france-geojson.gregoiredavid.fr/repo/departements.geojson"
    gdf = gpd.read_file(url)
    var_et_bdx = gdf[gdf["code"].isin(["83", "13"])]
    
    # Charger les communes
    communes_var_url = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements/83-var/communes-83-var.geojson"
    communes_bdx_url = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements/13-bouches-du-rhone/communes-13-bouches-du-rhone.geojson"
    var_communes = gpd.read_file(communes_var_url)
    bdx_communes = gpd.read_file(communes_bdx_url)
    
    return var_et_bdx, pd.concat([var_communes, bdx_communes])

@st.cache_data
def load_kml_data():
    """Charge les données KML depuis le dossier data/kml/"""
    kml_directory = "data/kml"
    itinerary_data = {}
    
    if os.path.exists(kml_directory):
        colors = ["red", "blue", "green", "purple", "orange", "darkred", "darkblue", 
                 "darkgreen", "cadetblue", "darkpurple", "pink", "lightblue", 
                 "lightgreen", "gray", "lightred", "beige"]
        
        color_index = 0
        
        for filename in os.listdir(kml_directory):
            if filename.endswith(".kml"):
                kml_path = os.path.join(kml_directory, filename)
                try:
                    itineraire_gdf = gpd.read_file(kml_path, driver='KML')
                    if not itineraire_gdf.empty and not itineraire_gdf.geometry.isnull().all():
                        layer_name = os.path.splitext(filename)[0]
                        current_color = colors[color_index % len(colors)]
                        color_index += 1
                        
                        itinerary_data[layer_name] = {
                            'gdf': itineraire_gdf,
                            'color': current_color
                        }
                except Exception as e:
                    st.error(f"Erreur avec le fichier {filename}: {e}")
    
    return itinerary_data

@st.cache_data
def load_excel_data():
    """Charge les données Excel des dépôts"""
    excel_path = "data/Implantations Var_v3.xlsx"
    if os.path.exists(excel_path):
        return pd.read_excel(excel_path)
    return None

def create_map():
    """Crée et retourne la carte Folium"""
    # Charger les données
    var_et_bdx, communes_var_et_bdx = load_geographic_data()
    kml_data = load_kml_data()
    excel_data = load_excel_data()
    
    # Initialisation de la carte
    m = folium.Map(location=[43.25, 6.0], zoom_start=10)
    
    # Ajouter une couche claire
    folium.TileLayer(
        tiles="cartodbpositron",
        name="Clair (Positron)",
        control=True,
    ).add_to(m)
    
    # 1. Calque des départements
    folium.GeoJson(
        var_et_bdx,
        name="Départements Var et Bouches-du-Rhône",
        style_function=lambda x: {'fillColor': 'none', 'color': 'black', 'weight': 2}
    ).add_to(m)
    
    # 2. Calque des communes avec noms
    communes_layer = FeatureGroup(name="Communes")
    name_communes_layer = FeatureGroup(name="Noms des communes", show=False)
    
    for idx, row in communes_var_et_bdx.iterrows():
        # Délimitations des communes
        folium.GeoJson(
            row.geometry,
            style_function=lambda x: {'fillColor': 'none', 'color': 'blue', 'weight': 0.5}
        ).add_to(communes_layer)
        
        # Noms des communes centrés
        try:
            centroid = row.geometry.centroid
            folium.Marker(
                location=[centroid.y, centroid.x],
                icon=DivIcon(
                    icon_size=(80, 19),
                    icon_anchor=(0, 0),
                    html=f'<div style="font-size: 9pt; color: black;">{row["nom"]}</div>',
                ),
            ).add_to(name_communes_layer)
        except Exception as e:
            st.warning(f"Centroïde impossible pour {row.get('nom', 'N/A')}")
    
    communes_layer.add_to(m)
    name_communes_layer.add_to(m)
    
    # FeatureGroups pour les itinéraires
    all_itineraries_red_layer = FeatureGroup(name="Tous les itinéraires (Rouge)")
    all_traversed_communes_yellow_layer = FeatureGroup(name="Communes traversées (Jaune)")
    
    all_traversed_commune_geometries = []
    traversed_commune_names = set()
    itinerary_colors = {}
    
    # 3. Traiter les itinéraires KML
    for layer_name, data in kml_data.items():
        itineraire_gdf = data['gdf']
        current_color = data['color']
        
        itin_layer = FeatureGroup(name=f"Itinéraire: {layer_name}", show=False)
        itinerary_colors[layer_name] = current_color
        
        for _, itineraire in itineraire_gdf.iterrows():
            # Ligne de l'itinéraire
            folium.GeoJson(
                itineraire.geometry,
                style_function=lambda x, color=current_color: {'color': color, 'weight': 5}
            ).add_to(itin_layer)
            
            # Version rouge pour la couche globale
            folium.GeoJson(
                itineraire.geometry,
                style_function=lambda x: {'color': 'red', 'weight': 5}
            ).add_to(all_itineraries_red_layer)
            
            # Communes traversées
            communes_traversees = communes_var_et_bdx[communes_var_et_bdx.intersects(itineraire.geometry)]
            for _, commune in communes_traversees.iterrows():
                folium.GeoJson(
                    commune.geometry,
                    style_function=lambda x, color=current_color: {
                        'fillColor': color, 
                        'color': 'none', 
                        'fillOpacity': 0.3
                    }
                ).add_to(itin_layer)
                
                if commune["nom"] not in traversed_commune_names:
                    all_traversed_commune_geometries.append(commune.geometry)
                    traversed_commune_names.add(commune["nom"])
        
        itin_layer.add_to(m)
    
    # Couche jaune pour toutes les communes traversées
    if all_traversed_commune_geometries:
        traversed_communes_geoseries = gpd.GeoSeries(all_traversed_commune_geometries)
        traversed_communes_geoseries.crs = communes_var_et_bdx.crs
        
        folium.GeoJson(
            traversed_communes_geoseries,
            style_function=lambda x: {'fillColor': 'yellow', 'color': 'none', 'fillOpacity': 0.2}
        ).add_to(all_traversed_communes_yellow_layer)
        
        # Noms des communes traversées
        for commune_name in traversed_commune_names:
            commune_row = communes_var_et_bdx[communes_var_et_bdx["nom"] == commune_name].iloc[0]
            try:
                centroid = commune_row.geometry.centroid
                folium.Marker(
                    location=[centroid.y, centroid.x],
                    icon=DivIcon(html=f'<div style="font-size: 15pt; color: green;">{commune_row.nom}</div>')
                ).add_to(all_traversed_communes_yellow_layer)
            except Exception:
                pass
    
    all_itineraries_red_layer.add_to(m)
    all_traversed_communes_yellow_layer.add_to(m)
    
    # 4. Points des dépôts depuis Excel
    if excel_data is not None:
        couches_par_categorie = {}
        communes_avec_pointeurs = set()
        categories_legende = {}
        
        for idx, row in excel_data.iterrows():
            nom = row["Label"]
            latitude = row["Latitude"]
            longitude = row["Longitude"]
            icone = row["Icone"]
            couleur = row["Couleur"]
            categorie = row["Catégorie"]
            adresse = row["Adresse"]
            
            if categorie not in categories_legende:
                categories_legende[categorie] = {"couleur": couleur, "icone": icone}
            
            point = Point(longitude, latitude)
            for _, commune in communes_var_et_bdx.iterrows():
                if commune.geometry.contains(point):
                    communes_avec_pointeurs.add(commune["nom"])
                    break
            
            if categorie not in couches_par_categorie:
                couches_par_categorie[categorie] = folium.FeatureGroup(name=categorie, show=True)
            
            folium.Marker(
                location=[latitude, longitude],
                icon=folium.Icon(color=couleur, icon=icone, prefix="fa"),
                popup=f"<b>{nom}</b><br>Catégorie: {categorie}<br>Adresse: {adresse}",
                tooltip=nom
            ).add_to(couches_par_categorie[categorie])
        
        for couche in couches_par_categorie.values():
            couche.add_to(m)
        
        # Légende
        legende_html = """
        <div style="
            position: fixed; 
            bottom: 20px; 
            right: 20px; 
            z-index: 1000;
            background: white; 
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 0 10px rgba(0,0,0,0.2);
            max-width: 250px;
            font-family: Arial;
            font-size: 12px;
        ">
            <h4 style="margin-top: 0; margin-bottom: 10px;">Légende</h4>
            <div style="margin-bottom: 10px;"><strong>Catégories des Dépôts</strong></div>
        """
        
        for categorie, style in categories_legende.items():
            legende_html += f"""
            <div style="margin-bottom: 5px;">
                <i class="fa fa-{style['icone']}" style="color: {style['couleur']}; margin-right: 5px;"></i>
                {categorie}
            </div>
            """
        
        legende_html += """
            <div style="margin-top: 15px; margin-bottom: 10px;"><strong>Itinéraires</strong></div>
        """
        
        for itineraire_name, color in itinerary_colors.items():
            legende_html += f"""
            <div style="margin-bottom: 5px;">
                <span style="display: inline-block; width: 20px; height: 5px; background-color: {color}; vertical-align: middle; margin-right: 5px;"></span>
                {itineraire_name}
            </div>
            """
        
        legende_html += "</div>"
        m.get_root().html.add_child(folium.Element(legende_html))
    
    # Contrôle des calques
    LayerControl().add_to(m)
    
    return m

# Interface Streamlit
st.markdown("""
Cette carte interactive montre :
- 🚚 **Les itinéraires** (fichiers KML) avec leurs communes traversées
- 📍 **Les dépôts** localisés avec leurs catégories
- 🗺️ **Les communes et départements** de la région

Utilisez le contrôle de calques en haut à droite pour afficher/masquer les différentes couches.
""")

# Créer et afficher la carte
with st.spinner('Chargement de la carte...'):
    carte = create_map()

# Afficher la carte
st_folium(carte, width=1200, height=700)

# Informations dans la sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("Statistiques")
if load_excel_data() is not None:
    st.sidebar.write(f"📊 Dépôts chargés : {len(load_excel_data())}")

kml_data = load_kml_data()
st.sidebar.write(f"🛣️ Itinéraires chargés : {len(kml_data)}")