"""
agents/knowledge_graph.py — Knowledge Graph Agent Node for PatentPilot AI

Stage 7 of the 11-stage pipeline:
1. Reads technical_entities and patent_results from state.
2. Executes Cypher MERGE queries in Neo4j to create nodes & relationships:
   - (Patent)-[:HAS_INVENTOR]->(Inventor)
   - (Patent)-[:USES_ALGORITHM]->(Algorithm)
   - (Patent)-[:CLASSIFIED_AS]->(IPCCode)
3. Returns knowledge_graph_id in PatentPilotState update.
"""

import uuid
import logging
from typing import Any, Dict, List
from state import PatentPilotState
from retrieval.neo4j_client import execute_cypher, get_neo4j_driver

logger = logging.getLogger(__name__)


def knowledge_graph_agent_node(state: PatentPilotState) -> Dict[str, Any]:
    """
    Knowledge Graph agent node function.
    """
    patent_results = state.get("patent_results") or []
    technical_entities = state.get("technical_entities") or []
    graph_run_id = f"kg_run_{uuid.uuid4().hex[:8]}"

    driver = get_neo4j_driver()
    if not driver:
        logger.warning("Neo4j not connected — returning mock knowledge_graph_id.")
        return {"knowledge_graph_id": graph_run_id}

    # 1. Process patent_results
    for patent in patent_results:
        patent_id = str(patent.get("patent_id") or "").strip()
        title = str(patent.get("title") or "").strip()
        if not patent_id:
            continue

        # MERGE Patent node
        execute_cypher(
            "MERGE (p:Patent {patent_id: $patent_id}) "
            "ON CREATE SET p.title = $title "
            "ON MATCH SET p.title = $title",
            {"patent_id": patent_id, "title": title}
        )

        # MERGE Inventors & HAS_INVENTOR relationships
        inventors = patent.get("inventors") or []
        for inv in inventors:
            inv_name = str(inv).strip()
            if inv_name:
                execute_cypher(
                    "MERGE (p:Patent {patent_id: $patent_id}) "
                    "MERGE (i:Inventor {name: $inv_name}) "
                    "MERGE (p)-[:HAS_INVENTOR]->(i)",
                    {"patent_id": patent_id, "inv_name": inv_name}
                )

        # MERGE IPC Codes & CLASSIFIED_AS relationships
        ipc_codes = patent.get("ipc_codes") or []
        for ipc in ipc_codes:
            code = str(ipc).strip()
            if code:
                execute_cypher(
                    "MERGE (p:Patent {patent_id: $patent_id}) "
                    "MERGE (c:IPCCode {code: $code}) "
                    "MERGE (p)-[:CLASSIFIED_AS]->(c)",
                    {"patent_id": patent_id, "code": code}
                )

    # 2. Process technical_entities
    for entity_record in technical_entities:
        source_id = str(entity_record.get("source_id") or "").strip()
        if not source_id:
            continue

        # MERGE Patent/Source node
        execute_cypher(
            "MERGE (p:Patent {patent_id: $source_id})",
            {"source_id": source_id}
        )

        # MERGE Algorithms & USES_ALGORITHM relationships
        algorithms = entity_record.get("algorithms") or []
        for algo in algorithms:
            algo_name = str(algo).strip()
            if algo_name:
                execute_cypher(
                    "MERGE (p:Patent {patent_id: $source_id}) "
                    "MERGE (a:Algorithm {name: $algo_name}) "
                    "MERGE (p)-[:USES_ALGORITHM]->(a)",
                    {"source_id": source_id, "algo_name": algo_name}
                )

    logger.info(f"Knowledge graph nodes & relationships created in Neo4j (Run ID: {graph_run_id})")
    return {"knowledge_graph_id": graph_run_id}
