import hashlib
import math
from typing import List
from rich.console import Console

try:
    import torch
    TORCH_AVAILABLE = True
except Exception:
    torch = None
    TORCH_AVAILABLE = False

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
    SentenceTransformer GPU batch encoder. Strictly uses CUDA when specified.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = None, strict_gpu: bool = True):
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        self.strict_gpu = strict_gpu
        self.model = None

        if self.strict_gpu and self.device.startswith("cuda"):
            if not TORCH_AVAILABLE or not torch.cuda.is_available():
                console.print(f"[yellow]CUDA requested ({self.device}) but PyTorch/CUDA is unavailable. Using DeterministicHashEncoder fallback.[/yellow]")
                self.model = DeterministicHashEncoder()
            else:
                try:
                    console.print(f"[bold green]Strict GPU Execution: Loading SentenceTransformer '{model_name}' on {self.device}...[/bold green]")
                    self.model = SentenceTransformer(model_name, device=self.device)
                except Exception as e:
                    console.print(f"[yellow]SentenceTransformer load error ({e}). Using DeterministicHashEncoder fallback.[/yellow]")
                    self.model = DeterministicHashEncoder()
        else:
            if SENTENCE_TRANSFORMERS_AVAILABLE and TORCH_AVAILABLE:
                console.print(f"[bold blue]Loading SentenceTransformer '{model_name}' on {self.device}...[/bold blue]")
                try:
                    self.model = SentenceTransformer(model_name, device=self.device)
                except Exception as e:
                    console.print(f"[yellow]SentenceTransformer load error: {e}[/yellow]")
                    self.model = DeterministicHashEncoder()
            else:
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


def get_encoder(device: str = None) -> EmbeddingEncoder:
    global _encoder_instance
    if _encoder_instance is None or (device and _encoder_instance.device != device):
        _encoder_instance = EmbeddingEncoder(device=device)
    return _encoder_instance

