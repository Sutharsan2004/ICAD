


## Wall, object and room detection with 70% accuracy. Incorrect measurements



# import matplotlib.pyplot as plt
# import os
# import math
# from dotenv import load_dotenv
# import ezdxf
# from ezdxf import path 
# from openai import OpenAI
# import networkx as nx
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
#         print(f"  -> Kept {len(msp)} entities across {len(include_layers)} layers.")
#         print(f"  -> Success! Cleaned DXF saved as: {output_filepath}")
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
#     except Exception as e:
#         print(f"Error reading scale, defaulting to 1.0: {e}")
#         return 1.0

# # ==========================================
# # 2. VISUALIZATION ENGINE
# # ==========================================

# def visualize_results(wall_lines, rooms, objects_data):
#     """
#     UPDATED: Renders distinct colors and strict Z-ordering so walls are never hidden.
#     """
#     plt.figure(figsize=(12, 8))
    
#     # LAYER 1 (Bottom): Rooms
#     for room in rooms:
#         poly = room.get('polygon')
#         if poly and poly.geom_type == 'Polygon':
#             x, y = poly.exterior.xy
#             # Light blue fill, no borders (let the walls act as the visual borders)
#             plt.fill(x, y, alpha=0.35, color='dodgerblue', edgecolor='none', zorder=1)
            
#     # LAYER 2 (Middle): Structural Walls
#     for i, line in enumerate(wall_lines):
#         x_coords = [line[0][0], line[1][0]]
#         y_coords = [line[0][1], line[1][1]]
#         label = 'Structural Walls' if i == 0 else ""
#         plt.plot(x_coords, y_coords, color='black', linewidth=2.5, zorder=2, label=label)
        
#     # LAYER 3 (Top): Objects
#     if objects_data:
#         obj_x = [obj['center_x'] for obj in objects_data]
#         obj_y = [obj['center_y'] for obj in objects_data]
#         plt.scatter(obj_x, obj_y, color='red', s=25, label='Detected Objects', zorder=3)
        
#     plt.title("CAD R&D: Extracted Rooms, Walls, and Objects")
#     plt.xlabel("X units (true mm)")
#     plt.ylabel("Y units (true mm)")
#     plt.axis('equal') 
#     plt.legend()
#     plt.grid(True, linestyle='--', alpha=0.3)
#     plt.show()

# def visualize_debug_walls_vs_objects(wall_lines, objects_data):
#     plt.figure(figsize=(12, 8))
    
#     for i, line in enumerate(wall_lines):
#         x_coords = [line[0][0], line[1][0]]
#         y_coords = [line[0][1], line[1][1]]
#         label = 'Structural Wall' if i == 0 else ""
#         plt.plot(x_coords, y_coords, color='blue', linewidth=1.5, zorder=1, label=label)
        
#     if objects_data:
#         obj_x = [obj['center_x'] for obj in objects_data]
#         obj_y = [obj['center_y'] for obj in objects_data]
#         plt.scatter(obj_x, obj_y, color='red', s=20, label='Classified as Object', zorder=2)
        
#     plt.title("DEBUG MODE: Wall vs. Object Classification")
#     plt.xlabel("X units (true mm)")
#     plt.ylabel("Y units (true mm)")
#     plt.axis('equal') 
#     plt.legend()
#     plt.grid(True, linestyle='--', alpha=0.5)
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
#     except Exception as e:
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

# def extract_dxf_geometry(filepath, scale=1.0):
#     try:
#         doc = ezdxf.readfile(filepath)
#         msp = doc.modelspace()
#     except Exception as e:
#         return []

#     raw_lines = []
#     for entity in msp.query('LINE LWPOLYLINE POLYLINE INSERT ARC CIRCLE ELLIPSE SPLINE'):
#         process_cad_entity(entity, raw_lines, scale)
#     return raw_lines

# # ==========================================
# # 4. FILTERING & MEASUREMENT ENGINE
# # ==========================================

# def extract_objects_and_walls(raw_lines, gap_tolerance=15, min_obj_size=300, max_obj_size=4000):
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
#     objects_data = []
    
#     for comp in nx.connected_components(G):
#         cluster_lines = [raw_lines[idx] for idx in comp]
#         mls = MultiLineString([LineString(l) for l in cluster_lines])
        
#         minx, miny, maxx, maxy = mls.bounds
#         diag = math.hypot(maxx - minx, maxy - miny)
        
#         if min_obj_size <= diag <= max_obj_size: 
#             obj_w = maxx - minx
#             obj_h = maxy - miny
#             objects_data.append({
#                 "object_id": f"Obj_{len(objects_data)+1}",
#                 "length": round(max(obj_w, obj_h), 2),
#                 "width": round(min(obj_w, obj_h), 2),
#                 "center_x": round(mls.centroid.x, 2),
#                 "center_y": round(mls.centroid.y, 2),
#                 "point": mls.centroid
#             })
#         elif diag > max_obj_size:
#             wall_lines.extend(cluster_lines)
            
#     return wall_lines, objects_data


# def extract_measurements(wall_lines, extracted_objects, max_door_width=3000, min_room_area=1500000):
#     """
#     UPDATED: 
#     1. Increased max_door_width to 3000mm to seal open-plan leaks.
#     2. Any closed polygon smaller than min_room_area is now converted to an Object.
#     """
#     if not wall_lines: 
#         return []
        
#     shapely_lines = [LineString(l) for l in wall_lines]
#     merged_walls = unary_union(shapely_lines)
    
