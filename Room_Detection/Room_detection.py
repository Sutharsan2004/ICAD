# import matplotlib.pyplot as plt
# import os
# import math
# from dotenv import load_dotenv
# import ezdxf
# from ezdxf import path 
# from openai import OpenAI
# import networkx as nx
# import numpy as np
# from shapely.geometry import Point, LineString, Polygon, MultiPoint, MultiLineString
# from shapely.ops import polygonize, unary_union
# from shapely.strtree import STRtree

# load_dotenv()

# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# # ==========================================
# # 0. LAYER FILTERING
# # ==========================================

# def filter_dxf_layers(input_filepath, output_filepath, include_layers):
#     print(f"\n[+] Filtering layers in {os.path.basename(input_filepath)}...")
#     try:
#         doc = ezdxf.readfile(input_filepath)
#         msp = doc.modelspace()
#         entities_to_delete = []
#         for entity in msp:
#             if entity.dxf.layer not in include_layers:
#                 entities_to_delete.append(entity)
#         for entity in entities_to_delete:
#             msp.delete_entity(entity)
#         doc.saveas(output_filepath)
#         return True
#     except Exception as e:
#         print(f"Error filtering layers: {e}")
#         return False

# # ==========================================
# # 1. DYNAMIC SCALE DETECTOR
# # ==========================================

# def get_dxf_scale_to_mm(filepath):
#     try:
#         doc = ezdxf.readfile(filepath)
#         insunits = doc.header.get('$INSUNITS', 0)
#         scale_map = {0: 1.0, 1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0}
#         scale = scale_map.get(insunits, 1.0)
#         unit_names = {0: "Unitless", 1: "Inches", 2: "Feet", 4: "Millimeters", 5: "Centimeters", 6: "Meters"}
#         print(f"  -> Detected internal units: {unit_names.get(insunits, 'Unknown')} ($INSUNITS={insunits})")
#         print(f"  -> Applying dynamic scale multiplier: {scale}")
#         return scale
#     except Exception:
#         return 1.0

# # ==========================================
# # 2. VISUALIZATION ENGINE
# # ==========================================

# def visualize_results(wall_lines, wall_cavities, rooms, objects_data):
#     """
#     Plots Rooms (Blue), Walls (Black), and Objects (Red).
#     """
#     plt.figure(figsize=(14, 10))
    
#     # LAYER 1: Rooms (Light Blue Fill)
#     for room in rooms:
#         poly = room.get('polygon')
#         if poly and poly.geom_type == 'Polygon':
#             x, y = poly.exterior.xy
#             plt.fill(x, y, alpha=0.35, color='dodgerblue', edgecolor='blue', linewidth=1, zorder=1)
            
#             centroid = poly.centroid
#             plt.text(centroid.x, centroid.y, room['name'], 
#                      fontsize=8, ha='center', va='center', weight='bold',
#                      bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=2), zorder=5)
            
#     # LAYER 2: Solid Wall Cavities
#     for cav in wall_cavities:
#         if cav.geom_type == 'Polygon':
#             x, y = cav.exterior.xy
#             plt.fill(x, y, alpha=1.0, color='dimgray', zorder=2)

#     # LAYER 3: Clean Structural Wall Outlines
#     for i, line in enumerate(wall_lines):
#         x_coords = [line[0][0], line[1][0]]
#         y_coords = [line[0][1], line[1][1]]
#         label = 'Structural Walls' if i == 0 else ""
#         plt.plot(x_coords, y_coords, color='black', linewidth=2.0, zorder=3, label=label)
        
#     # LAYER 4: Furniture/Objects (Red Dots)
#     if objects_data:
#         obj_x = [obj['center_x'] for obj in objects_data]
#         obj_y = [obj['center_y'] for obj in objects_data]
#         plt.scatter(obj_x, obj_y, color='red', s=25, label='Detected Objects', zorder=4)
        
