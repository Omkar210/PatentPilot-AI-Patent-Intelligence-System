import asyncio
import httpx
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from rich.console import Console

console = Console()

class ArxivClient:
    def __init__(self):
        self.base_url = "http://export.arxiv.org/api/query"
        
    async def fetch_ai_patents(self, limit: int = 50, domain_keyword: str = "artificial intelligence") -> List[Dict[str, Any]]:
        results = []
        page_size = 200
        
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                for start in range(0, limit, page_size):
                    batch_limit = min(page_size, limit - start)
                    console.print(f"[dim]ArXiv API: Fetching {batch_limit} results starting at {start} for '{domain_keyword}'...[/dim]")
                    
                    params = {
                        "search_query": f'all:"{domain_keyword}"',
                        "start": start,
                        "max_results": batch_limit,
                        "sortBy": "submittedDate",
                        "sortOrder": "descending"
                    }
                    
                    response = await client.get(self.base_url, params=params)
                    if response.status_code == 200:
                        root = ET.fromstring(response.text)
                        ns = '{http://www.w3.org/2005/Atom}'
                        entries = root.findall(f'{ns}entry')
                        
                        if not entries:
                            break # No more results
                            
                        for entry in entries:
                            id_element = entry.find(f'{ns}id')
                            arxiv_id = id_element.text.split('/')[-1] if id_element is not None else "Unknown"
                            
                            title_elem = entry.find(f'{ns}title')
                            title = title_elem.text.strip().replace('\n', ' ') if title_elem is not None else "Untitled arXiv Paper"
                            
                            summary_elem = entry.find(f'{ns}summary')
                            abstract = summary_elem.text.strip().replace('\n', ' ') if summary_elem is not None else "No abstract provided."
                            
                            authors = []
                            for author in entry.findall(f'{ns}author'):
                                name_elem = author.find(f'{ns}name')
                                if name_elem is not None:
                                    authors.append(name_elem.text.strip())
                            if not authors:
                                authors = ["Unknown Author"]
                                
                            published_elem = entry.find(f'{ns}published')
                            pub_date = published_elem.text[:10] if published_elem is not None else "2023-01-01"
                            
                            categories = []
                            for cat in entry.findall(f'{ns}category'):
                                term = cat.attrib.get('term')
                                if term:
                                    categories.append(term)
                                    
                            pdf_url = ""
                            for link in entry.findall(f'{ns}link'):
                                if link.attrib.get('title') == 'pdf' or link.attrib.get('type') == 'application/pdf':
                                    pdf_url = link.attrib.get('href')
                                    break
                                    
                            if not pdf_url:
                                pdf_url = f"http://arxiv.org/pdf/{arxiv_id}.pdf"
                                
                            if pdf_url.startswith("http://"):
                                pdf_url = pdf_url.replace("http://", "https://")
                                
                            results.append({
                                "patent_number": f"ARXIV-{arxiv_id}",
                                "title": title,
                                "abstract": abstract,
                                "claims": "Claims are not applicable to academic papers (ArXiv).",
                                "description": "Description retrieved via ArXiv PDF extraction.",
                                "inventors": authors,
                                "assignee": "ArXiv Research Preprints",
                                "filing_date": pub_date,
                                "publication_date": pub_date,
                                "cpc_codes": categories[:3] if categories else ["cs.AI"],
                                "ipc_codes": ["cs.AI"],
                                "pdf_url": pdf_url,
                                "source_repository": "ArXiv",
                                "domain_tags": [domain_keyword, "Academic Research"]
                            })
                            
                    # Respect API limits by delaying slightly
                    await asyncio.sleep(3.0)
                    
        except Exception as e:
            print(f"ArXiv Error: {e}")
            
        return results