#     if merged_walls.geom_type == 'LineString':
#         lines_list = [merged_walls]
#     elif merged_walls.geom_type == 'MultiLineString':
#         lines_list = list(merged_walls.geoms)
#     else:
#         return []

#     endpoints = []
#     for line in lines_list:
#         endpoints.append(Point(line.coords[0]))
#         endpoints.append(Point(line.coords[-1]))
        
#     invisible_doors = []
#     lines_tree = STRtree(lines_list)
    
#     for ep in endpoints:
#         nearest_idx = lines_tree.nearest(ep)
#         if nearest_idx is not None:
#             if isinstance(nearest_idx, (list, tuple, set)) or type(nearest_idx).__name__ == 'ndarray':
#                  nearest_idx = nearest_idx[0] if len(nearest_idx) > 0 else None
            
#             if nearest_idx is not None:
#                 nearest_line = lines_list[nearest_idx]
#                 dist = ep.distance(nearest_line)
                
#                 if 0 < dist <= max_door_width:
#                     nearest_pt = nearest_line.interpolate(nearest_line.project(ep))
#                     invisible_doors.append(LineString([ep, nearest_pt]))
            
#     all_geometry = lines_list + invisible_doors
#     noded_geometry = unary_union(all_geometry)
#     raw_polygons = list(polygonize(noded_geometry))
    
#     min_x, min_y, max_x, max_y = noded_geometry.bounds
#     total_bbox_area = (max_x - min_x) * (max_y - min_y)
    
#     rooms_data = []
#     for poly in raw_polygons:
#         area = poly.area 
#         rm_minx, rm_miny, rm_maxx, rm_maxy = poly.bounds
#         width = rm_maxx - rm_minx
#         height = rm_maxy - rm_miny
        
#         # 1. Is it big enough to be a room?
#         if area >= min_room_area:
#             rooms_data.append({
#                 "room_id": f"Room_{len(rooms_data)+1}",
#                 "width": round(width, 2),
#                 "height": round(height, 2),
#                 "area": round(area, 2),
#                 "polygon": poly,
#                 "objects_inside": []
#             })
#         # 2. Is it a closed loop, but too small to be a room? (Convert to Object)
#         elif 50000 <= area < min_room_area: # Ignore microscopic drafting fragments < 50,000 mm2
#             extracted_objects.append({
#                 "object_id": f"Obj_{len(extracted_objects)+1}_(ClosedPoly)",
#                 "length": round(max(width, height), 2),
#                 "width": round(min(width, height), 2),
#                 "center_x": round(poly.centroid.x, 2),
#                 "center_y": round(poly.centroid.y, 2),
#                 "point": poly.centroid
#             })

#     clean_rooms = []
#     for i, room in enumerate(rooms_data):
#         is_invalid = False
#         if room['area'] > (total_bbox_area * 0.5): 
#             continue
            
#         for j, other_room in enumerate(rooms_data):
#             if i != j:
#                 if room['polygon'].contains(other_room['polygon'].representative_point()):
#                     is_invalid = True
#                     break 
#                 intersection = room['polygon'].intersection(other_room['polygon'])
#                 if intersection.area > (0.8 * room['polygon'].area):
#                     if room['area'] < other_room['area']:
#                         is_invalid = True
#                         break
#                     elif room['area'] == other_room['area'] and i > j:
#                         is_invalid = True
#                         break
                        
#         if not is_invalid:
#             clean_rooms.append(room)
            
#     return sorted(clean_rooms, key=lambda x: x['area'], reverse=True)

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
    
#     LAYERS_TO_SHOW = ["Base", "Wall", "Walls", "Structural", "0", "Doors", "Windows"] 
    
#     DEBUG_MODE = True 
    
#     print(f"--- Processing {os.path.basename(RAW_DXF_FILE)} ---")
    
#     success = filter_dxf_layers(RAW_DXF_FILE, CLEAN_DXF_FILE, LAYERS_TO_SHOW)
#     if not success:
#         print("Fatal Error: Could not generate the clean DXF file. Exiting.")
#         exit()
        
#     print(f"\n[+] Extracting data from the filtered file: {os.path.basename(CLEAN_DXF_FILE)}")
    
#     DRAWING_SCALE = get_dxf_scale_to_mm(CLEAN_DXF_FILE)
    
#     print("\n[+] Extracting Semantic Text Annotations...")
#     all_texts = get_all_texts(CLEAN_DXF_FILE)
#     for text in all_texts:
#         text['x'] *= DRAWING_SCALE
#         text['y'] *= DRAWING_SCALE
        
#     print("\n[+] Extracting Geometry & Normalizing Scale...")
#     all_lines = extract_dxf_geometry(CLEAN_DXF_FILE, scale=DRAWING_SCALE)
#     print(f"  - Extracted {len(all_lines)} raw line segments.")
    
#     print("\n[+] Classifying Walls vs. Objects using Graph Connectivity...")
#     wall_lines, extracted_objects = extract_objects_and_walls(all_lines)
#     print(f"  - Isolated {len(wall_lines)} structural wall segments.")
#     print(f"  - Detected {len(extracted_objects)} interior objects.")

#     if DEBUG_MODE:
#         print("\n[DEBUG] Pausing to show the structural skeleton. Close the plot window to continue...")
#         visualize_debug_walls_vs_objects(wall_lines, extracted_objects)

