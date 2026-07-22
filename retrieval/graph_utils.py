"""
retrieval/graph_utils.py — NetworkX Graph Utility for Frontend Visualization

Pulls a 1-hop neighborhood subgraph for a given patent_id from Neo4j
and returns it as a networkx.Graph object.
"""

from typing import Any, Dict
import networkx as nx
from retrieval.neo4j_client import execute_cypher, get_neo4j_driver


def get_patent_subgraph(patent_id: str) -> nx.Graph:
    """
    Queries Neo4j for nodes & relationships connected to patent_id
    and builds a NetworkX Graph object.
    """
    G = nx.Graph()
    G.add_node(patent_id, type="Patent", label=f"Patent {patent_id}")

    driver = get_neo4j_driver()
    if not driver:
        return G

    cypher = """
    MATCH (p:Patent {patent_id: $patent_id})-[r]-(n)
    RETURN type(r) AS rel_type, labels(n)[0] AS target_type, 
           coalesce(n.name, n.code, n.patent_id) AS target_name
    """

    records = execute_cypher(cypher, {"patent_id": patent_id})

    for row in records:
        rel_type = row.get("rel_type")
        target_type = row.get("target_type")
        target_name = row.get("target_name")

        if target_name:
            target_node_id = f"{target_type}:{target_name}"
            G.add_node(target_node_id, type=target_type, label=target_name)
            G.add_edge(patent_id, target_node_id, relationship=rel_type)

    return G
