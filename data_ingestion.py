# data_ingestion.py

import requests
from bs4 import BeautifulSoup
from kg_manager import KnowledgeGraphManager
from config import (
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD,
    MOSDAC_BASE_URL, MOSDAC_MISSIONS_MENU_PATH, MOSDAC_OPEN_DATA_MENU_PATH,
    KG_SCHEMA
)
import logging
from urllib.parse import urljoin

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MOSDACDataIngester:
    def __init__(self):
        self.kg_manager = KnowledgeGraphManager(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
        self._create_constraints()

    def _create_constraints(self):
        """Ensures unique constraints exist in Neo4j for key node properties using Neo4j 4.x/5.x syntax."""
        try:
            # Corrected syntax for Neo4j 4.x/5.x: "FOR" instead of "ON", "REQUIRE" instead of "ASSERT"
            self.kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (dp:DataProduct) REQUIRE dp.name IS UNIQUE")
            self.kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Satellite) REQUIRE s.name IS UNIQUE")
            self.kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (sn:Sensor) REQUIRE sn.name IS UNIQUE")
            self.kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Parameter) REQUIRE p.name IS UNIQUE")
            self.kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (df:DataFormat) REQUIRE df.name IS UNIQUE")
            self.kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (aa:ApplicationArea) REQUIRE aa.name IS UNIQUE")
            self.kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (svc:Service) REQUIRE svc.name IS UNIQUE")
            self.kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (tr:TimeResolution) REQUIRE tr.value IS UNIQUE")
            self.kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (sr:SpatialResolution) REQUIRE sr.value IS UNIQUE")
            self.kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (inst:Institution) REQUIRE inst.name IS UNIQUE")
            logging.info("Neo4j unique constraints ensured.")
        except Exception as e:
            logging.error(f"Failed to create Neo4j constraints. This might cause issues with data ingestion: {e}")

    def scrape_and_ingest_menus(self):
        """
        Scrapes satellite and data product information from the main navigation menus
        of the MOSDAC website.
        """
        logging.info(f"Starting MOSDAC menu scraping from: {MOSDAC_BASE_URL}")
        try:
            response = requests.get(MOSDAC_BASE_URL, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            total_ingested = 0

            # --- Scrape Missions (Satellites) ---
            logging.info("Scraping Missions (Satellites) from menu...")
            missions_menu = soup.find('li', id='menu-1427-1', class_='menuparent') # The 'Missions' <li>
            if missions_menu:
                satellite_links = missions_menu.find('ul').find_all('li', class_='sf-depth-2')
                for li in satellite_links:
                    a_tag = li.find('a', href=True)
                    if a_tag:
                        name = a_tag.get_text(strip=True)
                        link = urljoin(MOSDAC_BASE_URL, a_tag['href'])
                        
                        self.kg_manager.add_entity("Satellite", {"name": name, "link": link, "mission_type": "Meteorological"})
                        total_ingested += 1
                        logging.info(f"Ingested Satellite: {name} ({link})")
            else:
                logging.warning("Missions menu not found. Check HTML selectors for 'menu-1427-1'.")


            # --- Scrape Data Access -> Open Data (Data Products) ---
            logging.info("Scraping Data Products from 'Data Access -> Open Data' menu...")
            data_access_menu = soup.find('li', id='menu-1426-1', class_='menuparent') # The 'Data Access' <li>
            if data_access_menu:
                open_data_menu = data_access_menu.find('li', id='menu-1474-1', class_='menuparent') # The 'Open Data' <li>
                if open_data_menu:
                    # Find all sf-depth-4 links under Open Data
                    data_product_links = open_data_menu.find_all('li', class_='sf-depth-4')
                    for li in data_product_links:
                        a_tag = li.find('a', href=True)
                        if a_tag:
                            name = a_tag.get_text(strip=True)
                            link = urljoin(MOSDAC_BASE_URL, a_tag['href'])
                            
                            # Add a placeholder description for now, as full descriptions are on linked pages
                            description = f"Data product related to {name} available on MOSDAC. Visit {link} for more details."
                            
                            self.kg_manager.add_entity("DataProduct", {"name": name, "description": description, "link": link})
                            total_ingested += 1
                            logging.info(f"Ingested DataProduct: {name} ({link})")
                else:
                    logging.warning("Open Data submenu not found. Check HTML selectors for 'menu-1474-1'.")
            else:
                logging.warning("Data Access menu not found. Check HTML selectors for 'menu-1426-1'.")

            if total_ingested == 0:
                logging.error(f"No data was ingested from the MOSDAC menus. Check HTML selectors in data_ingestion.py.")
            else:
                logging.info(f"MOSDAC menu scraping completed. Ingested {total_ingested} entities.")

        except requests.exceptions.RequestException as e:
            logging.error(f"Error during web scraping request for {MOSDAC_BASE_URL}: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred during parsing or ingestion from menus: {e}", exc_info=True)
        finally:
            self.kg_manager.close()

    def _ingest_data_product(self, name, description, link, satellites=None, parameters=None, data_formats=None):
        """
        Helper function. This is less critical for menu scraping, but kept for consistency
        if you later expand to scrape individual product pages.
        """
        logging.info(f"Ingesting generic data product via helper: {name}")

        data_product_props = {"name": name, "description": description, "link": link}
        self.kg_manager.add_entity("DataProduct", data_product_props)

        if satellites:
            for sat_name in satellites:
                self.kg_manager.add_entity("Satellite", {"name": sat_name})
                self.kg_manager.add_relationship(
                    "DataProduct", {"name": name},
                    "Satellite", {"name": sat_name},
                    "FROM_SATELLITE"
                )
        
        if parameters:
            for param_name in parameters:
                self.kg_manager.add_entity("Parameter", {"name": param_name})
                self.kg_manager.add_relationship(
                    "DataProduct", {"name": name},
                    "Parameter", {"name": param_name},
                    "PROVIDES"
                )

        if data_formats:
            for fmt_name in data_formats:
                self.kg_manager.add_entity("DataFormat", {"name": fmt_name})
                self.kg_manager.add_relationship(
                    "DataProduct", {"name": name},
                    "DataFormat", {"name": fmt_name},
                    "AVAILABLE_IN_FORMAT"
                )
        
        self.kg_manager.add_entity("Institution", {"name": "ISRO", "type": "Space Agency"})
        self.kg_manager.add_relationship(
            "DataProduct", {"name": name},
            "Institution", {"name": "ISRO"},
            "PRODUCED_BY"
        )


# Example usage
if __name__ == '__main__':
    ingester = MOSDACDataIngester()
    
    # --- IMPORTANT ---
    # 1. Clear existing data from Neo4j if you want a fresh graph.
    #    UNCOMMENT THE FOLLOWING LINES ONLY IF YOU WANT TO CLEAR YOUR ENTIRE DB!
    # kg_manager_temp = KnowledgeGraphManager(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
    # kg_manager_temp._execute_query("MATCH (n) DETACH DELETE n")
    # kg_manager_temp.close()
    # logging.info("Cleared all data from Neo4j before scraping.")
    
    # Call the new menu scraping function
    ingester.scrape_and_ingest_menus()
    
    logging.info("MOSDAC data ingestion script finished.")