#     plt.title("CAD R&D: Distinct Extraction of Rooms, Walls, and Objects")
#     plt.xlabel("X units (true mm)")
#     plt.ylabel("Y units (true mm)")
#     plt.axis('equal') 
#     plt.legend()
#     plt.grid(True, linestyle='--', alpha=0.3)
#     plt.show()

# # ==========================================
# # 3. TEXT & GEOMETRY EXTRACTION
# # ==========================================

# def extract_dxf_text(entity, texts_list):
#     if entity.dxftype() == 'TEXT':
#         texts_list.append({"text": entity.dxf.text, "x": entity.dxf.insert.x, "y": entity.dxf.insert.y})
#     elif entity.dxftype() == 'MTEXT':
#         texts_list.append({"text": entity.text, "x": entity.dxf.insert.x, "y": entity.dxf.insert.y})
#     elif entity.dxftype() == 'INSERT':
#         for sub_entity in entity.virtual_entities():
#             extract_dxf_text(sub_entity, texts_list)

# def get_all_texts(filepath):
#     try:
#         doc = ezdxf.readfile(filepath)
#         msp = doc.modelspace()
#     except Exception:
#         return []
#     texts = []
#     for entity in msp.query('TEXT MTEXT INSERT'):
#         extract_dxf_text(entity, texts)
#     return texts

# def process_cad_entity(entity, raw_lines, scale=1.0):
#     if entity.dxftype() == 'INSERT':
#         for sub_entity in entity.virtual_entities():
#             process_cad_entity(sub_entity, raw_lines, scale)
#         return
#     try:
#         p = path.make_path(entity)
#         points = list(p.flattening(distance=0.1))
#         for i in range(len(points) - 1):
#             start = (round(points[i].x * scale, 1), round(points[i].y * scale, 1))
#             end = (round(points[i+1].x * scale, 1), round(points[i+1].y * scale, 1))
#             raw_lines.append([start, end])
#     except Exception:
#         pass

# def extract_dxf_geometry_by_layer(filepath, target_layers, scale=1.0):
#     """
#     NEW: Extracts geometry ONLY if it belongs to a specific list of layers.
#     This prevents furniture from mixing into structural walls.
#     """
#     try:
#         doc = ezdxf.readfile(filepath)
#         msp = doc.modelspace()
#     except Exception:
#         return []
#     raw_lines = []
#     for entity in msp.query('LINE LWPOLYLINE POLYLINE INSERT ARC CIRCLE ELLIPSE SPLINE'):
#         # Only process if layer is in our targeted list
#         if entity.dxf.layer in target_layers:
#             process_cad_entity(entity, raw_lines, scale)
#     return raw_lines

# # ==========================================
# # 4. FILTERING & MEASUREMENT ENGINE
# # ==========================================

# def extract_objects_and_walls(raw_lines, gap_tolerance=15, min_obj_size=300, max_obj_size=4000):
#     """Processes structural lines into clean, continuous wall segments."""
#     shapely_lines = [LineString(line) for line in raw_lines]
#     buffered = [line.buffer(gap_tolerance) for line in shapely_lines]
#     tree = STRtree(buffered)
#     G = nx.Graph()
#     G.add_nodes_from(range(len(raw_lines)))
#     for i, poly in enumerate(buffered):
#         for j in tree.query(poly):
#             if i != j and poly.intersects(buffered[j]):
#                 G.add_edge(i, j)
#     wall_lines = []
#     for comp in nx.connected_components(G):
#         cluster_lines = [raw_lines[idx] for idx in comp]
#         wall_lines.extend(cluster_lines)
#     return wall_lines

