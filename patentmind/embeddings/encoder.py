import hashlib
import math
import torch
from typing import List
from rich.console import Console

console = Console()

class DeterministicHashEncoder:
    """
    Fallback 384-dimensional dense vector encoder.
    Used when SentenceTransformer or underlying C-extensions (_regex.pyd) 
    are blocked by OS Application Control policies or missing.
    """
    def __init__(self, vector_dim: int = 384):
        self.vector_dim = vector_dim

    def encode(self, texts: List[str], batch_size: int = 64, show_progress_bar: bool = False, convert_to_numpy: bool = True) -> List[List[float]]:
        embeddings = []
        for text in texts:
            vec = []
            for i in range(self.vector_dim):
                h = hashlib.sha256(f"{text}_{i}".encode('utf-8')).hexdigest()
                val = (int(h[:8], 16) / 0xFFFFFFFF) * 2.0 - 1.0
                vec.append(val)
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            vec = [x / norm for x in vec]
            embeddings.append(vec)
        return embeddings

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except Exception as e:
    console.print(f"[yellow]SentenceTransformer import disabled ({e}). Using DeterministicHashEncoder fallback.[/yellow]")
    SentenceTransformer = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class EmbeddingEncoder:
    """
    SentenceTransformer all-MiniLM-L6-v2 GPU batch encoder with Hash fallback.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None

        if SENTENCE_TRANSFORMERS_AVAILABLE:
            console.print(f"[bold blue]Loading SentenceTransformer '{model_name}' on {self.device}...[/bold blue]")
            try:
                self.model = SentenceTransformer(model_name, device=self.device)
            except Exception as e:
                console.print(f"[yellow]SentenceTransformer device fallback: {e}[/yellow]")
                try:
                    self.model = SentenceTransformer(model_name, device="cpu")
                except Exception as e2:
                    console.print(f"[yellow]SentenceTransformer load failed: {e2}. Falling back to HashEncoder.[/yellow]")
                    self.model = DeterministicHashEncoder()
        else:
            console.print("[bold yellow]SentenceTransformer unavailable — using DeterministicHashEncoder (384-dim).[/bold yellow]")
            self.model = DeterministicHashEncoder()

    def batch_encode(self, texts: List[str], batch_size: int = 64) -> List[List[float]]:
        if not texts:
            return []
        try:
            res = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            return res.tolist() if hasattr(res, "tolist") else res
        except Exception as e:
            console.print(f"[yellow]Encoding error ({e}), using hash encoder fallback.[/yellow]")
            fallback = DeterministicHashEncoder()
            return fallback.encode(texts)


_encoder_instance = None


def get_encoder() -> EmbeddingEncoder:
    global _encoder_instance
    if _encoder_instance is None:
        _encoder_instance = EmbeddingEncoder()
    return _encoder_instance

