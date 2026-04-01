import customtkinter as ctk
from tkinter import filedialog, messagebox
import requests
import json
import re
import os
import geopandas as gpd
from shapely.geometry import LineString, Polygon, shape # Updated Import

class OSMDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("OSM Data Extractor Pro")
        self.geometry("500x600")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # --- UI ELEMENTS ---
        self.label = ctk.CTkLabel(self, text="OSM Data Downloader", font=("Roboto", 24))
        self.label.pack(pady=20)

        self.source_entry = ctk.CTkEntry(self, placeholder_text="Paste Way ID or OSM URL...", width=400)
        self.source_entry.pack(pady=10)

        self.name_entry = ctk.CTkEntry(self, placeholder_text="Custom Filename (Optional)", width=400)
        self.name_entry.pack(pady=10)

        self.format_label = ctk.CTkLabel(self, text="Select Export Format:")
        self.format_label.pack(pady=5)

        self.format_var = ctk.StringVar(value="GeoJSON")
        self.format_menu = ctk.CTkOptionMenu(self, values=["GeoJSON", "GPX", "KML", "Shapefile"], variable=self.format_var)
        self.format_menu.pack(pady=10)

        self.download_btn = ctk.CTkButton(self, text="Select Folder & Download", command=self.start_download, fg_color="#2ecc71", hover_color="#27ae60")
        self.download_btn.pack(pady=30)

        self.status_label = ctk.CTkLabel(self, text="Ready", text_color="gray")
        self.status_label.pack(pady=10)

    def get_way_id(self, user_input):
        match = re.search(r'(\d+)', user_input)
        return match.group(1) if match else None

    # --- UPDATED PORTION 1: Smart Geometry Logic ---
    def save_as_shapefile(self, data, folder, filename):
        element = data['elements'][0]
        tags = element.get('tags', {})
        coords = [(pt['lon'], pt['lat']) for pt in element.get('geometry', [])]

        if len(coords) < 2:
            raise Exception("Not enough coordinates to create geometry.")

        # Check if it's a Polygon (closed loop) or a LineString
        if coords[0] == coords[-1] and len(coords) >= 4:
            geom = Polygon(coords)
        else:
            geom = LineString(coords)

        gdf = gpd.GeoDataFrame([tags], geometry=[geom], crs="EPSG:4326")
        full_path = os.path.join(folder, f"{filename}.shp")
        gdf.to_file(full_path, driver='ESRI Shapefile')
        return full_path

    # --- UPDATED PORTION 2: Basic Format Polygon Support ---
    def convert_basic_data(self, data, way_id, fmt):
        element = data['elements'][0]
        tags = element.get('tags', {})
        coords = element.get('geometry', [])
        name = tags.get('name', f"Way_{way_id}")

        # Detect if it's a polygon for GeoJSON
        is_polygon = coords[0] == coords[-1] if len(coords) > 2 else False

        if fmt == "GeoJSON":
            geom_type = "Polygon" if is_polygon else "LineString"
            # Polygons in GeoJSON require coordinates nested in an additional list
            geom_coords = [[ [pt['lon'], pt['lat']] for pt in coords ]] if is_polygon else [[pt['lon'], pt['lat']] for pt in coords]

            geojson = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "properties": tags,
                    "geometry": {"type": geom_type, "coordinates": geom_coords}
                }]
            }
            return json.dumps(geojson, indent=4), "geojson"

        elif fmt == "GPX":
            # GPX is strictly for tracks (lines); polygons will show as closed tracks
            gpx = f'<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1"><trk><name>{name}</name><trkseg>'
            for pt in coords: gpx += f'<trkpt lat="{pt["lat"]}" lon="{pt["lon"]}"></trkpt>'
            gpx += '</trkseg></trk></gpx>'
            return gpx, "gpx"

        elif fmt == "KML":
            coord_str = " ".join([f"{pt['lon']},{pt['lat']},0" for pt in coords])
            # Use Polygon tag for KML if it's a closed loop
            if is_polygon:
                geom_xml = f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{coord_str}</coordinates></LinearRing></outerBoundaryIs></Polygon>"
            else:
                geom_xml = f"<LineString><coordinates>{coord_str}</coordinates></LineString>"

            kml = f'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>{name}</name>{geom_xml}</Placemark></Document></kml>'
            return kml, "kml"

    def start_download(self):
        source = self.source_entry.get().strip()
        way_id = self.get_way_id(source)

        if not way_id:
            messagebox.showerror("Error", "Please enter a valid Way ID or URL.")
            return

        save_dir = filedialog.askdirectory()
        if not save_dir: return

        self.status_label.configure(text="Fetching Data...", text_color="yellow")
        self.update()

        # --- UPDATED PORTION 3: Universal Query ---
        # Note: Changed to fetch way OR relation to cover all polygon types
        url = "https://overpass-api.de/api/interpreter"
        query = f"[out:json];(way({way_id});rel({way_id}););out geom;"

        try:
            response = requests.get(url, params={'data': query}, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if not data.get('elements'): raise Exception("Object not found in OSM.")

                fmt = self.format_var.get()
                user_filename = self.name_entry.get().strip() or f"osm_export_{way_id}"
                user_filename = re.sub(r'[\\/*?:"<>|]', "", user_filename)

                if fmt == "Shapefile":
                    self.save_as_shapefile(data, save_dir, user_filename)
                else:
                    content, ext = self.convert_basic_data(data, way_id, fmt)
                    full_path = os.path.join(save_dir, f"{user_filename}.{ext}")
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)

                self.status_label.configure(text="Complete!", text_color="#2ecc71")
                messagebox.showinfo("Success", f"File saved to:\n{save_dir}")
            else:
                self.status_label.configure(text="Server Error", text_color="red")
        except Exception as e:
            self.status_label.configure(text="Failed", text_color="red")
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    app = OSMDownloader()
    app.mainloop()