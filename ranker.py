from haystack import Document
from haystack.components.rankers import SentenceTransformersSimilarityRanker

ranker = SentenceTransformersSimilarityRanker()
docs = [Document(content="Paris"), Document(content="Berlin")]
query = "City in Germany"
ranker.warm_up()
result = ranker.run(query=query, documents=docs)
docs = result["documents"]
print(docs[0].content)