# kg_manager.py

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable # Corrected import path
import logging
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class KnowledgeGraphManager:
    def __init__(self, uri, username, password):
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None
        self._connect()

    def _connect(self):
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            self.driver.verify_connectivity()
            logging.info("Connected to Neo4j database successfully.")
        except ServiceUnavailable as e:
            logging.error(f"Failed to connect to Neo4j database at {self.uri}: {e}. Ensure Neo4j is running and accessible, and credentials are correct.")
            self.driver = None # Ensure driver is None if connection fails
        except Exception as e:
            logging.error(f"An unexpected error occurred while connecting to Neo4j: {e}")
            self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()
            logging.info("Neo4j database connection closed.")

    def _execute_query(self, query, parameters=None):
        """Internal helper to execute read/write queries."""
        if not self.driver:
            logging.warning("Neo4j driver is not active. Attempting to reconnect...")
            self._connect() # Attempt to reconnect if driver is not active
            if not self.driver:
                logging.error("No active Neo4j driver available to execute query after reconnection attempt.")
                return [] # Return empty list if connection is still not active

        records = []
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters)
                for record in result:
                    records.append(record)
            return records
        except Exception as e:
            logging.error(f"Error executing Neo4j query: {e}\nQuery: {query}\nParams: {parameters}")
            return []

    def add_entity(self, label, properties):
        """Adds a node (entity) to the graph."""
        props_str = ", ".join([f"{k}: ${k}" for k in properties.keys()])
        query = f"MERGE (n:{label} {{{props_str}}}) RETURN n"
        result = self._execute_query(query, properties)
        if result:
            logging.info(f"Added/Merged {label} node: {properties.get('name', properties)}")
        return result

    def add_relationship(self, from_label, from_props, to_label, to_props, rel_type, rel_properties=None):
        """Adds a relationship between two nodes."""
        rel_properties = rel_properties if rel_properties is not None else {}
        from_match = " AND ".join([f"from.{k} = ${k}_from" for k in from_props.keys()])
        to_match = " AND ".join([f"to.{k} = ${k}_to" for k in to_props.keys()])
        rel_props_str = ", ".join([f"{k}: ${k}" for k in rel_properties.keys()])

        query = (
            f"MATCH (from:{from_label} {{{from_match}}}), (to:{to_label} {{{to_match}}}) "
            f"MERGE (from)-[r:{rel_type} {{{rel_props_str}}}]->(to) RETURN r"
        )
        params = {**{f"{k}_from": v for k, v in from_props.items()},
                  **{f"{k}_to": v for k, v in to_props.items()},
                  **rel_properties}

        result = self._execute_query(query, params)
        if result:
            logging.info(f"Added/Merged relationship: ({from_label})-[:{rel_type}]->({to_label})")
        return result

    def get_entity_details(self, entity_name, entity_label=None):
        """
        Retrieves details about an entity.
        Can specify label for more precision, or search all if None.
        """
        match_clause = f"(n:{{label}})" if entity_label else "(n)"
        query = f"""
        MATCH {match_clause}
        WHERE toLower(n.name) CONTAINS toLower($entity_name)
        OPTIONAL MATCH (n)-[r]-(m)
        RETURN n, COLLECT(DISTINCT {{type: type(r), target_name: m.name, target_label: LABELS(m)[0], relationship_props: properties(r)}}) AS relationships
        LIMIT 1
        """
        params = {"entity_name": entity_name}
        if entity_label:
            params["label"] = entity_label

        records = self._execute_query(query, params)
        if records:
            record = records[0]
            node_data = dict(record["n"])
            relationships_data = record["relationships"]
            return {"node": node_data, "relationships": relationships_data}
        return None

    def get_related_entities(self, entity_name, entity_label, relationship_type=None, target_label=None):
        """
        Retrieves entities related to a given entity via a specific relationship.
        """
        query = f"MATCH (e:{entity_label})"

        if relationship_type:
            if target_label:
                query += f"-[r_type:{relationship_type}]->(r:{target_label})"
            else:
                query += f"-[r_type:{relationship_type}]->(r)"
        else: # If no specific relationship type, find any outgoing relationship
             query += f"-[r_type]->(r)"


        query += f" WHERE toLower(e.name) CONTAINS toLower($entity_name) " \
                 f"RETURN r.name AS related_name, LABELS(r)[0] AS related_label, type(r_type) AS relationship_type"

        params = {"entity_name": entity_name}
        if target_label:
            pass

        records = self._execute_query(query, params)
        return [{"name": rec["related_name"], "label": rec["related_label"], "type": rec["relationship_type"]} for rec in records]