#     print("\n[+] Running Polygonize Engine to extract discrete rooms...")
#     # Pass the extracted_objects list in so small polygons can be appended to it!
#     rooms = extract_measurements(wall_lines, extracted_objects) 
        
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

#     print("\n[+] Generating Visual Plot...")
#     visualize_results(wall_lines, rooms, extracted_objects)

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
from dotenv import load_dotenv
import ezdxf
from ezdxf import path 
from openai import OpenAI
import networkx as nx
from shapely.geometry import Point, LineString, Polygon, MultiPoint, MultiLineString
from shapely.ops import polygonize, unary_union
from shapely.strtree import STRtree

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
        print(f"  -> Kept {len(msp)} entities across {len(include_layers)} layers.")
        print(f"  -> Success! Cleaned DXF saved as: {output_filepath}")
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
    except Exception as e:
        print(f"Error reading scale, defaulting to 1.0: {e}")
        return 1.0

# ==========================================
# 2. VISUALIZATION ENGINE
# ==========================================

def visualize_results(wall_lines, rooms, objects_data):
    """
    UPDATED: Adds room name labels to the center of each room.
    """
    plt.figure(figsize=(14, 10)) # Slightly larger plot for labels
    
    # LAYER 1 (Bottom): Rooms & Labels
    for room in rooms:
        poly = room.get('polygon')
        if poly and poly.geom_type == 'Polygon':
            x, y = poly.exterior.xy
            plt.fill(x, y, alpha=0.35, color='dodgerblue', edgecolor='none', zorder=1)
            
            # Add Room Name Label
            centroid = poly.centroid
            plt.text(centroid.x, centroid.y, room['name'], 
                     fontsize=9, ha='center', va='center', weight='bold',
                     bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1.5), zorder=4)
            
    # LAYER 2 (Middle): Structural Walls
    for i, line in enumerate(wall_lines):
        x_coords = [line[0][0], line[1][0]]
        y_coords = [line[0][1], line[1][1]]
        label = 'Structural Walls' if i == 0 else ""
        plt.plot(x_coords, y_coords, color='black', linewidth=2.5, zorder=2, label=label)
        
    # LAYER 3 (Top): Objects
    if objects_data:
        obj_x = [obj['center_x'] for obj in objects_data]
        obj_y = [obj['center_y'] for obj in objects_data]
        plt.scatter(obj_x, obj_y, color='red', s=25, label='Detected Objects', zorder=3)
        
    plt.title("CAD R&D: Extracted Rooms, Walls, and Objects with Labels")
    plt.xlabel("X units (true mm)")
    plt.ylabel("Y units (true mm)")
    plt.axis('equal') 
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.3)
    plt.show()

def visualize_debug_walls_vs_objects(wall_lines, objects_data):
    plt.figure(figsize=(12, 8))
    
    for i, line in enumerate(wall_lines):
        x_coords = [line[0][0], line[1][0]]
        y_coords = [line[0][1], line[1][1]]
        label = 'Structural Wall' if i == 0 else ""
        plt.plot(x_coords, y_coords, color='blue', linewidth=1.5, zorder=1, label=label)
        
    if objects_data:
        obj_x = [obj['center_x'] for obj in objects_data]
        obj_y = [obj['center_y'] for obj in objects_data]
        plt.scatter(obj_x, obj_y, color='red', s=20, label='Classified as Object', zorder=2)
        
    plt.title("DEBUG MODE: Wall vs. Object Classification")
    plt.xlabel("X units (true mm)")
    plt.ylabel("Y units (true mm)")
    plt.axis('equal') 
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.show()

# ==========================================
# 3. TEXT & GEOMETRY EXTRACTION
# ==========================================

def extract_dxf_text(entity, texts_list):
    if entity.dxftype() == 'TEXT':
        texts_list.append({"text": entity.dxf.text, "x": entity.dxf.insert.x, "y": entity.dxf.insert.y})
    elif entity.dxftype() == 'MTEXT':
        texts_list.append({"text": entity.text, "x": entity.dxf.insert.x, "y": entity.dxf.insert.y})
    elif entity.dxftype() == 'INSERT':
        for sub_entity in entity.virtual_entities():
            extract_dxf_text(sub_entity, texts_list)

def get_all_texts(filepath):
    try:
        doc = ezdxf.readfile(filepath)
        msp = doc.modelspace()
    except Exception as e:
        return []

    texts = []
    for entity in msp.query('TEXT MTEXT INSERT'):
        extract_dxf_text(entity, texts)
    return texts

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

def extract_dxf_geometry(filepath, scale=1.0):
    try:
        doc = ezdxf.readfile(filepath)
        msp = doc.modelspace()
    except Exception as e:
        return []

    raw_lines = []
    for entity in msp.query('LINE LWPOLYLINE POLYLINE INSERT ARC CIRCLE ELLIPSE SPLINE'):
        process_cad_entity(entity, raw_lines, scale)
    return raw_lines

# ==========================================
# 4. FILTERING & MEASUREMENT ENGINE
# ==========================================

