import asyncio
from haystack import AsyncPipeline
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.retrievers import InMemoryEmbeddingRetriever, InMemoryBM25Retriever
from haystack.components.joiners import DocumentJoiner
from haystack.components.builders import ChatPromptBuilder
from haystack.components.generators.chat import OpenAIChatGenerator

hybrid_rag_retrieval = AsyncPipeline()
hybrid_rag_retrieval.add_component("text_embedder", SentenceTransformersTextEmbedder())
hybrid_rag_retrieval.add_component("embedding_retriever", InMemoryEmbeddingRetriever(document_store=document_store))
hybrid_rag_retrieval.add_component("bm25_retriever", InMemoryBM25Retriever(document_store=document_store))
hybrid_rag_retrieval.add_component("document_joiner", DocumentJoiner())
hybrid_rag_retrieval.add_component("prompt_builder", ChatPromptBuilder(template=prompt_template))
hybrid_rag_retrieval.add_component("llm", OpenAIChatGenerator())

hybrid_rag_retrieval.connect("text_embedder", "embedding_retriever")
hybrid_rag_retrieval.connect("bm25_retriever", "document_joiner")
hybrid_rag_retrieval.connect("embedding_retriever", "document_joiner")
hybrid_rag_retrieval.connect("document_joiner", "prompt_builder.documents")
hybrid_rag_retrieval.connect("prompt_builder", "llm")

async def process_results():
    async for partial_output in hybrid_rag_retrieval.run_async_generator(
            data=data,
            include_outputs_from={"document_joiner", "llm"}
    ):
        # Each partial_output contains the results from a completed component
        if "retriever" in partial_output:
            print("Retrieved documents:", len(partial_output["document_joiner"]["documents"]))
        if "llm" in partial_output:
            print("Generated answer:", partial_output["llm"]["replies"][0])

asyncio.run(process_results())