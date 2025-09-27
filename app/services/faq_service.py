import logging
import json
from typing import List, Dict, Optional
import sqlite3

logger = logging.getLogger(__name__)

class FAQService:
    def __init__(self):
        self.db_path = "customer_support.db"
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS faqs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER,
                    question TEXT,
                    answer TEXT,
                    language TEXT
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Database init failed: {e}")
    
    def add_faq(self, company_id: int, question: str, answer: str, language: str):
        """Add FAQ to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO faqs (company_id, question, answer, language) VALUES (?, ?, ?, ?)",
                (company_id, question, answer, language)
            )
            conn.commit()
            conn.close()
            logger.info(f"Added FAQ for company {company_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add FAQ: {e}")
            return False
    
    def search_relevant(self, query: str, company_id: int, language: str, top_k: int = 3) -> List[Dict]:
        """Simple keyword search for FAQs"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Simple keyword matching
            cursor.execute(
                "SELECT question, answer FROM faqs WHERE company_id = ? AND language = ?",
                (company_id, language)
            )
            
            results = []
            for question, answer in cursor.fetchall():
                if any(word.lower() in query.lower() for word in question.split()):
                    results.append({
                        "question": question,
                        "answer": answer,
                        "score": 0.8
                    })
            
            conn.close()
            return results[:top_k]
        except Exception as e:
            logger.error(f"FAQ search failed: {e}")
            return []