def extract_objects_and_walls(raw_lines, gap_tolerance=15, min_obj_size=300, max_obj_size=4000):
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
    objects_data = []
    
    for comp in nx.connected_components(G):
        cluster_lines = [raw_lines[idx] for idx in comp]
        mls = MultiLineString([LineString(l) for l in cluster_lines])
        
        minx, miny, maxx, maxy = mls.bounds
        diag = math.hypot(maxx - minx, maxy - miny)
        
        if min_obj_size <= diag <= max_obj_size: 
            obj_w = maxx - minx
            obj_h = maxy - miny
            objects_data.append({
                "object_id": f"Obj_{len(objects_data)+1}",
                "length": round(max(obj_w, obj_h), 2),
                "width": round(min(obj_w, obj_h), 2),
                "center_x": round(mls.centroid.x, 2),
                "center_y": round(mls.centroid.y, 2),
                "point": mls.centroid
            })
        elif diag > max_obj_size:
            wall_lines.extend(cluster_lines)
            
    return wall_lines, objects_data


def extract_measurements(wall_lines, extracted_objects, max_door_width=2000, min_room_area=1500000):
    """
    REFINEMENT: Reduced max_door_width to 2000mm to prevent distinct rooms from merging.
    """
    if not wall_lines: 
        return []
        
    shapely_lines = [LineString(l) for l in wall_lines]
    merged_walls = unary_union(shapely_lines)
    
    if merged_walls.geom_type == 'LineString':
        lines_list = [merged_walls]
    elif merged_walls.geom_type == 'MultiLineString':
        lines_list = list(merged_walls.geoms)
    else:
        return []

    endpoints = []
    for line in lines_list:
        endpoints.append(Point(line.coords[0]))
        endpoints.append(Point(line.coords[-1]))
        
    invisible_doors = []
    lines_tree = STRtree(lines_list)
    
    for ep in endpoints:
        nearest_idx = lines_tree.nearest(ep)
        if nearest_idx is not None:
            if isinstance(nearest_idx, (list, tuple, set)) or type(nearest_idx).__name__ == 'ndarray':
                 nearest_idx = nearest_idx[0] if len(nearest_idx) > 0 else None
            
            if nearest_idx is not None:
                nearest_line = lines_list[nearest_idx]
                dist = ep.distance(nearest_line)
                
                if 0 < dist <= max_door_width:
                    nearest_pt = nearest_line.interpolate(nearest_line.project(ep))
                    invisible_doors.append(LineString([ep, nearest_pt]))
            
    all_geometry = lines_list + invisible_doors
    noded_geometry = unary_union(all_geometry)
    raw_polygons = list(polygonize(noded_geometry))
    
    min_x, min_y, max_x, max_y = noded_geometry.bounds
    total_bbox_area = (max_x - min_x) * (max_y - min_y)
    
    rooms_data = []
    for poly in raw_polygons:
        area = poly.area 
        rm_minx, rm_miny, rm_maxx, rm_maxy = poly.bounds
        width = rm_maxx - rm_minx
        height = rm_maxy - rm_miny
        
        # 1. Is it big enough to be a room? (> 1.5m^2)
        if area >= min_room_area:
            rooms_data.append({
                "room_id": f"Room_{len(rooms_data)+1}",
                "width": round(width, 2),
                "height": round(height, 2),
                "area": round(area, 2),
                "polygon": poly,
                "objects_inside": []
            })
        # 2. Is it a closed loop, but too small to be a room? (Convert to Object)
        # Slightly raised lower bound to avoid tiny math noise
        elif 100000 <= area < min_room_area: 
            extracted_objects.append({
                "object_id": f"Obj_{len(extracted_objects)+1}_(ClosedPoly)",
                "length": round(max(width, height), 2),
                "width": round(min(width, height), 2),
                "center_x": round(poly.centroid.x, 2),
                "center_y": round(poly.centroid.y, 2),
                "point": poly.centroid
            })

    clean_rooms = []
    for i, room in enumerate(rooms_data):
        is_invalid = False
        if room['area'] > (total_bbox_area * 0.5): 
            continue
            
        for j, other_room in enumerate(rooms_data):
            if i != j:
                if room['polygon'].contains(other_room['polygon'].representative_point()):
                    is_invalid = True
                    break 
                intersection = room['polygon'].intersection(other_room['polygon'])
                if intersection.area > (0.8 * room['polygon'].area):
                    if room['area'] < other_room['area']:
                        is_invalid = True
                        break
                    elif room['area'] == other_room['area'] and i > j:
                        is_invalid = True
                        break
                        
        if not is_invalid:
            clean_rooms.append(room)
            
    return sorted(clean_rooms, key=lambda x: x['area'], reverse=True)

