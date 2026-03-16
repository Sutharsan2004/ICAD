# ICAD Room Extractor & HVAC Load Calculator

An intelligent architectural floor plan analysis tool built with Streamlit, Shapely, and OpenAI. It automatically parses raw DWG/DXF files, detects enclosed room geometries, classifies room types using GPT-4o Vision, and calculates dynamic HVAC cooling loads (TR) and airflow (CFM).

## 🚀 Features
* **Smart Layer Detection:** Uses a geometric heuristic engine to automatically identify structural walls and base layers without relying on strict CAD naming conventions.
* **Auto-Scaling:** Automatically detects if a drawing is in Meters or Millimeters and scales the coordinates accordingly.
* **AI Room Classification:** Renders the detected floor plan and sends it to GPT-4o alongside geometric statistics to intelligently classify rooms (e.g., Conference Hall, Master Bedroom).
* **Gap Bridging & Polygonization:** Uses advanced `shapely` spatial logic to bridge open doors and windows to form closed room polygons.
* **HVAC Calculations:** Calculates Sensible Heat, Total Heat Load (kW), Tons of Refrigeration (TR), and Airflow (CFM) based on room area, glass fraction, and occupancy.

## 📁 File Structure
* `app.py`: The main Streamlit user interface, layer-scoring logic, and OpenAI API integration.
* `geometry_engine.py`: The core CAD math engine. Handles DXF entity extraction, path-flattening, graph-based furniture clustering (NetworkX), and spatial polygonization.
* `heat_load.py`: The mathematical engine for computing wall/glass surface areas, U-values, and converting Watts to TR/CFM.

## 🛠️ Prerequisites
Before running the application, you must install **ODA File Converter** on your machine. This is a free utility required to convert proprietary `.dwg` files into open `.dxf` format.
1. Download ODA File Converter: [https://www.opendesign.com/guestfiles/oda_file_converter](https://www.opendesign.com/guestfiles/oda_file_converter)
2. Install it on your system.
3. Note the installation path (e.g., `C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe`). You will need to input this in the app's sidebar.

## ⚙️ Installation

1. **Clone the repository or download the files:**
   Ensure `app.py`, `geometry_engine.py`, and `heat_load.py` are in the same folder.

2. **Create a virtual environment (Recommended):**
   ```bash
   python -m venv env
   source env/Scripts/activate  # On Windows
   # source env/bin/activate    # On Mac/Linux