# def process_furniture_to_objects(furn_lines, gap_tolerance=50):
#     """Groups furniture lines into localized red dot objects."""
#     shapely_lines = [LineString(line) for line in furn_lines]
#     buffered = [line.buffer(gap_tolerance) for line in shapely_lines]
#     tree = STRtree(buffered)
#     G = nx.Graph()
#     G.add_nodes_from(range(len(furn_lines)))
#     for i, poly in enumerate(buffered):
#         for j in tree.query(poly):
#             if i != j and poly.intersects(buffered[j]):
#                 G.add_edge(i, j)
#     objects_data = []
#     for comp in nx.connected_components(G):
#         cluster_lines = [furn_lines[idx] for idx in comp]
#         mls = MultiLineString([LineString(l) for l in cluster_lines])
#         minx, miny, maxx, maxy = mls.bounds
#         objects_data.append({
#             "object_id": f"Obj_{len(objects_data)+1}",
#             "length": round(maxx - minx, 2),
#             "width": round(maxy - miny, 2),
#             "center_x": round(mls.centroid.x, 2),
#             "center_y": round(mls.centroid.y, 2),
#             "point": mls.centroid
#         })
#     return objects_data

# def extract_measurements(wall_lines, furn_lines, max_door_width=2500, min_room_area=1500000):
#     """
#     NEW: Takes BOTH wall lines and furniture lines. Uses furniture doors to physically close gaps,
#     but filters out inner furniture polygons so they don't become micro-rooms.
#     """
#     if not wall_lines: return [], []
        
#     shapely_wall_lines = [LineString(l) for l in wall_lines]
#     merged_walls = unary_union(shapely_wall_lines)
    
#     if merged_walls.geom_type == 'LineString': lines_list = [merged_walls]
#     elif merged_walls.geom_type == 'MultiLineString': lines_list = list(merged_walls.geoms)
#     else: return [], []

#     valid_endpoints = []
#     for line in lines_list:
#         if line.length > 400: 
#             valid_endpoints.append(Point(line.coords[0]))
#             valid_endpoints.append(Point(line.coords[-1]))
        
#     invisible_doors = []
    
#     # 1. Cap Double-Line Wall Ends Unconditionally (<= 400mm)
#     for i, ep1 in enumerate(valid_endpoints):
#         for j, ep2 in enumerate(valid_endpoints):
#             if i < j and ep1.distance(ep2) <= 400:
#                 invisible_doors.append(LineString([ep1, ep2]))

#     # 2. Strict Orthogonal Line-of-Sight Bridging (For open archways with NO doors)
#     for i, ep1 in enumerate(valid_endpoints):
#         for j, ep2 in enumerate(valid_endpoints):
#             if i < j:
#                 dist = ep1.distance(ep2)
#                 if 400 < dist <= max_door_width:
#                     dx, dy = abs(ep1.x - ep2.x), abs(ep1.y - ep2.y)
#                     if dx < 100 or dy < 100: 
#                         bridge = LineString([ep1, ep2])
#                         if not bridge.crosses(merged_walls):
#                             invisible_doors.append(bridge)
                            
#     # 3. Combine Walls + Invisible Bridges + FURNITURE DOORS
#     shapely_furn_lines = [LineString(l) for l in furn_lines]
#     all_geometry = lines_list + invisible_doors + shapely_furn_lines
#     noded_geometry = unary_union(all_geometry)
#     raw_polygons = list(polygonize(noded_geometry))
    
#     min_x, min_y, max_x, max_y = noded_geometry.bounds
#     total_bbox_area = (max_x - min_x) * (max_y - min_y)
    
#     rooms_data = []
#     wall_cavities = []
    
#     for poly in raw_polygons:
#         area = poly.area 
#         rm_minx, rm_miny, rm_maxx, rm_maxy = poly.bounds
#         width = rm_maxx - rm_minx
#         height = rm_maxy - rm_miny
        
#         if area >= min_room_area:
#             rooms_data.append({
#                 "room_id": f"Room_{len(rooms_data)+1}",
#                 "width": round(width, 2),
#                 "height": round(height, 2),
#                 "area": round(area, 2),
#                 "polygon": poly,
#                 "objects_inside": []
#             })
#         elif 10000 < area < min_room_area: 
#             wall_cavities.append(poly)

#     # Filter nested duplicate polygons (Destroys inner beds/cars so they don't become rooms)
#     clean_rooms = []
#     for i, room in enumerate(rooms_data):
#         is_invalid = False
#         if room['area'] > (total_bbox_area * 0.4): continue # Skip huge exterior building loop
            