def generate_room_name(width, height, text_context):
    context_str = ", ".join(text_context) if text_context else "No text labels found."
    prompt = f"""
    You are an expert architectural CAD assistant. I have mathematically extracted a partitioned zone from a floorplan.
    Zone Dimensions: {width} units by {height} units.
    Text annotations found inside this zone: [{context_str}]
    Based on the size and the text annotations, what is the most logical, professional name for this space?
    Reply ONLY with the room name. Do not include any other conversational text.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a CAD architectural assistant."},
                      {"role": "user", "content": prompt}],
            temperature=0.5
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Unnamed Partition"

# ==========================================
# 5. MAIN EXECUTION WORKFLOW
# ==========================================
if __name__ == "__main__":
    RAW_DXF_FILE = r"C:\Users\abine\OneDrive\Documents\Icebergs_sudharsan\CAD_R&D\Graph Based CAD\DXF_FIles\House Floor Plan Sample.dxf" 
    CLEAN_DXF_FILE = r"C:\Users\abine\OneDrive\Documents\Icebergs_sudharsan\CAD_R&D\Graph Based CAD\DXF_FIles\Cleaned_sample.dxf"
    
    LAYERS_TO_SHOW = ["Furniture", "Base", "Wall", "Walls", "Structural", "0", "Doors", "Windows"] 

    #LAYERS_TO_SHOW = ["GLASS", "MAIN", "MAIN-4", "SEC"]
    
    # You can turn debug off now that walls are verified
    DEBUG_MODE = False
    
    print(f"--- Processing {os.path.basename(RAW_DXF_FILE)} ---")
    
    success = filter_dxf_layers(RAW_DXF_FILE, CLEAN_DXF_FILE, LAYERS_TO_SHOW)
    if not success:
        print("Fatal Error: Could not generate the clean DXF file. Exiting.")
        exit()
        
    print(f"\n[+] Extracting data from the filtered file: {os.path.basename(CLEAN_DXF_FILE)}")
    
    DRAWING_SCALE = get_dxf_scale_to_mm(CLEAN_DXF_FILE)
    
    print("\n[+] Extracting Semantic Text Annotations...")
    all_texts = get_all_texts(CLEAN_DXF_FILE)
    for text in all_texts:
        text['x'] *= DRAWING_SCALE
        text['y'] *= DRAWING_SCALE
        
    print("\n[+] Extracting Geometry & Normalizing Scale...")
    all_lines = extract_dxf_geometry(CLEAN_DXF_FILE, scale=DRAWING_SCALE)
    print(f"  - Extracted {len(all_lines)} raw line segments.")
    
    print("\n[+] Classifying Walls vs. Objects using Graph Connectivity...")
    wall_lines, extracted_objects = extract_objects_and_walls(all_lines)
    print(f"  - Isolated {len(wall_lines)} structural wall segments.")
    print(f"  - Detected {len(extracted_objects)} interior objects.")

    if DEBUG_MODE:
        print("\n[DEBUG] Pausing to show the structural skeleton. Close the plot window to continue...")
        visualize_debug_walls_vs_objects(wall_lines, extracted_objects)

    print("\n[+] Running Polygonize Engine to extract discrete rooms...")
    rooms = extract_measurements(wall_lines, extracted_objects) 
        
    print("\n[+] Executing Spatial Mapping (Placing objects in rooms)...")
    for room in rooms:
        poly = room['polygon']
        usable_floor_space = poly.buffer(-50)
        
        for obj in extracted_objects:
            if usable_floor_space.covers(obj['point']): 
                room['objects_inside'].append({"id": obj['object_id'], "length": obj['length'], "width": obj['width']})
        
        catchment_area = poly.buffer(1000) 
        texts_in_room = [t['text'] for t in all_texts if catchment_area.contains(Point(t['x'], t['y']))]
        room['name'] = generate_room_name(room['width'], room['height'], texts_in_room)

    print("\n[+] Generating Visual Plot with Labels...")
    visualize_results(wall_lines, rooms, extracted_objects)

    for room in rooms:
        if 'polygon' in room:
            del room['polygon']

    print("\n--- FINAL GRANULAR MEASUREMENT RESULTS ---")
    for room in rooms:
        w_m = round(room['width'] / 1000, 2)
        h_m = round(room['height'] / 1000, 2)
        area_m2 = round(room['area'] / 1000000, 2)

        print(f"\n[{room['name']}]")
        print(f"  - Dimensions: {room['width']} x {room['height']} mm  ({w_m} x {h_m} m)")
        print(f"  - Area: {room['area']} mm²  ({area_m2} m²)")
        print(f"  - Objects Contained: {len(room['objects_inside'])}")










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
#         print(f"  -> Kept {len(msp)} entities across {len(include_layers)} layers.")
#         print(f"  -> Success! Cleaned DXF saved as: {output_filepath}")
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
#     except Exception as e:
#         print(f"Error reading scale, defaulting to 1.0: {e}")
#         return 1.0

# # ==========================================
# # 2. VISUALIZATION ENGINE
# # ==========================================

# def visualize_results(wall_lines, wall_cavities, rooms, objects_data):
#     """
#     Plots Rooms, Solid Wall Cavities, Wall Lines, and floating Objects.
#     """
#     plt.figure(figsize=(14, 10))
    
#     # LAYER 1: Rooms (Light Blue Fill)
#     for room in rooms:
#         poly = room.get('polygon')
#         if poly and poly.geom_type == 'Polygon':
#             x, y = poly.exterior.xy
#             plt.fill(x, y, alpha=0.35, color='dodgerblue', edgecolor='none', zorder=1)
            
#             # Add Room Name Label
#             centroid = poly.centroid
#             plt.text(centroid.x, centroid.y, room['name'], 
#                      fontsize=8, ha='center', va='center', weight='bold',
#                      bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=2), zorder=5)
            
#     # LAYER 2: Solid Wall Cavities (Dark Gray Fill for professional CAD look)
#     for cav in wall_cavities:
#         if cav.geom_type == 'Polygon':
#             x, y = cav.exterior.xy
#             plt.fill(x, y, alpha=1.0, color='dimgray', zorder=2)

#     # LAYER 3: Structural Wall Outlines
#     for i, line in enumerate(wall_lines):
#         x_coords = [line[0][0], line[1][0]]
#         y_coords = [line[0][1], line[1][1]]
#         label = 'Structural Walls' if i == 0 else ""
#         plt.plot(x_coords, y_coords, color='black', linewidth=1.5, zorder=3, label=label)
        
