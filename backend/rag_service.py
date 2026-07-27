import os
import json
import chromadb
from typing import List, Dict, Any

class LabRAGService:
    def __init__(self, db_path: str = "./chroma_db"):
        """
        Initializes the persistent ChromaDB client and indexes our diagnostic lab catalog & FAQs.
        """
        self.db_path = db_path
        self.client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.client.get_or_create_collection(
            name="lab_knowledge_base",
            metadata={"hnsw:space": "cosine"}
        )
        self._load_and_index_data()

    def _load_and_index_data(self):
        """
        Loads test_catalog.json and faqs.json from the data/ directory and embeds them into ChromaDB.
        Only indexes if collection is currently empty to avoid duplicate insertions.
        """
        if self.collection.count() > 0:
            # Already indexed
            return

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        catalog_path = os.path.join(base_dir, "data", "test_catalog.json")
        faqs_path = os.path.join(base_dir, "data", "faqs.json")

        documents = []
        metadatas = []
        ids = []

        # 1. Index Test Catalog
        if os.path.exists(catalog_path):
            with open(catalog_path, "r", encoding="utf-8") as f:
                tests = json.load(f)
                for t in tests:
                    doc_text = (
                        f"Test Name: {t['name']} ({', '.join(t.get('aliases', []))})\n"
                        f"Category: {t['category']} | Price: ₹{t['price_inr']} INR\n"
                        f"Fasting Required: {'Yes (' + str(t['fasting_hours']) + ' hours)' if t['fasting_required'] else 'No'}\n"
                        f"Sample Type: {t['sample_type']} | Turnaround Time: {t['turnaround_time']}\n"
                        f"Description: {t['description']}"
                    )
                    documents.append(doc_text)
                    metadatas.append({
                        "type": "test",
                        "name": t["name"],
                        "price": t["price_inr"],
                        "fasting": str(t["fasting_required"])
                    })
                    ids.append(t["test_id"])

        # 2. Index FAQs
        if os.path.exists(faqs_path):
            with open(faqs_path, "r", encoding="utf-8") as f:
                faqs = json.load(f)
                for faq in faqs:
                    doc_text = (
                        f"Laboratory Policy FAQ: {faq['question']}\n"
                        f"Aliases/Keywords: {', '.join(faq.get('aliases', []))}\n"
                        f"Policy Answer: {faq['answer']}"
                    )
                    documents.append(doc_text)
                    metadatas.append({
                        "type": "faq",
                        "question": faq["question"]
                    })
                    ids.append(faq["faq_id"])

        if documents:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"[RAG Service] Successfully indexed {len(documents)} laboratory records into ChromaDB.")

    def search_knowledge_base(self, query_text: str, n_results: int = 3) -> str:
        """
        Performs vector similarity search on the user's query and returns formatted context string
        to be injected into the LLM system prompt.
        """
        results = self.collection.query(
            query_texts=[query_text],
            n_results=min(n_results, self.collection.count())
        )

        if not results or not results.get("documents") or not results["documents"][0]:
            return "No specific laboratory tests or policies found in knowledge base."

        retrieved_docs = results["documents"][0]
        formatted_context = "=== RETRIEVED LABORATORY KNOWLEDGE BASE ===\n"
        for i, doc in enumerate(retrieved_docs, 1):
            formatted_context += f"--- Result {i} ---\n{doc}\n\n"
        
        return formatted_context.strip()


# Global singleton instance for easy import across FastAPI routes
rag_service = None

def get_rag_service() -> LabRAGService:
    global rag_service
    if rag_service is None:
        rag_service = LabRAGService()
    return rag_service


if __name__ == "__main__":
    # Test execution when run standalone
    service = LabRAGService()
    print("\n--- Test RAG Search: 'how much is lipid profile and do i need fasting' ---")
    print(service.search_knowledge_base("how much is lipid profile and do i need fasting", n_results=2))