#         for j, other_room in enumerate(rooms_data):
#             if i != j:
#                 # If room A is inside room B, A is just furniture (like a car in the garage). Discard A!
#                 if other_room['polygon'].contains(room['polygon'].representative_point()):
#                     is_invalid = True
#                     break 
#                 intersection = room['polygon'].intersection(other_room['polygon'])
#                 if intersection.area > (0.8 * room['polygon'].area):
#                     if room['area'] < other_room['area']: 
#                         is_invalid = True
#                         break
#         if not is_invalid:
#             clean_rooms.append(room)
            
#     return sorted(clean_rooms, key=lambda x: x['area'], reverse=True), wall_cavities

# def generate_room_name(width, height, text_context):
#     context_str = ", ".join(text_context) if text_context else "No text labels found."
#     prompt = f"""
#     You are an expert architectural CAD assistant. I have mathematically extracted a partitioned zone from a floorplan.
#     Zone Dimensions: {width} units by {height} units.
#     Text annotations found inside this zone: [{context_str}]
#     Based on the size and the text annotations, what is the most logical, professional name for this space?
#     Reply ONLY with the room name. Do not include any other conversational text.
#     """
#     try:
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[{"role": "system", "content": "You are a CAD architectural assistant."},
#                       {"role": "user", "content": prompt}],
#             temperature=0.5
#         )
#         return response.choices[0].message.content.strip()
#     except Exception:
#         return "Unnamed Partition"

# # ==========================================
# # 5. MAIN EXECUTION WORKFLOW
# # ==========================================
# if __name__ == "__main__":
#     RAW_DXF_FILE = r"C:\Users\abine\OneDrive\Documents\Icebergs_sudharsan\CAD_R&D\Graph Based CAD\DXF_FIles\House Floor Plan Sample.dxf" 
#     CLEAN_DXF_FILE = r"C:\Users\abine\OneDrive\Documents\Icebergs_sudharsan\CAD_R&D\Graph Based CAD\DXF_FIles\Cleaned_sample.dxf"
    
#     # 1. SPLIT YOUR LAYERS INTO TWO CATEGORIES
#     STRUCTURAL_LAYERS = ["Wall", "Walls", "Structural", "0", "Windows", "Base"] 
#     FURNITURE_LAYERS = ["Furniture", "Doors"] 
    
#     print(f"--- Processing {os.path.basename(RAW_DXF_FILE)} ---")
    
#     success = filter_dxf_layers(RAW_DXF_FILE, CLEAN_DXF_FILE, STRUCTURAL_LAYERS + FURNITURE_LAYERS)
#     if not success: exit()
        
#     print(f"\n[+] Extracting data from the filtered file...")
#     DRAWING_SCALE = get_dxf_scale_to_mm(CLEAN_DXF_FILE)
    
#     all_texts = get_all_texts(CLEAN_DXF_FILE)
#     for text in all_texts:
#         text['x'] *= DRAWING_SCALE
#         text['y'] *= DRAWING_SCALE
        
#     print("\n[+] Extracting Structural Geometry vs Furniture Geometry...")
#     # Extract walls and furniture completely independently
#     raw_wall_lines = extract_dxf_geometry_by_layer(CLEAN_DXF_FILE, STRUCTURAL_LAYERS, DRAWING_SCALE)
#     raw_furn_lines = extract_dxf_geometry_by_layer(CLEAN_DXF_FILE, FURNITURE_LAYERS, DRAWING_SCALE)
    
#     print("\n[+] Processing Walls and Objects...")
#     wall_lines = extract_objects_and_walls(raw_wall_lines)
#     extracted_objects = process_furniture_to_objects(raw_furn_lines)

#     print("\n[+] Running Polygonize Engine to extract discrete rooms...")
#     # Pass BOTH into the measurement engine. Furniture lines will seal the rooms!
#     rooms, wall_cavities = extract_measurements(wall_lines, raw_furn_lines) 
        
#     print("\n[+] Executing Spatial Mapping (Placing objects in rooms)...")
#     for room in rooms:
#         poly = room['polygon']
#         usable_floor_space = poly.buffer(-50)
        
#         for obj in extracted_objects:
#             if usable_floor_space.covers(obj['point']): 
#                 room['objects_inside'].append({"id": obj['object_id'], "length": obj['length'], "width": obj['width']})
        
#         catchment_area = poly.buffer(1000) 
#         texts_in_room = [t['text'] for t in all_texts if catchment_area.contains(Point(t['x'], t['y']))]
#         room['name'] = generate_room_name(room['width'], room['height'], texts_in_room)

#     print("\n[+] Generating Distinct Visual Plot...")
#     visualize_results(wall_lines, wall_cavities, rooms, extracted_objects)

#     for room in rooms:
#         if 'polygon' in room:
#             del room['polygon']

#     print("\n--- FINAL GRANULAR MEASUREMENT RESULTS ---")
#     for room in rooms:
#         w_m = round(room['width'] / 1000, 2)
#         h_m = round(room['height'] / 1000, 2)
#         area_m2 = round(room['area'] / 1000000, 2)

#         print(f"\n[{room['name']}]")
#         print(f"  - Dimensions: {room['width']} x {room['height']} mm  ({w_m} x {h_m} m)")
#         print(f"  - Area: {room['area']} mm²  ({area_m2} m²)")
#         print(f"  - Objects Contained: {len(room['objects_inside'])}")













import matplotlib.pyplot as plt
import os
import math
import ezdxf
from ezdxf import path 
import networkx as nx
import numpy as np
from shapely.geometry import Point, LineString, Polygon, MultiPoint, MultiLineString
from shapely.ops import polygonize, unary_union
from shapely.strtree import STRtree

# ==========================================
# 0. LAYER FILTERING
# ==========================================

def filter_dxf_layers(input_filepath, output_filepath, include_layers):
    print(f"\n[+] Filtering layers in {os.path.basename(input_filepath)}...")
    try:
        doc = ezdxf.readfile(input_filepath)
        msp = doc.modelspace()
        entities_to_delete = []
        for entity in msp:
            if entity.dxf.layer not in include_layers:
                entities_to_delete.append(entity)
        for entity in entities_to_delete:
            msp.delete_entity(entity)
        doc.saveas(output_filepath)
        return True
    except Exception as e:
        print(f"Error filtering layers: {e}")
        return False

# ==========================================
# 1. DYNAMIC SCALE DETECTOR
# ==========================================

def get_dxf_scale_to_mm(filepath):
    try:
        doc = ezdxf.readfile(filepath)
        insunits = doc.header.get('$INSUNITS', 0)
        scale_map = {0: 1.0, 1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0}
        scale = scale_map.get(insunits, 1.0)
        unit_names = {0: "Unitless", 1: "Inches", 2: "Feet", 4: "Millimeters", 5: "Centimeters", 6: "Meters"}
        print(f"  -> Detected internal units: {unit_names.get(insunits, 'Unknown')} ($INSUNITS={insunits})")
        print(f"  -> Applying dynamic scale multiplier: {scale}")
        return scale
    except Exception:
        return 1.0

# ==========================================
# 2. VISUALIZATION ENGINE
# ==========================================

def visualize_results(wall_lines, wall_cavities, rooms, objects_data):
    """Plots Rooms (Blue), Walls (Black), and Objects (Red) with precise labeling."""
    plt.figure(figsize=(16, 10))
    
    # LAYER 1: Rooms (Light Blue Fill)
    for room in rooms:
        poly = room.get('polygon')
        if poly and poly.geom_type == 'Polygon':
            x, y = poly.exterior.xy
            plt.fill(x, y, alpha=0.35, color='dodgerblue', edgecolor='blue', linewidth=1, zorder=1)
            
            # Room Label
            centroid = poly.centroid
            plt.text(centroid.x, centroid.y, room['name'], 
                     fontsize=9, ha='center', va='center', weight='bold',
                     bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=2), zorder=5)
            
    # LAYER 2: Solid Wall Cavities
    for cav in wall_cavities:
        if cav.geom_type == 'Polygon':
            x, y = cav.exterior.xy
            plt.fill(x, y, alpha=1.0, color='dimgray', zorder=2)

    # LAYER 3: Clean Structural Wall Outlines
    for i, line in enumerate(wall_lines):
        x_coords = [line[0][0], line[1][0]]
        y_coords = [line[0][1], line[1][1]]
        label = 'Structural Walls' if i == 0 else ""
        plt.plot(x_coords, y_coords, color='black', linewidth=2.0, zorder=3, label=label)
        
    # LAYER 4: Objects / Doors (Red Dots + Labels)
    if objects_data:
        obj_x = [obj['center_x'] for obj in objects_data]
        obj_y = [obj['center_y'] for obj in objects_data]
        plt.scatter(obj_x, obj_y, color='red', s=25, label='Detected Objects', zorder=4)
        
        for obj in objects_data:
            plt.text(obj['center_x'], obj['center_y'] + 250, obj['object_id'], 
                     fontsize=7, color='darkred', ha='center', zorder=6)
        
    plt.title("CAD R&D: Extracted Rooms, Walls, and Objects")
    plt.xlabel("X units (true mm)")
    plt.ylabel("Y units (true mm)")
    plt.axis('equal') 
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.3)
    plt.show()

