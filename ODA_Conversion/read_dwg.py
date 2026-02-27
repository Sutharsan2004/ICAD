import os
import json
import shutil
import subprocess
import ezdxf
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

# ==========================================
# 1. CONVERSION LAYER (DWG -> DXF)
# ==========================================

def convert_dwg_to_dxf(dwg_filepath: str) -> str:
    """
    Converts a DWG file to DXF using the ODA File Converter.
    Note: ODA requires input and output DIRECTORIES, not file paths.
    """
    print(f"Starting conversion for: {dwg_filepath}")
    
    # Setup paths
    base_dir = os.path.dirname(os.path.abspath(dwg_filepath))
    filename = os.path.basename(dwg_filepath)
    filename_no_ext = os.path.splitext(filename)[0]
    
    # Create temporary input/output directories for ODA
    input_dir = os.path.join(base_dir, "temp_oda_in")
    output_dir = os.path.join(base_dir, "temp_oda_out")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    # Copy the target DWG into the input directory
    temp_dwg_path = os.path.join(input_dir, filename)
    shutil.copy2(dwg_filepath, temp_dwg_path)
    
    # Path to the ODA executable (Update this based on your OS)
    # Windows: "C:\\Program Files\\ODA\\ODAFileConverter\\ODAFileConverter.exe"
    # Mac: "/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter"
    # Linux: "ODAFileConverter"
    oda_executable = "C:\Program Files\ODA\ODAFileConverter 26.12.0\ODAFileConverter.exe" 
    
    # ODA CLI Arguments: "Input_Dir" "Output_Dir" "Version" "Output_Format" "Recurse" "Audit"
    try:
        subprocess.run([
            oda_executable, 
            input_dir, 
            output_dir, 
            "ACAD2018", # AutoCAD version to output
            "DXF",      # Target format
            "0",        # Don't recurse subfolders
            "1"         # Audit file
        ], check=True, capture_output=True)
    except FileNotFoundError:
        raise Exception("ODA File Converter not found. Please install it and check the path.")
    except subprocess.CalledProcessError as e:
        raise Exception(f"ODA Conversion failed: {e.stderr.decode()}")

    # Find the newly created DXF
    dxf_filename = f"{filename_no_ext}.dxf"
    output_dxf_path = os.path.join(output_dir, dxf_filename)
    final_dxf_path = os.path.join(base_dir, dxf_filename)
    
    # Move it to the main directory and clean up temp folders
    if os.path.exists(output_dxf_path):
        shutil.move(output_dxf_path, final_dxf_path)
        shutil.rmtree(input_dir)
        shutil.rmtree(output_dir)
        print(f"✅ Successfully converted to: {final_dxf_path}")
        return final_dxf_path
    else:
        raise Exception("Conversion completed, but output DXF was not found.")


# ==========================================
# 2. EXTRACTION LAYER (Parsing the DXF)
# ==========================================

# def extract_cad_context(dxf_filepath: str) -> str:
#     """
#     Reads the DXF file and extracts text labels, equipment names, 
#     and dimensions into a structured JSON string.
#     """
#     print(f"Extracting geometry from {dxf_filepath}...")
#     try:
#         doc = ezdxf.readfile(dxf_filepath)
#         msp = doc.modelspace()
#     except Exception as e:
#         return json.dumps({"error": f"Failed to read DXF: {str(e)}"})

#     cad_context = {
#         "text_labels": [],
#         "dimensions": []
#     }

#     # Extract all text (Rooms, Equipment names like "CHILLER-1")
#     for text in msp.query('TEXT MTEXT'):
#         text_content = text.dxf.text if text.dxftype() == 'TEXT' else text.text
#         if text_content.strip():
#             cad_context["text_labels"].append({
#                 "label": text_content.strip(),
#                 "x": round(text.dxf.insert.x, 2),
#                 "y": round(text.dxf.insert.y, 2)
#             })

#     # Extract Explicit Dimensions drawn on the file
#     for dim in msp.query('DIMENSION'):
#         try:
#             cad_context["dimensions"].append({
#                 "measurement": round(dim.get_measurement(), 2),
#                 "start_x": round(dim.dxf.def_point2.x, 2),
#                 "start_y": round(dim.dxf.def_point2.y, 2),
#                 "end_x": round(dim.dxf.def_point3.x, 2),
#                 "end_y": round(dim.dxf.def_point3.y, 2)
#             })
#         except Exception:
#             pass # Skip complex angular dims for now

#     return json.dumps(cad_context)

