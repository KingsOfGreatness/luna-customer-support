import logging
from typing import List, Dict, Optional
import sqlite3
import os
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings as ChromaSettings
import json

logger = logging.getLogger(__name__)

class FAQService:
    def __init__(self):
        self.db_path = "customer_support.db"
        self.chroma_client = None
        self.embedding_model = None
        self._init_database()
        self._init_vector_store()
    
    def _init_database(self):
        """Initialize SQLite database for FAQ storage"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create FAQ table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS faqs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    language TEXT DEFAULT 'english',
                    category TEXT DEFAULT 'general',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("FAQ database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize FAQ database: {e}")
    
    def _init_vector_store(self):
        """Initialize ChromaDB for semantic search"""
        try:
            # Initialize embedding model
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Initialize ChromaDB client
            chroma_settings = ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
            self.chroma_client = chromadb.Client(chroma_settings)
            
            # Create or get collection
            try:
                self.collection = self.chroma_client.get_collection(name="faq_collection")
            except:
                self.collection = self.chroma_client.create_collection(name="faq_collection")
            
            logger.info("Vector store initialized successfully")
            
        except Exception as e:
            logger.warning(f"Vector store initialization failed: {e}")
            self.chroma_client = None
            self.embedding_model = None
    
    def add_faq(self, company_id: int, question: str, answer: str, language: str = "english", category: str = "general"):
        """Add FAQ to database and vector store"""
        try:
            # Add to SQLite
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO faqs (company_id, question, answer, language, category)
                VALUES (?, ?, ?, ?, ?)
            ''', (company_id, question, answer, language, category))
            
            faq_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Add to vector store if available
            if self.chroma_client and self.embedding_model:
                try:
                    # Create document ID
                    doc_id = f"faq_{company_id}_{faq_id}"
                    
                    # Add to ChromaDB
                    self.collection.add(
                        documents=[question],
                        metadatas=[{
                            "company_id": company_id,
                            "answer": answer,
                            "language": language,
                            "category": category,
                            "faq_id": faq_id
                        }],
                        ids=[doc_id]
                    )
                except Exception as e:
                    logger.warning(f"Failed to add FAQ to vector store: {e}")
            
            logger.info(f"Added FAQ for company {company_id} in {language}")
            return faq_id
            
        except Exception as e:
            logger.error(f"Failed to add FAQ: {e}")
            raise
    
    def search_faq(self, query: str, company_id: int, limit: int = 3) -> List[Dict]:
        """Search FAQ using vector similarity"""
        try:
            results = []
            
            # Try vector search first
            if self.chroma_client and self.collection:
                try:
                    search_results = self.collection.query(
                        query_texts=[query],
                        where={"company_id": company_id},
                        n_results=limit
                    )
                    
                    if search_results['documents'] and search_results['documents'][0]:
                        for i, doc in enumerate(search_results['documents'][0]):
                            metadata = search_results['metadatas'][0][i]
                            results.append({
                                "question": doc,
                                "answer": metadata.get("answer", ""),
                                "language": metadata.get("language", "english"),
                                "category": metadata.get("category", "general"),
                                "score": search_results['distances'][0][i] if 'distances' in search_results else 1.0
                            })
                    
                    if results:
                        return results
                        
                except Exception as e:
                    logger.warning(f"Vector search failed, falling back to SQL: {e}")
            
            # Fallback to SQL text search
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT question, answer, language, category 
                FROM faqs 
                WHERE company_id = ? AND (
                    question LIKE ? OR answer LIKE ?
                )
                LIMIT ?
            ''', (company_id, f"%{query}%", f"%{query}%", limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            for row in rows:
                results.append({
                    "question": row[0],
                    "answer": row[1],
                    "language": row[2],
                    "category": row[3],
                    "score": 0.8  # Default score for SQL search
                })
            
            return results
            
        except Exception as e:
            logger.error(f"FAQ search failed: {e}")
            return []
    
    def get_company_faqs(self, company_id: int, language: str = None) -> List[Dict]:
        """Get all FAQs for a company, optionally filtered by language"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if language:
                cursor.execute('''
                    SELECT question, answer, language, category 
                    FROM faqs 
                    WHERE company_id = ? AND language = ?
                    ORDER BY created_at DESC
                ''', (company_id, language))
            else:
                cursor.execute('''
                    SELECT question, answer, language, category 
                    FROM faqs 
                    WHERE company_id = ?
                    ORDER BY created_at DESC
                ''', (company_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "question": row[0],
                    "answer": row[1],
                    "language": row[2],
                    "category": row[3]
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"Failed to get company FAQs: {e}")
            return []