# bot_logic.py

import requests # Import for making HTTP requests to Gemini API
from nlu_processor import NLUProcessor
from kg_manager import KnowledgeGraphManager
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, KG_SCHEMA
import logging
import json # For handling JSON payload for Gemini API

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ISROBot:
    def __init__(self):
        self.nlu_processor = NLUProcessor()
        self.kg_manager = KnowledgeGraphManager(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
        self.last_detailed_response_content = None # Stores content for summarization
        self.last_detailed_entity_name = None # Stores entity name for use case generation

    def _call_gemini_llm(self, prompt, api_key=""):
        """
        Calls the Gemini 2.0 Flash LLM to generate text.
        The API key is left empty; Canvas will inject it at runtime.
        """
        logging.info(f"Calling Gemini LLM with prompt: {prompt[:100]}...") # Log first 100 chars
        chat_history = []
        chat_history.push({ "role": "user", "parts": [{ "text": prompt }] })
        
        # Payload for the Gemini API call
        payload = { "contents": chat_history }
        
        # Gemini API endpoint (gemini-2.0-flash is the default)
        # The API key is passed as a query parameter
        gemini_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

        try:
            response = requests.post(
                gemini_api_url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(payload), # Convert Python dict to JSON string
                timeout=30 # Add a timeout for the API call
            )
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
            result = response.json()

            if result.get("candidates") and result["candidates"][0].get("content") and result["candidates"][0]["content"].get("parts"):
                generated_text = result["candidates"][0]["content"]["parts"][0]["text"]
                logging.info("Gemini LLM call successful.")
                return generated_text
            else:
                logging.error(f"Gemini LLM response format unexpected: {result}")
                return "I couldn't generate a response from the AI at this moment."
        except requests.exceptions.RequestException as e:
            logging.error(f"Error calling Gemini LLM: {e}")
            return "I'm having trouble connecting to the generative AI right now. Please try again later."
        except Exception as e:
            logging.error(f"An unexpected error occurred during Gemini LLM call: {e}")
            return "An internal error occurred while processing your request."

    def generate_response(self, user_query):
        nlu_result = self.nlu_processor.process_query(user_query)
        logging.info(f"NLU Result: {nlu_result}")

        intent = nlu_result['main_intent']
        entities = nlu_result['entities']

        response_text = "I'm sorry, I couldn't find information on that. Could you please rephrase or ask about specific MOSDAC data products, satellites, or services?"

        # Helper to find a primary entity from recognized entities, prioritizing specific labels
        def find_primary_entity(entities_dict, preferred_labels):
            for label in preferred_labels:
                if label in entities_dict:
                    return entities_dict[label], label
            for label, name in entities_dict.items():
                if label in KG_SCHEMA['nodes']:
                    return name, label
            return None, None

        # --- Handle different intents and query the KG ---
        if intent == "get_details":
            primary_entity_name, primary_entity_label = find_primary_entity(
                entities, ["DataProduct", "Satellite", "Sensor", "Parameter", "ApplicationArea", "Service", "Institution"]
            )
                
            if primary_entity_name:
                details = self.kg_manager.get_entity_details(primary_entity_name, primary_entity_label)
                if details:
                    response_parts = []
                    node = details['node']
                    response_parts.append(f"Here's what I know about {node.get('name', primary_entity_name)}:")

                    description_content = node.get('description')
                    if description_content:
                        response_parts.append(f"- Description: {description_content}")
                        # Store detailed description for potential summarization
                        self.last_detailed_response_content = description_content
                        self.last_detailed_entity_name = node.get('name', primary_entity_name)
                    else:
                        self.last_detailed_response_content = None
                        self.last_detailed_entity_name = None

                    for prop, value in node.items():
                        if prop not in ["name", "description"]: # 'name' and 'description' handled
                            response_parts.append(f"- {prop.replace('_', ' ').title()}: {value}")

                    if details['relationships']:
                        response_parts.append("\nRelated Information:")
                        for rel in details['relationships']:
                            if rel['type'] == "FROM_SATELLITE":
                                response_parts.append(f"  - It is derived from the {rel['target_name']} satellite.")
                            elif rel['type'] == "PROVIDES":
                                response_parts.append(f"  - It provides data on {rel['target_name'].lower()}.")
                            elif rel['type'] == "AVAILABLE_IN_FORMAT":
                                response_parts.append(f"  - It is available in {rel['target_name']} format.")
                            elif rel['type'] == "APPLICABLE_FOR":
                                response_parts.append(f"  - It is applicable for {rel['target_name'].lower()}.")
                            elif rel['type'] == "USES_SENSOR":
                                response_parts.append(f"  - It uses the {rel['target_name']} sensor.")
                            elif rel['type'] == "PRODUCED_BY":
                                response_parts.append(f"  - It is produced by {rel['target_name']}.")
                            else:
                                response_parts.append(f"  - Related to {rel['target_name']} ({rel['target_label']}) via {rel['type'].replace('_', ' ').lower()}.")
                    response_text = "\n".join(response_parts)

                    # Suggest LLM features if a description was found
                    if self.last_detailed_response_content:
                        response_text += "\n\n✨ Would you like me to summarize this, or generate use case ideas for this data?"
                else:
                    response_text = f"I couldn't find detailed information about '{primary_entity_name}'. It might not be in my knowledge base yet."
                    self.last_detailed_response_content = None
                    self.last_detailed_entity_name = None
            else:
                response_text = "Please specify which MOSDAC data product, satellite, or service you'd like to know about."
                self.last_detailed_response_content = None
                self.last_detailed_entity_name = None

        elif intent == "list_data_products":
            products = self.kg_manager._execute_query("MATCH (p:DataProduct) RETURN p.name AS name, p.description AS description LIMIT 5")
            if products:
                response_text = "MOSDAC provides various data products, including:\n"
                for p in products:
                    response_text += f"- {p['name']}\n"
                response_text += "You can ask for more details about a specific product, e.g., 'Tell me about sea surface temperature data'."
            else:
                response_text = "I couldn't find a list of data products. The knowledge graph might be empty or the query needs refinement."
            self.last_detailed_response_content = None
            self.last_detailed_entity_name = None
        
        elif intent == "get_data_format":
            product_name, product_label = find_primary_entity(entities, ["DataProduct"])
            if product_name:
                formats = self.kg_manager.get_related_entities(product_name, product_label, "AVAILABLE_IN_FORMAT", "DataFormat")
                if formats:
                    format_names = [f['name'] for f in formats]
                    response_text = f"The data for {product_name} is typically available in the following formats: {', '.join(format_names)}."
                else:
                    response_text = f"I don't have information on the specific data format for {product_name}."
            else:
                response_text = "Please specify which data product's format you are interested in."
            self.last_detailed_response_content = None
            self.last_detailed_entity_name = None

        elif intent == "get_download_info":
            product_name, product_label = find_primary_entity(entities, ["DataProduct", "Parameter"])
            if product_name:
                details = self.kg_manager.get_entity_details(product_name, product_label)
                if details and 'link' in details['node']:
                    response_text = f"You can usually download data for {details['node']['name']} from this link: {details['node']['link']}. Please visit the MOSDAC website for specific download procedures."
                else:
                    response_text = f"I don't have direct download links for {product_name}. Please visit the MOSDAC website (mosdac.gov.in) and navigate to the data products section to find download options."
            else:
                response_text = "Please specify which data product you'd like download information for."
            self.last_detailed_response_content = None
            self.last_detailed_entity_name = None

        elif intent == "get_applications":
            product_name, product_label = find_primary_entity(entities, ["DataProduct", "Parameter", "Satellite"])
            if product_name:
                applications = self.kg_manager.get_related_entities(product_name, product_label, "APPLICABLE_FOR", "ApplicationArea")
                if applications:
                    app_names = [a['name'] for a in applications]
                    response_text = f"The data/satellite '{product_name}' is applicable for areas such as: {', '.join(app_names)}."
                else:
                    response_text = f"I don't have specific application information for {product_name} in my knowledge base."
            else:
                response_text = "Please tell me which data product or satellite you'd like to know applications for."
            self.last_detailed_response_content = None
            self.last_detailed_entity_name = None

        elif intent == "get_services":
            institution_name = entities.get("Institution", "MOSDAC") # Default to MOSDAC
            services = self.kg_manager.get_related_entities(institution_name, "Institution", "OFFERS_SERVICE", "Service")
            if services:
                service_names = [s['name'] for s in services]
                response_text = f"{institution_name} offers services like: {', '.join(service_names)}. You can often find visualization tools or data download portals."
            else:
                response_text = f"I couldn't find specific service information for {institution_name}."
            self.last_detailed_response_content = None
            self.last_detailed_entity_name = None

        # --- NEW LLM INTENT HANDLERS ---
        elif intent == "summarize_info":
            if self.last_detailed_response_content:
                prompt = f"Summarize the following information about {self.last_detailed_entity_name} concisely in a paragraph:\n\n{self.last_detailed_response_content}"
                llm_summary = self._call_gemini_llm(prompt)
                response_text = f"✨ Here's a summary of the previous information about {self.last_detailed_entity_name}:\n{llm_summary}"
            else:
                response_text = "I don't have a recent detailed piece of information to summarize. Please ask me about a specific data product or satellite first."
            self.last_detailed_response_content = None # Clear after summarization
            self.last_detailed_entity_name = None

        elif intent == "generate_use_cases":
            target_entity_name, target_entity_label = find_primary_entity(
                entities, ["DataProduct", "Satellite", "Parameter", "ApplicationArea"]
            )
            
            if target_entity_name:
                details = self.kg_manager.get_entity_details(target_entity_name, target_entity_label)
                if details and details['node'].get('description'):
                    context = details['node']['description']
                else:
                    context = f"data related to {target_entity_name}"

                prompt = f"Generate 3-5 creative and practical use case ideas for '{target_entity_name}' (which is {target_entity_label.lower()}), considering its nature as {context}. Focus on meteorological, oceanographic, or environmental applications. Provide them as a bulleted list."
                llm_use_cases = self._call_gemini_llm(prompt)
                response_text = f"✨ Here are some use case ideas for {target_entity_name}:\n{llm_use_cases}"
            else:
                response_text = "Please specify which data product, satellite, or parameter you'd like use case ideas for."
            self.last_detailed_response_content = None
            self.last_detailed_entity_name = None
        # --- END NEW LLM INTENT HANDLERS ---

        return response_text

    def close(self):
        self.kg_manager.close()

# Example usage (for testing)
if __name__ == '__main__':
    bot = ISROBot()
    
    print("--- MOSDAC Help Bot ---")
    print("Try asking: 'Tell me about sea surface temperature data'")
    print("Then: 'summarize that' or 'generate use cases for sea surface temperature data'")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Bot: Goodbye!")
            break
        
        bot_response = bot.generate_response(user_input)
        print(f"Bot: {bot_response}")

    bot.close()