# Example usage (for testing, not part of the main Flask app flow)
if __name__ == '__main__':
    kg_manager = KnowledgeGraphManager(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)

    # --- Clear existing data for fresh start (USE WITH CAUTION IN REAL PROJECTS!) ---
    # It's good to run this once to ensure your graph is clean before re-populating
    # UNCOMMENT THIS LINE ONLY IF YOU WANT TO CLEAR YOUR DATABASE
    # kg_manager._execute_query("MATCH (n) DETACH DELETE n")
    # print("Cleared existing graph data.")

    # --- Add some dummy data for testing ---
    # Adding a CREATE CONSTRAINT for uniqueness on DataProduct name (good practice)
    # Corrected syntax for Neo4j 4.x/5.x: "FOR" instead of "ON", "REQUIRE" instead of "ASSERT"
    kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (dp:DataProduct) REQUIRE dp.name IS UNIQUE")
    kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Satellite) REQUIRE s.name IS UNIQUE")
    kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (sn:Sensor) REQUIRE sn.name IS UNIQUE")
    kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Parameter) REQUIRE p.name IS UNIQUE")
    kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (df:DataFormat) REQUIRE df.name IS UNIQUE")
    kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (aa:ApplicationArea) REQUIRE aa.name IS UNIQUE")
    kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (svc:Service) REQUIRE svc.name IS UNIQUE")
    kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (tr:TimeResolution) REQUIRE tr.value IS UNIQUE")
    kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (sr:SpatialResolution) REQUIRE sr.value IS UNIQUE")
    kg_manager._execute_query("CREATE CONSTRAINT IF NOT EXISTS FOR (inst:Institution) REQUIRE inst.name IS UNIQUE")
    logging.info("Neo4j unique constraints ensured.")


    # --- Add some dummy MOSDAC data for testing ---
    # You will replace this with actual scraped data later
    kg_manager.add_entity("DataProduct", {"name": "Sea Surface Temperature", "description": "Global daily sea surface temperature anomaly data.", "coverage": "Global", "update_frequency": "Daily", "link": "https://mosdac.gov.in/data/sst"})
    kg_manager.add_entity("Satellite", {"name": "INSAT-3D", "mission_type": "Meteorological", "status": "Operational", "launch_date": "2013-07-26"})
    kg_manager.add_entity("Sensor", {"name": "Imager", "band": "Visible, IR", "wavelength_range": "0.5-12.0 µm"})
    kg_manager.add_entity("Parameter", {"name": "Temperature", "unit": "Celsius"})
    kg_manager.add_entity("DataFormat", {"name": "NetCDF", "description": "Network Common Data Form"})
    kg_manager.add_entity("ApplicationArea", {"name": "Cyclone Forecasting"})
    kg_manager.add_entity("ApplicationArea", {"name": "Climate Study"})
    kg_manager.add_entity("TimeResolution", {"value": "Daily"})
    kg_manager.add_entity("SpatialResolution", {"value": "4km"})
    kg_manager.add_entity("Institution", {"name": "ISRO", "type": "Space Agency"})
    kg_manager.add_entity("Service", {"name": "Data Download Portal", "description": "Portal for accessing various satellite data products", "access_url": "https://mosdac.gov.in/data-access"})

    # Relationships for Sea Surface Temperature
    kg_manager.add_relationship(
        "DataProduct", {"name": "Sea Surface Temperature"},
        "Parameter", {"name": "Temperature"},
        "PROVIDES"
    )
    kg_manager.add_relationship(
        "DataProduct", {"name": "Sea Surface Temperature"},
        "Satellite", {"name": "INSAT-3D"},
        "FROM_SATELLITE"
    )
    kg_manager.add_relationship(
        "Satellite", {"name": "INSAT-3D"},
        "Sensor", {"name": "Imager"},
        "USES_SENSOR"
    )
    kg_manager.add_relationship(
        "DataProduct", {"name": "Sea Surface Temperature"},
        "DataFormat", {"name": "NetCDF"},
        "AVAILABLE_IN_FORMAT"
    )
    kg_manager.add_relationship(
        "DataProduct", {"name": "Sea Surface Temperature"},
        "ApplicationArea", {"name": "Climate Study"},
        "APPLICABLE_FOR"
    )
    kg_manager.add_relationship(
        "DataProduct", {"name": "Sea Surface Temperature"},
        "Institution", {"name": "ISRO"},
        "PRODUCED_BY"
    )
    kg_manager.add_relationship(
        "DataProduct", {"name": "Sea Surface Temperature"},
        "TimeResolution", {"value": "Daily"},
        "HAS_TIME_RESOLUTION"
    )
    kg_manager.add_relationship(
        "DataProduct", {"name": "Sea Surface Temperature"},
        "SpatialResolution", {"value": "4km"},
        "HAS_SPATIAL_RESOLUTION"
    )

    # Add another product for testing
    kg_manager.add_entity("DataProduct", {"name": "Rainfall Data", "description": "Gridded rainfall data derived from INSAT satellites.", "coverage": "India", "update_frequency": "Hourly", "link": "https://mosdac.gov.in/data/rainfall"})
    kg_manager.add_entity("Satellite", {"name": "INSAT-3DR", "mission_type": "Meteorological", "status": "Operational", "launch_date": "2016-09-08"})
    kg_manager.add_relationship(
        "DataProduct", {"name": "Rainfall Data"},
        "Parameter", {"name": "Rainfall"},
        "PROVIDES"
    )
    kg_manager.add_relationship(
        "DataProduct", {"name": "Rainfall Data"},
        "Satellite", {"name": "INSAT-3DR"},
        "FROM_SATELLITE"
    )
    kg_manager.add_relationship(
        "DataProduct", {"name": "Rainfall Data"},
        "ApplicationArea", {"name": "Agricultural Monitoring"},
        "APPLICABLE_FOR"
    )
    kg_manager.add_relationship(
        "DataProduct", {"name": "Rainfall Data"},
        "TimeResolution", {"value": "Hourly"},
        "HAS_TIME_RESOLUTION"
    )
    kg_manager.add_relationship(
        "DataProduct", {"name": "Rainfall Data"},
        "DataFormat", {"name": "NetCDF"},
        "AVAILABLE_IN_FORMAT"
    )

    # Example of a Service
    kg_manager.add_entity("Institution", {"name": "MOSDAC", "type": "Data Centre"})
    kg_manager.add_relationship(
        "Institution", {"name": "MOSDAC"},
        "Service", {"name": "Data Download Portal"},
        "OFFERS_SERVICE"
    )
    kg_manager.add_relationship(
        "Institution", {"name": "ISRO"},
        "Service", {"name": "Data Download Portal"}, # ISRO as parent of MOSDAC
        "OFFERS_SERVICE"
    )


    print("\n--- Testing queries ---")
    # Test getting entity details
    sst_details = kg_manager.get_entity_details("Sea Surface Temperature", "DataProduct")
    if sst_details:
        print(f"Details for Sea Surface Temperature: {sst_details['node']}")
        for rel in sst_details['relationships']:
            print(f"  - {rel['type']} -> {rel['target_name']} ({rel['target_label']})")
    else:
        print("Sea Surface Temperature not found.")

    # Test getting related entities (Satellites providing a parameter)
    satellites_for_temperature = kg_manager.get_related_entities("Temperature", "Parameter", "OBSERVED_BY", "Satellite")
    if satellites_for_temperature:
        print(f"\nSatellites observing Temperature: {[s['name'] for s in satellites_for_temperature]}")
    
    # Test getting applications of Rainfall Data
    rainfall_applications = kg_manager.get_related_entities("Rainfall Data", "DataProduct", "APPLICABLE_FOR", "ApplicationArea")
    if rainfall_applications:
        print(f"\nApplications of Rainfall Data: {[a['name'] for a in rainfall_applications]}")

    # Test getting services offered by MOSDAC
    mosdac_services = kg_manager.get_related_entities("MOSDAC", "Institution", "OFFERS_SERVICE", "Service")
    if mosdac_services:
        print(f"\nServices offered by MOSDAC: {[s['name'] for s in mosdac_services]}")


    kg_manager.close()
