"""
scripts/fetch_domain_data.py — Fetch sample patents & research papers across AI domains

Domains:
- Artificial Intelligence, Machine Learning, Deep Learning, Large Language Models (LLMs),
  Agentic AI, Retrieval-Augmented Generation (RAG), Computer Vision, Natural Language Processing,
  Generative AI, AI Infrastructure, Vector Databases, Edge AI, Robotics, Autonomous Systems, Emerging Technologies

Sources:
- PatentsView (USPTO)
- Semantic Scholar
- arXiv
- OpenAlex
- CrossRef
"""

import json
import time
import urllib.parse
from pathlib import Path
import httpx

DOMAINS = [
    "Artificial Intelligence",
    "Machine Learning",
    "Deep Learning",
    "Large Language Models",
    "Agentic AI",
    "Retrieval-Augmented Generation",
    "Computer Vision",
    "Natural Language Processing",
    "Generative AI",
    "AI Infrastructure",
    "Vector Databases",
    "Edge AI",
    "Robotics",
    "Autonomous Systems",
    "Emerging Technologies"
]

OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)


def fetch_arxiv(domain: str, limit: int = 10):
    url = f"http://export.arxiv.org/api/query?search_query=all:{urllib.parse.quote(domain)}&max_results={limit}"
    try:
        r = httpx.get(url, timeout=10.0)
        if r.status_code == 200:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(r.text)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            entries = []
            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns).text.strip().replace('\n', ' ') if entry.find('atom:title', ns) is not None else ""
                summary = entry.find('atom:summary', ns).text.strip().replace('\n', ' ') if entry.find('atom:summary', ns) is not None else ""
                paper_id = entry.find('atom:id', ns).text if entry.find('atom:id', ns) is not None else ""
                entries.append({
                    "id": paper_id,
                    "title": title,
                    "abstract": summary,
                    "source": "arXiv",
                    "domain": domain
                })
            return entries
    except Exception as e:
        print(f"  [arXiv Error] {domain}: {e}")
    return []


def fetch_semantic_scholar(domain: str, limit: int = 10):
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={urllib.parse.quote(domain)}&limit={limit}&fields=title,abstract,url,year,authors"
    try:
        r = httpx.get(url, timeout=10.0)
        if r.status_code == 200:
            data = r.json()
            papers = []
            for item in data.get("data", []):
                papers.append({
                    "id": item.get("paperId"),
                    "title": item.get("title"),
                    "abstract": item.get("abstract") or "",
                    "url": item.get("url"),
                    "year": item.get("year"),
                    "authors": [a.get("name") for a in item.get("authors", [])],
                    "source": "Semantic Scholar",
                    "domain": domain
                })
            return papers
    except Exception as e:
        print(f"  [Semantic Scholar Error] {domain}: {e}")
    return []


def fetch_openalex(domain: str, limit: int = 10):
    url = f"https://api.openalex.org/works?search={urllib.parse.quote(domain)}&per_page={limit}"
    try:
        r = httpx.get(url, timeout=10.0)
        if r.status_code == 200:
            data = r.json()
            works = []
            for item in data.get("results", []):
                title = item.get("title") or ""
                # Reconstruction of abstract from abstract_inverted_index if present
                abstract = ""
                inv_idx = item.get("abstract_inverted_index")
                if inv_idx:
                    words = {}
                    for word, pos_list in inv_idx.items():
                        for pos in pos_list:
                            words[pos] = word
                    abstract = " ".join([words[i] for i in sorted(words.keys())])
                
                works.append({
                    "id": item.get("id"),
                    "title": title,
                    "abstract": abstract,
                    "doi": item.get("doi"),
                    "year": item.get("publication_year"),
                    "type": item.get("type"),
                    "source": "OpenAlex",
                    "domain": domain
                })
            return works
    except Exception as e:
        print(f"  [OpenAlex Error] {domain}: {e}")
    return []


def fetch_crossref(domain: str, limit: int = 10):
    url = f"https://api.crossref.org/works?query={urllib.parse.quote(domain)}&rows={limit}"
    try:
        headers = {"User-Agent": "PatentPilotAI/1.0 (mailto:patentpilot@cdac.in)"}
        r = httpx.get(url, headers=headers, timeout=10.0)
        if r.status_code == 200:
            data = r.json()
            items = []
            for item in data.get("message", {}).get("items", []):
                titles = item.get("title", [])
                title = titles[0] if titles else ""
                items.append({
                    "id": item.get("DOI"),
                    "title": title,
                    "url": item.get("URL"),
                    "publisher": item.get("publisher"),
                    "type": item.get("type"),
                    "source": "CrossRef",
                    "domain": domain
                })
            return items
    except Exception as e:
        print(f"  [CrossRef Error] {domain}: {e}")
    return []


def fetch_patentsview(domain: str, limit: int = 10):
    # PatentsView query API
    url = "https://api.patentsview.org/patents/query"
    query = {"_or": [{"_text_any": {"patent_title": domain}}, {"_text_any": {"patent_abstract": domain}}]}
    fields = ["patent_id", "patent_title", "patent_abstract", "patent_date"]
    options = {"per_page": limit}
    try:
        r = httpx.post(url, json={"q": query, "f": fields, "o": options}, timeout=10.0)
        if r.status_code == 200:
            data = r.json()
            patents = []
            for item in data.get("patents", []):
                patents.append({
                    "id": item.get("patent_id"),
                    "title": item.get("patent_title"),
                    "abstract": item.get("patent_abstract"),
                    "date": item.get("patent_date"),
                    "source": "USPTO PatentsView",
                    "domain": domain
                })
            return patents
    except Exception as e:
        print(f"  [PatentsView Error] {domain}: {e}")
    return []


def main():
    print("=== Fetching Domain Data for PatentPilot AI ===")
    results = {}
    
    for domain in DOMAINS:
        print(f"\nFetching domain: {domain}")
        results[domain] = {
            "arXiv": fetch_arxiv(domain, 10),
            "SemanticScholar": fetch_semantic_scholar(domain, 10),
            "OpenAlex": fetch_openalex(domain, 10),
            "CrossRef": fetch_crossref(domain, 10),
            "PatentsView": fetch_patentsview(domain, 10)
        }
        time.sleep(0.5)

    out_file = OUTPUT_DIR / "domain_sample_data.json"
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[DONE] Saved domain samples to {out_file}")


if __name__ == "__main__":
    main()