# ==========================================
# 3. GEOMETRY EXTRACTION
# ==========================================

def process_cad_entity(entity, raw_lines, scale=1.0):
    if entity.dxftype() == 'INSERT':
        for sub_entity in entity.virtual_entities():
            process_cad_entity(sub_entity, raw_lines, scale)
        return
    try:
        p = path.make_path(entity)
        points = list(p.flattening(distance=0.1))
        for i in range(len(points) - 1):
            start = (round(points[i].x * scale, 1), round(points[i].y * scale, 1))
            end = (round(points[i+1].x * scale, 1), round(points[i+1].y * scale, 1))
            raw_lines.append([start, end])
    except Exception:
        pass

def extract_dxf_geometry_by_layer(filepath, target_layers, scale=1.0):
    try:
        doc = ezdxf.readfile(filepath)
        msp = doc.modelspace()
    except Exception:
        return []
    raw_lines = []
    for entity in msp.query('LINE LWPOLYLINE POLYLINE INSERT ARC CIRCLE ELLIPSE SPLINE'):
        if entity.dxf.layer in target_layers:
            process_cad_entity(entity, raw_lines, scale)
    return raw_lines

# ==========================================
# 4. FILTERING & MEASUREMENT ENGINE
# ==========================================

def extract_objects_and_walls(raw_lines, gap_tolerance=15):
    """Processes structural lines into clean, continuous wall segments."""
    shapely_lines = [LineString(line) for line in raw_lines]
    buffered = [line.buffer(gap_tolerance) for line in shapely_lines]
    tree = STRtree(buffered)
    G = nx.Graph()
    G.add_nodes_from(range(len(raw_lines)))
    for i, poly in enumerate(buffered):
        for j in tree.query(poly):
            if i != j and poly.intersects(buffered[j]):
                G.add_edge(i, j)
    wall_lines = []
    for comp in nx.connected_components(G):
        cluster_lines = [raw_lines[idx] for idx in comp]
        wall_lines.extend(cluster_lines)
    return wall_lines