#     # LAYER 4: True Floating Objects (Red Dots)
#     if objects_data:
#         obj_x = [obj['center_x'] for obj in objects_data]
#         obj_y = [obj['center_y'] for obj in objects_data]
#         plt.scatter(obj_x, obj_y, color='red', s=25, label='Detected Objects', zorder=4)
        
#     plt.title("CAD R&D: Extracted Rooms, Solid Walls, and Objects")
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
#     except Exception as e:
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

# def extract_dxf_geometry(filepath, scale=1.0):
#     try:
#         doc = ezdxf.readfile(filepath)
#         msp = doc.modelspace()
#     except Exception as e:
#         return []

#     raw_lines = []
#     for entity in msp.query('LINE LWPOLYLINE POLYLINE INSERT ARC CIRCLE ELLIPSE SPLINE'):
#         process_cad_entity(entity, raw_lines, scale)
#     return raw_lines

# # ==========================================
# # 4. FILTERING & MEASUREMENT ENGINE
# # ==========================================

# def extract_objects_and_walls(raw_lines, gap_tolerance=15, min_obj_size=300, max_obj_size=4000):
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
#     objects_data = []
    
#     for comp in nx.connected_components(G):
#         cluster_lines = [raw_lines[idx] for idx in comp]
#         mls = MultiLineString([LineString(l) for l in cluster_lines])
        
#         minx, miny, maxx, maxy = mls.bounds
#         diag = math.hypot(maxx - minx, maxy - miny)
        
#         # Truly isolated lines form floating objects
#         if min_obj_size <= diag <= max_obj_size: 
#             obj_w = maxx - minx
#             obj_h = maxy - miny
#             objects_data.append({
#                 "object_id": f"Obj_{len(objects_data)+1}",
#                 "length": round(max(obj_w, obj_h), 2),
#                 "width": round(min(obj_w, obj_h), 2),
#                 "center_x": round(mls.centroid.x, 2),
#                 "center_y": round(mls.centroid.y, 2),
#                 "point": mls.centroid
#             })
#         elif diag > max_obj_size:
#             wall_lines.extend(cluster_lines)
            
#     return wall_lines, objects_data


# def extract_measurements(wall_lines, extracted_objects, max_door_width=2500, min_room_area=1500000):
#     if not wall_lines: 
#         return [], []
        
#     shapely_lines = [LineString(l) for l in wall_lines]
#     merged_walls = unary_union(shapely_lines)
    
#     if merged_walls.geom_type == 'LineString':
#         lines_list = [merged_walls]
#     elif merged_walls.geom_type == 'MultiLineString':
#         lines_list = list(merged_walls.geoms)
#     else:
#         return [], []

#     endpoints = []
#     for line in lines_list:
#         endpoints.append(Point(line.coords[0]))
#         endpoints.append(Point(line.coords[-1]))
        
#     invisible_doors = []
    
#     # 1. Cap Double-Line Wall Ends (<= 400mm) unconditionally
#     for i, ep1 in enumerate(endpoints):
#         for j, ep2 in enumerate(endpoints):
#             if i < j:
#                 if ep1.distance(ep2) <= 400:
#                     invisible_doors.append(LineString([ep1, ep2]))

#     # 2. Line-of-Sight Doorway Bridging (400mm to 2500mm)
#     # This throws a web across open doorways, instantly sealing them.
#     for i, ep1 in enumerate(endpoints):
#         for j, ep2 in enumerate(endpoints):
#             if i < j:
#                 dist = ep1.distance(ep2)
#                 if 400 < dist <= max_door_width:
#                     bridge = LineString([ep1, ep2])
#                     # Topologically check if the bridge slices through a solid wall
#                     if not bridge.crosses(merged_walls):
#                         invisible_doors.append(bridge)
                            
#     # Combine walls and the new doorway mesh
#     all_geometry = lines_list + invisible_doors
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
        
#         # Room classification
#         if area >= min_room_area:
#             rooms_data.append({
#                 "room_id": f"Room_{len(rooms_data)+1}",
#                 "width": round(width, 2),
#                 "height": round(height, 2),
#                 "area": round(area, 2),
#                 "polygon": poly,
#                 "objects_inside": []
#             })
#         # Wall cavity classification
#         elif 10000 < area < min_room_area: 
#             wall_cavities.append(poly)

#     # Filter nested duplicate polygons
#     clean_rooms = []
#     for i, room in enumerate(rooms_data):
#         is_invalid = False
#         if room['area'] > (total_bbox_area * 0.4): # Drop massive outer world polygons
#             continue
            
#         for j, other_room in enumerate(rooms_data):
#             if i != j:
#                 if room['polygon'].contains(other_room['polygon'].representative_point()):
#                     is_invalid = True
#                     break 
#                 intersection = room['polygon'].intersection(other_room['polygon'])
#                 if intersection.area > (0.8 * room['polygon'].area):
#                     if room['area'] > other_room['area']: 
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
    
#     LAYERS_TO_SHOW = ["Base", "Wall", "Walls", "Structural", "0", "Doors", "Windows"] 
    
#     print(f"--- Processing {os.path.basename(RAW_DXF_FILE)} ---")
    
#     success = filter_dxf_layers(RAW_DXF_FILE, CLEAN_DXF_FILE, LAYERS_TO_SHOW)
#     if not success:
#         print("Fatal Error: Could not generate the clean DXF file. Exiting.")
#         exit()
        
#     print(f"\n[+] Extracting data from the filtered file: {os.path.basename(CLEAN_DXF_FILE)}")
    
#     DRAWING_SCALE = get_dxf_scale_to_mm(CLEAN_DXF_FILE)
    