def extract_cad_context(dxf_filepath: str) -> str:
    """
    Reads the DXF file and extracts free text, block attributes, 
    and nested block text into a structured JSON string.
    """
    print(f"Extracting geometry from {dxf_filepath}...")
    try:
        doc = ezdxf.readfile(dxf_filepath)
        msp = doc.modelspace()
    except Exception as e:
        return json.dumps({"error": f"Failed to read DXF: {str(e)}"})

    cad_context = {
        "text_labels": [],
        "dimensions": []
    }

    # 1. EXTRACT FREE-FLOATING TEXT
    for text in msp.query('TEXT MTEXT'):
        text_content = text.dxf.text if text.dxftype() == 'TEXT' else text.text
        if text_content.strip():
            cad_context["text_labels"].append({
                "label": text_content.strip(),
                "x": round(text.dxf.insert.x, 2),
                "y": round(text.dxf.insert.y, 2)
            })

    # 2. EXTRACT BLOCKS (INSERT ENTITIES) & ATTRIBUTES
    for insert in msp.query('INSERT'):
        # A. Grab Block Attributes (Dynamic text attached to the block)
        if insert.has_attrib:  # FIXED: singular 'has_attrib'
            for attrib in insert.attribs:
                if attrib.dxf.text.strip():
                    cad_context["text_labels"].append({
                        "label": attrib.dxf.text.strip(),
                        "x": round(attrib.dxf.insert.x, 2),
                        "y": round(attrib.dxf.insert.y, 2),
                        "context": "Block Attribute"
                    })
        
        # B. Grab Nested Text (Static text inside the block definition)
        # virtual_entities() automatically calculates the correct global X/Y coordinates
        for entity in insert.virtual_entities():
            if entity.dxftype() in {'TEXT', 'MTEXT'}:
                text_content = entity.dxf.text if entity.dxftype() == 'TEXT' else entity.text
                if text_content.strip():
                    cad_context["text_labels"].append({
                        "label": text_content.strip(),
                        "x": round(entity.dxf.insert.x, 2),
                        "y": round(entity.dxf.insert.y, 2),
                        "context": f"Inside Block: {insert.dxf.name}"
                    })
    # 3. EXTRACT DIMENSIONS
    for dim in msp.query('DIMENSION'):
        try:
            cad_context["dimensions"].append({
                "measurement": round(dim.get_measurement(), 2),
                "start_x": round(dim.dxf.def_point2.x, 2),
                "start_y": round(dim.dxf.def_point2.y, 2),
                "end_x": round(dim.dxf.def_point3.x, 2),
                "end_y": round(dim.dxf.def_point3.y, 2)
            })
        except Exception:
            pass 

    # DEBUGGING: Print how many labels we found so you can verify before it hits the LLM
    print(f"Found {len(cad_context['text_labels'])} text labels and {len(cad_context['dimensions'])} dimensions.")

    return json.dumps(cad_context)

# ==========================================
# 3. LLM QUERY LAYER (Groq + LangChain)
# ==========================================

def query_hvac_drawing(dwg_filepath: str, user_question: str) -> str:
    """
    Orchestrates the conversion, extraction, and querying process.
    """
    # 1. Convert DWG to DXF (if it isn't already a DXF)
    if dwg_filepath.lower().endswith(".dwg"):
        dxf_filepath = convert_dwg_to_dxf(dwg_filepath)
    else:
        dxf_filepath = dwg_filepath
        
    # 2. Extract Data
    cad_json = extract_cad_context(dxf_filepath)
    # --- ADD THIS DEBUGGING BLOCK ---
    parsed_data = json.loads(cad_json)
    labels_only = [item['label'] for item in parsed_data['text_labels']]
    print("\n--- DEBUG: First 15 labels extracted from CAD ---")
    print(labels_only[:15])
    print("-------------------------------------------------\n")
    # --------------------------------
    
    # 3. Setup LLM
    llm = ChatGroq(
        temperature=0.1, 
        model_name="llama-3.3-70b-versatile",
        groq_api_key = ""
    )
    
    # 4. Prompt Engineering
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert HVAC CAD assistant. 
        You have been given the raw extracted JSON data from an HVAC architectural drawing.
        
        The data contains 'text_labels' (showing equipment names and coordinates) 
        and 'dimensions' (showing physical measurements and start/end coordinates).
        
        Answer the user's question based strictly on this spatial data. 
        If the user asks about something not in the JSON, politely state it isn't in the drawing.
        
        CAD DRAWING DATA:
        {cad_data}
        """),
        ("human", "{question}")
    ])
    
    chain = prompt | llm
    
    print("\nQuerying Llama 3 on Groq...")
    response = chain.invoke({
        "cad_data": cad_json,
        "question": user_question
    })
    
    return response.content

# ==========================================
# 4. EXECUTION
# ==========================================

if __name__ == "__main__":
    # Ensure your API key is exported in your terminal
    # Make sure 'sample_mall_hvac.dwg' exists in the same folder as this script
    my_dwg = "DWG_FILE_PATH"
    
    question = """
    Analyze the text labels in this drawing. 
    1. List the major HVAC equipment or room names you can identify.
    2. Group similar items together.
    3. Give me the coordinates for a few of the main AC units.
    """
    
    if os.path.exists(my_dwg):
        answer = query_hvac_drawing(my_dwg, question)
        print("\n--- AI Response ---")
        print(answer)
    else:
        print(f"Please place a valid DWG file named '{my_dwg}' in this directory to test.")