def process_furniture_to_objects(furn_lines, gap_tolerance=50):
    """Groups furniture/door lines into localized red dot objects."""
    if not furn_lines: return []
    shapely_lines = [LineString(line) for line in furn_lines]
    buffered = [line.buffer(gap_tolerance) for line in shapely_lines]
    tree = STRtree(buffered)
    G = nx.Graph()
    G.add_nodes_from(range(len(furn_lines)))
    for i, poly in enumerate(buffered):
        for j in tree.query(poly):
            if i != j and poly.intersects(buffered[j]):
                G.add_edge(i, j)
    objects_data = []
    for comp in nx.connected_components(G):
        cluster_lines = [furn_lines[idx] for idx in comp]
        mls = MultiLineString([LineString(l) for l in cluster_lines])
        minx, miny, maxx, maxy = mls.bounds
        objects_data.append({
            "object_id": f"Obj {len(objects_data)+1}",
            "length": round(maxx - minx, 2),
            "width": round(maxy - miny, 2),
            "center_x": round(mls.centroid.x, 2),
            "center_y": round(mls.centroid.y, 2),
            "point": mls.centroid
        })
    return objects_data

def extract_measurements(wall_lines, objects_data, max_door_width=4000, min_room_area=1500000, min_closet_area=300000):
    """
    Features Orthogonal Bridging to seal open archways, and checks if small spaces 
    contain doors/objects to validate them as rooms.
    """
    if not wall_lines: return [], []
        
    shapely_wall_lines = [LineString(l) for l in wall_lines]
    merged_walls = unary_union(shapely_wall_lines)
    
    if merged_walls.geom_type == 'LineString': lines_list = [merged_walls]
    elif merged_walls.geom_type == 'MultiLineString': lines_list = list(merged_walls.geoms)
    else: return [], []

    valid_endpoints = []
    for line in lines_list:
        if line.length > 200: # Ignore noise
            valid_endpoints.append(Point(line.coords[0]))
            valid_endpoints.append(Point(line.coords[-1]))
        
    invisible_doors = []
    
    # 1. Cap Double-Line Wall Ends (<= 400mm)
    for i, ep1 in enumerate(valid_endpoints):
        for j, ep2 in enumerate(valid_endpoints):
            if i < j and ep1.distance(ep2) <= 400:
                invisible_doors.append(LineString([ep1, ep2]))

    # 2. STRICT Orthogonal Ray-Casting (Seals massive 120+ sqm archways safely)
    for i, ep1 in enumerate(valid_endpoints):
        for j, ep2 in enumerate(valid_endpoints):
            if i < j:
                dist = ep1.distance(ep2)
                if 400 < dist <= max_door_width:
                    dx = abs(ep1.x - ep2.x)
                    dy = abs(ep1.y - ep2.y)
                    # Line must be nearly perfectly horizontal or vertical (150mm CAD tolerance)
                    if dx < 150 or dy < 150: 
                        bridge = LineString([ep1, ep2])
                        if not bridge.crosses(merged_walls):
                            invisible_doors.append(bridge)
                            
    # 3. Polygonize
    all_geometry = lines_list + invisible_doors
    noded_geometry = unary_union(all_geometry)
    raw_polygons = list(polygonize(noded_geometry))
    
    min_x, min_y, max_x, max_y = noded_geometry.bounds
    total_bbox_area = (max_x - min_x) * (max_y - min_y)
    
    rooms_data = []
    wall_cavities = []
    
    for poly in raw_polygons:
        area = poly.area 
        rm_minx, rm_miny, rm_maxx, rm_maxy = poly.bounds
        width = rm_maxx - rm_minx
        height = rm_maxy - rm_miny
        
        is_valid_room = False
        
        # Rule 1: Large enough to be a room
        if area >= min_room_area:
            is_valid_room = True
        # Rule 2: Too small to be a room, BUT contains a door/object (Utility closet/Toilet)
        elif min_closet_area <= area < min_room_area:
            buffered_poly = poly.buffer(50) # Buffer slightly to catch objects touching the walls
            for obj in objects_data:
                if buffered_poly.covers(obj['point']):
                    is_valid_room = True
                    break
        
        if is_valid_room:
            rooms_data.append({
                "width": round(width, 2),
                "height": round(height, 2),
                "area": round(area, 2),
                "polygon": poly,
                "objects_inside": []
            })
        elif 10000 < area < min_closet_area: 
            wall_cavities.append(poly)

    # Filter nested duplicate polygons
    clean_rooms = []
    for i, room in enumerate(rooms_data):
        is_invalid = False
        if room['area'] > (total_bbox_area * 0.4): continue # Skip outer building shell
            
        for j, other_room in enumerate(rooms_data):
            if i != j:
                if other_room['polygon'].contains(room['polygon'].representative_point()):
                    is_invalid = True
                    break 
                intersection = room['polygon'].intersection(other_room['polygon'])
                if intersection.area > (0.8 * room['polygon'].area):
                    if room['area'] < other_room['area']: 
                        is_invalid = True
                        break
        if not is_invalid:
            clean_rooms.append(room)
            
    # Sort by size and assign sequential simple names
    clean_rooms = sorted(clean_rooms, key=lambda x: x['area'], reverse=True)
    for idx, room in enumerate(clean_rooms):
        room['name'] = f"Room {idx+1}"
        room['room_id'] = f"R{idx+1}"
            
    return clean_rooms, wall_cavities