#     print("\n[+] Extracting Semantic Text Annotations...")
#     all_texts = get_all_texts(CLEAN_DXF_FILE)
#     for text in all_texts:
#         text['x'] *= DRAWING_SCALE
#         text['y'] *= DRAWING_SCALE
        
#     print("\n[+] Extracting Geometry & Normalizing Scale...")
#     all_lines = extract_dxf_geometry(CLEAN_DXF_FILE, scale=DRAWING_SCALE)
    
#     print("\n[+] Classifying Walls vs. Objects using Graph Connectivity...")
#     wall_lines, extracted_objects = extract_objects_and_walls(all_lines)

#     print("\n[+] Running Polygonize Engine to extract discrete rooms...")
#     rooms, wall_cavities = extract_measurements(wall_lines) 
        
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

#     print("\n[+] Generating Visual Plot with Labels...")
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
#         print(f"  -> Kept {len(msp)} entities across {len(include_layers)} layers.")
#         print(f"  -> Success! Cleaned DXF saved as: {output_filepath}")
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
#     except Exception as e:
#         print(f"Error reading scale, defaulting to 1.0: {e}")
#         return 1.0

# # ==========================================
# # 2. VISUALIZATION ENGINE
# # ==========================================

# def visualize_results(wall_lines, wall_cavities, rooms, objects_data):
#     """
#     Plots Rooms, Solid Wall Cavities, Wall Lines, and floating Objects.
#     """
#     plt.figure(figsize=(14, 10))
    
#     # LAYER 1: Rooms (Light Blue Fill)
#     for room in rooms:
#         poly = room.get('polygon')
#         if poly and poly.geom_type == 'Polygon':
#             x, y = poly.exterior.xy
#             plt.fill(x, y, alpha=0.35, color='dodgerblue', edgecolor='none', zorder=1)
            
#             # Add Room Name Label
#             centroid = poly.centroid
#             plt.text(centroid.x, centroid.y, room['name'], 
#                      fontsize=8, ha='center', va='center', weight='bold',
#                      bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=2), zorder=5)
            
#     # LAYER 2: Solid Wall Cavities (Dark Gray Fill for professional CAD look)
#     for cav in wall_cavities:
#         if cav.geom_type == 'Polygon':
#             x, y = cav.exterior.xy
#             plt.fill(x, y, alpha=1.0, color='dimgray', zorder=2)

#     # LAYER 3: Structural Wall Outlines
#     for i, line in enumerate(wall_lines):
#         x_coords = [line[0][0], line[1][0]]
#         y_coords = [line[0][1], line[1][1]]
#         label = 'Structural Walls' if i == 0 else ""
#         plt.plot(x_coords, y_coords, color='black', linewidth=1.5, zorder=3, label=label)
        
#     # LAYER 4: True Floating Objects (Red Dots)
#     if objects_data:
#         obj_x = [obj['center_x'] for obj in objects_data]
#         obj_y = [obj['center_y'] for obj in objects_data]
#         plt.scatter(obj_x, obj_y, color='red', s=25, label='Detected Objects', zorder=4)
        
#     plt.title("CAD R&D: Extracted Rooms, Solid Walls, and Objects")
#     plt.xlabel("X units (true mm)")
#     plt.ylabel("Y units (true mm)")
#     plt.axis('equal') 
#     plt.legend()
#     plt.grid(True, linestyle='--', alpha=0.3)
#     plt.show()

# def visualize_debug_walls_vs_objects(wall_lines, objects_data):
#     """
#     DEBUG MODE: Plots only the classified walls and object centroids.
#     """
#     plt.figure(figsize=(12, 8))
#     for i, line in enumerate(wall_lines):
#         x_coords = [line[0][0], line[1][0]]
#         y_coords = [line[0][1], line[1][1]]
#         label = 'Structural Wall' if i == 0 else ""
#         plt.plot(x_coords, y_coords, color='blue', linewidth=1.5, zorder=1, label=label)
        
#     if objects_data:
#         obj_x = [obj['center_x'] for obj in objects_data]
#         obj_y = [obj['center_y'] for obj in objects_data]
#         plt.scatter(obj_x, obj_y, color='red', s=20, label='Classified as Object', zorder=2)
        
#     plt.title("DEBUG MODE: Wall vs. Object Classification")
#     plt.xlabel("X units (true mm)")
#     plt.ylabel("Y units (true mm)")
#     plt.axis('equal') 
#     plt.legend()
#     plt.grid(True, linestyle='--', alpha=0.5)
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
#     except Exception as e:
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

# def extract_dxf_geometry(filepath, scale=1.0):
#     try:
#         doc = ezdxf.readfile(filepath)
#         msp = doc.modelspace()
#     except Exception as e:
#         return []

#     raw_lines = []
#     for entity in msp.query('LINE LWPOLYLINE POLYLINE INSERT ARC CIRCLE ELLIPSE SPLINE'):
#         process_cad_entity(entity, raw_lines, scale)
#     return raw_lines

# # ==========================================
# # 4. FILTERING & MEASUREMENT ENGINE
# # ==========================================

# def extract_objects_and_walls(raw_lines, gap_tolerance=15, min_obj_size=300, max_obj_size=4000):
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
#     objects_data = []
    
#     for comp in nx.connected_components(G):
#         cluster_lines = [raw_lines[idx] for idx in comp]
#         mls = MultiLineString([LineString(l) for l in cluster_lines])
        
