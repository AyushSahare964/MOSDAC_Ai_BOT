# nlu_processor.py

import spacy
from config import KG_SCHEMA
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class NLUProcessor:
    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
            logging.info("spaCy model 'en_core_web_sm' loaded successfully.")
        except OSError:
            logging.error("spaCy model 'en_core_web_sm' not found. Please run 'python -m spacy download en_core_web_sm'")
            raise

        self.known_entity_labels = KG_SCHEMA["nodes"] # e.g., ["DataProduct", "Satellite", ...]
        self.known_relationship_types = KG_SCHEMA["relationships"]

        self.mosdac_keywords = {
            # Data Products (exact matches or common names)
            "sea surface temperature": "DataProduct",
            "cloud top pressure": "DataProduct",
            "rainfall data": "DataProduct",
            "humidity data": "DataProduct",
            "wind speed": "DataProduct",
            "vegetation index": "DataProduct",
            "soil moisture": "DataProduct",
            "ozone concentration": "DataProduct",
            "aerosol optical depth": "DataProduct",

            # Satellites
            "insat-3d": "Satellite",
            "insat-3dr": "Satellite", # Added
            "kalpana-1": "Satellite",
            "oceansat-2": "Satellite",
            "megha-tropiques": "Satellite",
            "scatsat-1": "Satellite",
            "gisat-1": "Satellite",

            # Sensors (if specific sensors are mentioned on the site)
            "imager": "Sensor",
            "sounder": "Sensor",
            "scatterometer": "Sensor",

            # Parameters
            "temperature": "Parameter",
            "pressure": "Parameter",
            "wind": "Parameter",
            "humidity": "Parameter",
            "rainfall": "Parameter",
            "ozone": "Parameter",
            "aerosol": "Parameter",

            # Data Formats
            "netcdf": "DataFormat",
            "hdf": "DataFormat",
            "jpeg": "DataFormat",
            "geotiff": "DataFormat",

            # Application Areas
            "cyclone forecasting": "ApplicationArea",
            "weather forecasting": "ApplicationArea",
            "climate study": "ApplicationArea",
            "agricultural monitoring": "ApplicationArea",
            "oceanography": "ApplicationArea",
            "atmospheric research": "ApplicationArea",

            # Services / General queries
            "data download": "Service",
            "visualization tool": "Service",
            "what data": "Query_DataProducts",
            "data on": "Query_DataProducts",
            "information about": "Query_Details",
            "details of": "Query_Details",
            "what is": "Query_Details_Object",
            "how to download": "Query_Download",
            "format of": "Query_Format",
            "time resolution": "Query_TimeResolution",
            "spatial resolution": "Query_SpatialResolution",
            "applications of": "Query_Applications",
            "what services": "Query_Services",
            
            # --- NEW LLM-RELATED KEYWORDS ---
            "summarize": "Query_Summarize",
            "summarize this": "Query_Summarize",
            "make it concise": "Query_Summarize",
            "can you summarize": "Query_Summarize",
            "use cases": "Query_UseCases",
            "application ideas": "Query_UseCases",
            "how can I use this": "Query_UseCases"
        }


    def process_query(self, text):
        doc = self.nlp(text.lower()) # Process the text with spaCy

        entities = []
        intents = []
        keywords = []

        # Default spaCy NER
        for ent in doc.ents:
            if ent.label_ in ["ORG", "PRODUCT", "LOC", "GPE", "NORP", "DATE"]: # Added DATE for potential time-based queries
                entities.append({"text": ent.text, "label": ent.label_, "type": "NER"})

        # Keyword-based entity and intent detection for MOSDAC
        for keyword, type_label in self.mosdac_keywords.items():
            if keyword in text.lower():
                if type_label.startswith("Query_"):
                    intents.append(type_label)
                else:
                    if type_label in self.known_entity_labels:
                        entities.append({"text": keyword, "label": type_label, "type": "Keyword"})
                    else:
                         keywords.append(keyword)
                
        # Identify potential relationships based on keywords
        found_relationships = []
        for rel_type in self.known_relationship_types:
            if rel_type.lower().replace('_', ' ') in text.lower():
                found_relationships.append(rel_type)

        # Simple intent logic based on keywords and entities
        main_intent = "general_query"
        if "Query_Download" in intents:
            main_intent = "get_download_info"
        elif "Query_Format" in intents:
            main_intent = "get_data_format"
        elif "Query_TimeResolution" in intents:
            main_intent = "get_time_resolution"
        elif "Query_SpatialResolution" in intents:
            main_intent = "get_spatial_resolution"
        elif "Query_Applications" in intents:
            main_intent = "get_applications"
        elif "Query_Services" in intents:
            main_intent = "get_services"
        elif "Query_DataProducts" in intents:
            main_intent = "list_data_products"
        elif "Query_Summarize" in intents: # NEW LLM INTENT
            main_intent = "summarize_info"
        elif "Query_UseCases" in intents: # NEW LLM INTENT
            main_intent = "generate_use_cases"
        elif "Query_Details" in intents or "Query_Details_Object" in intents:
            main_intent = "get_details"
        
        # If no specific query intent, but a MOSDAC-relevant entity is mentioned, assume general details
        if main_intent == "general_query":
            for ent_info in entities:
                if ent_info['label'] in KG_SCHEMA['nodes'] or ent_info['type'] in KG_SCHEMA['nodes']:
                    main_intent = "get_details"
                    break


        # Refine entities to pick the most relevant based on context
        unique_entities = {}
        for ent in entities:
            if ent['label'] in self.known_entity_labels:
                unique_entities[ent['label']] = ent['text']
            elif ent['type'] == 'NER' and ent['text'] not in unique_entities.values():
                 is_specific_overlap = False
                 for existing_label, existing_text in unique_entities.items():
                     if existing_text in ent['text'] and existing_label in self.known_entity_labels:
                         is_specific_overlap = True
                         break
                 if not is_specific_overlap:
                     unique_entities[ent['label']] = ent['text'] # Use spaCy's label or type

        return {
            "original_query": text,
            "main_intent": main_intent,
            "entities": unique_entities, # Stored as {label: text}
            "raw_entities": entities, # For debugging/more detailed handling if needed
            "keywords": keywords,
            "found_relationships": found_relationships
        }

# Example usage (for testing)
if __name__ == '__main__':
    nlu_processor = NLUProcessor()

    queries = [
        "What data products does MOSDAC provide?",
        "Tell me about sea surface temperature data.",
        "How can I download wind speed data?",
        "What is the format of Kalpana-1 data?",
        "What satellites observe rainfall?",
        "Give me details on INSAT-3D.",
        "What are the applications of satellite data?",
        "Is there a visualization tool available?",
        "summarize that", # NEW
        "generate use cases for rainfall data", # NEW
        "applications of INSAT-3D data" # NEW
    ]

    for query in queries:
        analysis = nlu_processor.process_query(query)
        print(f"\nQuery: {query}")
        print(f"  Intent: {analysis['main_intent']}")
        print(f"  Entities: {analysis['entities']}")
        print(f"  Relationships: {analysis['found_relationships']}")
