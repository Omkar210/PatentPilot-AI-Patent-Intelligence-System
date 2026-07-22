"""
retrieval/neo4j_client.py — Neo4j Knowledge Graph Connection & Driver

Establishes driver connection to Neo4j database using NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD.
"""

import os
import logging
from typing import Any, Dict, List, Optional
from neo4j import GraphDatabase, Driver
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "patentpilot123")

_neo4j_driver: Optional[Driver] = None


def get_neo4j_driver() -> Optional[Driver]:
    global _neo4j_driver
    if _neo4j_driver is None:
        try:
            _neo4j_driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
            # Verify connectivity
            _neo4j_driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {NEO4J_URI}")
        except Exception as e:
            logger.warning(f"Failed to connect to Neo4j at {NEO4J_URI}: {e}")
            _neo4j_driver = None
    return _neo4j_driver


def execute_cypher(query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Executes a Cypher query on Neo4j and returns list of record dictionaries."""
    driver = get_neo4j_driver()
    if not driver:
        logger.warning("Neo4j driver unavailable — skipping Cypher execution.")
        return []

    params = parameters or {}
    records_data = []

    try:
        with driver.session() as session:
            result = session.run(query, params)
            for record in result:
                records_data.append(record.data())
    except Exception as e:
        logger.error(f"Neo4j Cypher Execution Error: {e}")

    return records_data


def close_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver:
        _neo4j_driver.close()
        _neo4j_driver = None