#         minx, miny, maxx, maxy = mls.bounds
#         diag = math.hypot(maxx - minx, maxy - miny)
        
#         if min_obj_size <= diag <= max_obj_size: 
#             obj_w = maxx - minx
#             obj_h = maxy - miny
#             objects_data.append({
#                 "object_id": f"Obj_{len(objects_data)+1}",
#                 "length": round(max(obj_w, obj_h), 2),
#                 "width": round(min(obj_w, obj_h), 2),
#                 "center_x": round(mls.centroid.x, 2),
#                 "center_y": round(mls.centroid.y, 2),
#                 "point": mls.centroid
#             })
#         elif diag > max_obj_size:
#             wall_lines.extend(cluster_lines)
            
#     return wall_lines, objects_data

# def extract_measurements(wall_lines, max_door_width=2500, min_room_area=1500000):
#     if not wall_lines: 
#         return [], []
        
#     shapely_lines = [LineString(l) for l in wall_lines]
#     merged_walls = unary_union(shapely_lines)
    
#     if merged_walls.geom_type == 'LineString':
#         lines_list = [merged_walls]
#     elif merged_walls.geom_type == 'MultiLineString':
#         lines_list = list(merged_walls.geoms)
#     else:
#         return [], []

#     endpoints = []
#     for line in lines_list:
#         endpoints.append(Point(line.coords[0]))
#         endpoints.append(Point(line.coords[-1]))
        
#     invisible_doors = []
    
#     # 1. Cap Double-Line Wall Ends (<= 400mm) unconditionally
#     for i, ep1 in enumerate(endpoints):
#         for j, ep2 in enumerate(endpoints):
#             if i < j:
#                 if ep1.distance(ep2) <= 400:
#                     invisible_doors.append(LineString([ep1, ep2]))

#     # 2. Line-of-Sight Doorway Bridging (400mm to 2500mm)
#     for i, ep1 in enumerate(endpoints):
#         for j, ep2 in enumerate(endpoints):
#             if i < j:
#                 dist = ep1.distance(ep2)
#                 if 400 < dist <= max_door_width:
#                     bridge = LineString([ep1, ep2])
#                     if not bridge.crosses(merged_walls):
#                         invisible_doors.append(bridge)
                            
#     # Combine walls and the new doorway mesh
#     all_geometry = lines_list + invisible_doors
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
        
#         # Room classification
#         if area >= min_room_area:
#             rooms_data.append({
#                 "room_id": f"Room_{len(rooms_data)+1}",
#                 "width": round(width, 2),
#                 "height": round(height, 2),
#                 "area": round(area, 2),
#                 "polygon": poly,
#                 "objects_inside": []
#             })
#         # Wall cavity classification
#         elif 10000 < area < min_room_area: 
#             wall_cavities.append(poly)

#     # Filter nested duplicate polygons
#     clean_rooms = []
#     for i, room in enumerate(rooms_data):
#         is_invalid = False
#         if room['area'] > (total_bbox_area * 0.4): 
#             continue
            
#         for j, other_room in enumerate(rooms_data):
#             if i != j:
#                 if room['polygon'].contains(other_room['polygon'].representative_point()):
#                     is_invalid = True
#                     break 
#                 intersection = room['polygon'].intersection(other_room['polygon'])
#                 if intersection.area > (0.8 * room['polygon'].area):
#                     if room['area'] > other_room['area']: 
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
    
#     LAYERS_TO_SHOW = ["Base", "Wall", "Walls", "Structural", "0", "Doors", "Windows"] 
    
#     DEBUG_MODE = False
    
#     print(f"--- Processing {os.path.basename(RAW_DXF_FILE)} ---")
    
#     success = filter_dxf_layers(RAW_DXF_FILE, CLEAN_DXF_FILE, LAYERS_TO_SHOW)
#     if not success:
#         print("Fatal Error: Could not generate the clean DXF file. Exiting.")
#         exit()
        
#     print(f"\n[+] Extracting data from the filtered file: {os.path.basename(CLEAN_DXF_FILE)}")
    
#     DRAWING_SCALE = get_dxf_scale_to_mm(CLEAN_DXF_FILE)
    
#     print("\n[+] Extracting Semantic Text Annotations...")
#     all_texts = get_all_texts(CLEAN_DXF_FILE)
#     for text in all_texts:
#         text['x'] *= DRAWING_SCALE
#         text['y'] *= DRAWING_SCALE
        
#     print("\n[+] Extracting Geometry & Normalizing Scale...")
#     all_lines = extract_dxf_geometry(CLEAN_DXF_FILE, scale=DRAWING_SCALE)
#     print(f"  - Extracted {len(all_lines)} raw line segments.")
    
#     print("\n[+] Classifying Walls vs. Objects using Graph Connectivity...")
#     wall_lines, extracted_objects = extract_objects_and_walls(all_lines)
#     print(f"  - Isolated {len(wall_lines)} structural wall segments.")
#     print(f"  - Detected {len(extracted_objects)} interior objects.")

#     if DEBUG_MODE:
#         print("\n[DEBUG] Pausing to show the structural skeleton. Close the plot window to continue...")
#         visualize_debug_walls_vs_objects(wall_lines, extracted_objects)

#     print("\n[+] Running Polygonize Engine to extract discrete rooms...")
#     rooms, wall_cavities = extract_measurements(wall_lines) 
        
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

#     print("\n[+] Generating Visual Plot with Labels...")
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
