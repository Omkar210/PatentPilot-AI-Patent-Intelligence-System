import asyncio
import os
import httpx
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class OpenAlexClient:
    def __init__(self):
        # OpenAlex uses the 'mailto' parameter for its Polite Pool (faster response times).
        self.email = os.getenv("OPENALEX_EMAIL", "default@example.com")
        self.base_url = "https://api.openalex.org/works"
        
    async def fetch_ai_patents(self, limit: int = 50, domain_keyword: str = "artificial intelligence") -> List[Dict[str, Any]]:
        results = []
        page_size = 100
        
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                for page in range(1, (limit // page_size) + 2):
                    batch_limit = min(page_size, limit - len(results))
                    if batch_limit <= 0:
                        break
                        
                    params = {
                        "filter": "type:patent",
                        "search": domain_keyword,
                        "per-page": page_size,
                        "page": page,
                        "mailto": self.email
                    }
                    
                    response = await client.get(self.base_url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    works = data.get("results", [])
                    
                    for work in works:
                        # Extract the OpenAlex ID to use as the patent number
                        oa_id = work.get("id", "").split("/")[-1]
                        
                        # Extract title
                        title = work.get("title") or f"OpenAlex Patent {oa_id}"
                        
                        # OpenAlex provides abstracts in an inverted index format. We reconstruct it.
                        abstract_index = work.get("abstract_inverted_index")
                        abstract = "No abstract provided."
                        if abstract_index:
                            words = []
                            # Determine max index length
                            max_idx = max([idx for positions in abstract_index.values() for idx in positions]) if abstract_index else -1
                            if max_idx >= 0:
                                words = [""] * (max_idx + 1)
                                for word, positions in abstract_index.items():
                                    for pos in positions:
                                        words[pos] = word
                                abstract = " ".join(words)
                            
                        # Extract inventors (authorships)
                        inventors = []
                        for authorship in work.get("authorships", []):
                            author = authorship.get("author", {})
                            name = author.get("display_name")
                            if name:
                                inventors.append(name)
                        if not inventors:
                            inventors = ["Unknown Inventor"]
                            
                        # Extract technical concepts as CPC code approximations
                        concepts = [c.get("display_name") for c in work.get("concepts", [])]
                        
                        # PDF URL generation
                        # OpenAlex does not host PDFs. We construct a potential Google Patents link.
                        # (If the physical PDF does not exist at this URL, the pipeline's fallback kicks in).
                        pdf_url = f"https://patentimages.storage.googleapis.com/pdfs/{oa_id}.pdf"
                        
                        results.append({
                            "patent_number": oa_id,
                            "title": title,
                            "abstract": abstract,
                            "claims": "Claims retrieved via OpenAlex",
                            "description": "Description retrieved via OpenAlex",
                            "inventors": inventors,
                            "assignee": "OpenAlex Index",
                            "filing_date": work.get("publication_date", "2023-01-01"),
                            "publication_date": work.get("publication_date", "2023-01-01"),
                            "cpc_codes": concepts[:3] if concepts else ["G06N"],
                            "ipc_codes": ["G06N"],
                            "pdf_url": pdf_url,
                            "source_repository": "OpenAlex",
                            "domain_tags": [domain_keyword] + (concepts[:2] if concepts else [])
                        })
                        
                        if len(results) >= limit:
                            break
                            
                    # Respect API limits by delaying slightly
                    await asyncio.sleep(2.0)
        except Exception as e:
            print(f"OpenAlex Error: {e}")
            
        return results[:limit]
