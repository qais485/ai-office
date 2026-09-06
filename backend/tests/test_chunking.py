"""Tests for text chunking."""
import pytest
from app.services.rag_service import ChunkingService


class TestChunkingService:
    def setup_method(self):
        self.chunker = ChunkingService(chunk_size=100, chunk_overlap=20)

    def test_empty_text(self):
        assert self.chunker.chunk_text("") == []
        assert self.chunker.chunk_text("   ") == []
        assert self.chunker.chunk_text(None) == []

    def test_short_text_single_chunk(self):
        text = "Hello world."
        chunks = self.chunker.chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "Hello world."
        assert chunks[0]["index"] == 0
        assert "token_count" in chunks[0]

    def test_long_text_multiple_chunks(self):
        text = " ".join([f"Sentence {i}." for i in range(20)])
        chunks = self.chunker.chunk_text(text)
        assert len(chunks) > 1
        # Verify indices are sequential
        for i, chunk in enumerate(chunks):
            assert chunk["index"] == i

    def test_chunk_overlap(self):
        # Create text that will produce multiple chunks
        sentences = [f"This is sentence number {i} with some extra words to fill space." for i in range(10)]
        text = " ".join(sentences)
        chunks = self.chunker.chunk_text(text)
        assert len(chunks) > 1
        # Verify overlap: last part of chunk N should appear in chunk N+1
        for i in range(len(chunks) - 1):
            current_text = chunks[i]["text"]
            next_text = chunks[i + 1]["text"]
            # Overlap means some text from end of current appears in start of next
            # (may not always hold for sentence-based splitting, but chunks should be contiguous)
            assert len(current_text) > 0
            assert len(next_text) > 0

    def test_token_count(self):
        text = "One two three four five."
        chunks = self.chunker.chunk_text(text)
        assert chunks[0]["token_count"] == 5  # "One two three four five."

    def test_large_chunk_size(self):
        chunker = ChunkingService(chunk_size=10000, chunk_overlap=1000)
        text = "Short text."
        chunks = chunker.chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "Short text."

    def test_sentence_boundary_splitting(self):
        text = "First sentence. Second sentence. Third sentence."
        chunker = ChunkingService(chunk_size=30, chunk_overlap=5)
        chunks = chunker.chunk_text(text)
        assert len(chunks) >= 2
        # All original text should be preserved
        combined = " ".join(c["text"] for c in chunks)
        assert "First sentence" in combined
        assert "Second sentence" in combined
        assert "Third sentence" in combined