# ==========================================
# 5. MAIN EXECUTION WORKFLOW
# ==========================================
if __name__ == "__main__":
    RAW_DXF_FILE = r"C:\Users\abine\OneDrive\Documents\Icebergs_sudharsan\CAD_R&D\Graph Based CAD\DXF_FIles\House Floor Plan Sample.dxf" 
    CLEAN_DXF_FILE = r"C:\Users\abine\OneDrive\Documents\Icebergs_sudharsan\CAD_R&D\Graph Based CAD\DXF_FIles\Cleaned_sample.dxf"
    
    # LAYER SEPARATION
    STRUCTURAL_LAYERS = ["Wall", "Walls", "Structural", "0", "Windows", "Base"] 
    FURNITURE_LAYERS = ["Furniture", "Doors"] 
    
    print(f"--- Processing {os.path.basename(RAW_DXF_FILE)} ---")
    
    success = filter_dxf_layers(RAW_DXF_FILE, CLEAN_DXF_FILE, STRUCTURAL_LAYERS + FURNITURE_LAYERS)
    if not success: exit()
        
    print(f"\n[+] Extracting data from the filtered file...")
    DRAWING_SCALE = get_dxf_scale_to_mm(CLEAN_DXF_FILE)
        
    print("\n[+] Extracting Structural Geometry vs Furniture Geometry...")
    raw_wall_lines = extract_dxf_geometry_by_layer(CLEAN_DXF_FILE, STRUCTURAL_LAYERS, DRAWING_SCALE)
    raw_furn_lines = extract_dxf_geometry_by_layer(CLEAN_DXF_FILE, FURNITURE_LAYERS, DRAWING_SCALE)
    
    print("\n[+] Processing Walls and Objects...")
    wall_lines = extract_objects_and_walls(raw_wall_lines)
    extracted_objects = process_furniture_to_objects(raw_furn_lines)

    print("\n[+] Running Polygonize Engine to extract discrete rooms...")
    rooms, wall_cavities = extract_measurements(wall_lines, extracted_objects) 
        
    print("\n[+] Executing Spatial Mapping (Placing objects in rooms)...")
    for room in rooms:
        poly = room['polygon']
        usable_floor_space = poly.buffer(10)
        
        for obj in extracted_objects:
            if usable_floor_space.covers(obj['point']): 
                room['objects_inside'].append({"id": obj['object_id'], "length": obj['length'], "width": obj['width']})

    print("\n[+] Generating Distinct Visual Plot...")
    visualize_results(wall_lines, wall_cavities, rooms, extracted_objects)

    for room in rooms:
        if 'polygon' in room:
            del room['polygon']

    print("\n--- FINAL CLEAR MEASUREMENT RESULTS ---")
    for room in rooms:
        # Convert dimensions directly to formatted meters for clear reading
        w_m = round(room['width'] / 1000, 2)
        h_m = round(room['height'] / 1000, 2)
        area_m2 = round(room['area'] / 1000000, 2)

        print(f"\n[{room['name']}]")
        print(f"  - Dimensions: {w_m} x {h_m} m")
        print(f"  - Area: {area_m2} m²")
        
        if room['objects_inside']:
            obj_names = [obj['id'] for obj in room['objects_inside']]
            print(f"  - Objects Contained: {len(obj_names)} ({', '.join(obj_names)})")
        else:
            print(f"  - Objects Contained: 0")
