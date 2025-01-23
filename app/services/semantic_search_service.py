# import asyncio
# import io
# import json
# import os
# import threading

# import numpy as np

# # Initialize FAISS with correct threading options
# os.environ['KMP_DUPLICATE_LIB_OK']='TRUE'
# from typing import Annotated, Dict, List

# import faiss
# import fitz  # type: ignore
# from fastapi import Depends, HTTPException
# from motor.motor_asyncio import AsyncIOMotorCollection
# from odmantic import ObjectId
# from openai import AsyncClient
# from tenacity import retry, stop_after_attempt, wait_random_exponential

# from app.config.logging_config import logger
# from app.config.settings import settings
# from app.models.conversation import Conversation
# from app.models.message import Message
# from app.models.task import Task
# from app.services.mongo_service import MongoService, get_mongo_service


# class SemanticSearchService:
#     def __init__(self, mongo_service: MongoService, faiss_index_dir: str = "faiss_indices"):
#         self.mongo_service = mongo_service
#         self.vector_collection: AsyncIOMotorCollection = self.mongo_service.client.get_database("vector_store").get_collection("embeddings")
#         if not settings or not settings.openai_api_key:
#             logger.error("OpenAI API key not configured")
#             raise HTTPException(status_code=500, detail="OpenAI API key not configured")
#         self.async_client = AsyncClient(api_key=settings.openai_api_key)

#         self.faiss_index_dir = faiss_index_dir
#         os.makedirs(self.faiss_index_dir, exist_ok=True)
#         self.dimension = 1536  # Update based on your OpenAI embedding dimensions

#         # Dictionaries to hold FAISS indices and locks per user
#         self.faiss_indices: Dict[str, faiss.IndexFlatIP] = {}
#         self.faiss_locks: Dict[str, threading.Lock] = {}

#     def _get_faiss_index_path(self, user_id: str) -> str:
#         """Get the file path for a user's FAISS index."""
#         return os.path.join(self.faiss_index_dir, f"faiss_{user_id}.index")

#     def _get_mapping_path(self, user_id: str) -> str:
#         """Get the file path for a user's mapping file."""
#         return os.path.join(self.faiss_index_dir, f"mapping_{user_id}.json")

#     def _load_faiss_index(self, user_id: str) -> faiss.IndexFlatIP:
#         """Load or create a FAISS index for a specific user with thread safety."""
#         if user_id not in self.faiss_locks:
#             self.faiss_locks[user_id] = threading.Lock()

#         with self.faiss_locks[user_id]:
#             index_path = self._get_faiss_index_path(user_id)
#             if os.path.exists(index_path):
#                 try:
#                     logger.info(f"Loading FAISS index for user {user_id} from disk.")
#                     index = faiss.read_index(index_path)
#                     if not isinstance(index, faiss.IndexFlatIP):
#                         logger.warning(f"FAISS index for user {user_id} is not IndexFlatIP. Recreating index.")
#                         index = faiss.IndexFlatIP(self.dimension)
#                 except Exception as e:
#                     logger.error(f"Failed to load FAISS index for user {user_id}: {e}. Creating a new index.")
#                     index = faiss.IndexFlatIP(self.dimension)
#             else:
#                 logger.info(f"Creating new FAISS index for user {user_id}.")
#                 index = faiss.IndexFlatIP(self.dimension)
#             self.faiss_indices[user_id] = index
#             return index

#     def _save_faiss_index(self, user_id: str):
#         """Save a user's FAISS index to disk."""
#         index = self.faiss_indices.get(user_id)
#         if index:
#             index_path = self._get_faiss_index_path(user_id)
#             faiss.write_index(index, index_path)
#             logger.info(f"FAISS index for user {user_id} saved to disk.")
#         else:
#             logger.error(f"No FAISS index found for user {user_id} to save.")

#     def _load_mapping(self, user_id: str) -> List[str]:
#         """Load the mapping list for a user."""
#         mapping_path = self._get_mapping_path(user_id)
#         if os.path.exists(mapping_path):
#             with open(mapping_path, 'r') as f:
#                 mapping = json.load(f)
#         else:
#             mapping = []
#         return mapping

#     def _save_mapping(self, user_id: str, mapping: List[str]):
#         """Save the mapping list for a user."""
#         mapping_path = self._get_mapping_path(user_id)
#         with open(mapping_path, 'w') as f:
#             json.dump(mapping, f)
#         logger.info(f"Mapping for user {user_id} saved.")

#     async def initialize(self):
#         """Initialize service by ensuring indexes exist and loading embeddings into FAISS."""
#         await self._ensure_mongo_indexes()
#         await self._load_all_embeddings_into_faiss()

#         # Verify FAISS indices
#         for user_id, index in self.faiss_indices.items():
#             logger.info(f"User {user_id} FAISS index has {index.ntotal} vectors.")

#     async def _ensure_mongo_indexes(self):
#         """Create required indexes in MongoDB."""
#         try:
#             existing_indexes = []
#             async for index in self.vector_collection.list_indexes():
#                 existing_indexes.append(index)

#             # Create compound index for user and conversation filtering
#             compound_index_exists = any(idx.get("name") == "user_conversation_index" for idx in existing_indexes)
#             if not compound_index_exists:
#                 await self.vector_collection.create_index(
#                     [("user_id", 1), ("conversation_id", 1)],
#                     name="user_conversation_index"
#                 )
#                 logger.info("Created compound index for user_id and conversation_id.")
#         except Exception as e:
#             logger.error(f"Error creating indexes: {e}")
#             raise HTTPException(status_code=500, detail="Failed to create indexes in MongoDB")

#     async def _load_all_embeddings_into_faiss(self):
#         """Load all embeddings from MongoDB into their respective FAISS indices."""
#         try:
#             # First, clean up any embeddings with wrong dimensions
#             cursor = self.vector_collection.find({})
#             async for doc in cursor:
#                 user_id = doc.get("user_id")
#                 embedding = doc.get("embedding")
#                 if user_id and embedding:
#                     if len(embedding) != self.dimension:
#                         logger.warning(f"Deleting embedding with incorrect dimension for user {user_id}. Got {len(embedding)}, expected {self.dimension}")
#                         await self.vector_collection.delete_one({"_id": doc["_id"]})

#             # Now load the remaining valid embeddings
#             cursor = self.vector_collection.find({}, {"embedding": 1, "user_id": 1})
#             async for doc in cursor:
#                 user_id = doc.get("user_id")
#                 embedding = doc.get("embedding")
#                 if user_id and embedding:
#                     logger.info(f"Loading embedding with dimension: {len(embedding)}, Expected: {self.dimension}")
#                     if len(embedding) != self.dimension:
#                         logger.error(f"Dimension mismatch for user {user_id}: Got {len(embedding)}, expected {self.dimension}")
#                         continue
                        
#                     if user_id not in self.faiss_indices:
#                         index = self._load_faiss_index(user_id)
#                     else:
#                         index = self.faiss_indices[user_id]
                        
#                     embedding_np = np.array(embedding).astype('float32')
#                     embedding_reshaped = embedding_np.reshape(1, -1)
#                     logger.info(f"Reshaped embedding shape: {embedding_reshaped.shape}")
                    
#                     faiss.normalize_L2(embedding_reshaped)  # Normalize for cosine similarity
#                     index.add(embedding_reshaped)
#             # After loading all embeddings, save indices to disk
#             for user_id in self.faiss_indices.keys():
#                 self._save_faiss_index(user_id)
#             logger.info("All embeddings loaded into FAISS indices.")
#         except Exception as e:
#             logger.error(f"Error loading embeddings into FAISS: {e}")
#             raise

#     @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
#     async def get_embedding(self, text: str) -> List[float]:
#         """Get OpenAI embedding for text"""
#         try:
#             response = await self.async_client.embeddings.create(
#                 model="text-embedding-ada-002",  # Update based on your model
#                 input=text
#             )
#             return response.data[0].embedding
#         except Exception as e:
#             logger.error(f"Error getting embedding: {e}")
#             raise

#     async def search_similar_text_in_documents_or_guidelines(self, query: str, user_id: str, conversation_id: str, limit: int = 5) -> List[str]:
#         """Search for similar text using FAISS vector similarity with user and conversation isolation"""
#         try:
#             logger.info(f"Starting semantic search for query: '{query}' in conversation: {conversation_id}")
            
#             # Get query embedding and validate dimensions
#             logger.info("Getting embedding for query...")
#             query_embedding = await self.get_embedding(query)
#             logger.info(f"Query embedding dimension: {len(query_embedding)}")
#             if len(query_embedding) != self.dimension:
#                 logger.error(f"Query embedding dimension mismatch. Got {len(query_embedding)}, expected {self.dimension}")
#                 return []

#             # Convert to numpy array and normalize
#             logger.info("Processing query vector...")
#             query_vector = np.array(query_embedding).astype('float32')
#             query_vector_reshaped = query_vector.reshape(1, -1)
#             faiss.normalize_L2(query_vector_reshaped)
#             logger.info(f"Query vector shape after normalization: {query_vector_reshaped.shape}")

#             # Load or get the user's FAISS index
#             logger.info(f"Loading FAISS index for user {user_id}...")
#             index = self.faiss_indices.get(user_id)
#             if not index:
#                 index = self._load_faiss_index(user_id)
#             logger.info(f"FAISS index contains {index.ntotal} vectors")

#             # Check if the index has vectors
#             if index.ntotal == 0:
#                 logger.error(f"FAISS index for user {user_id} is empty.")
#                 return []

#             # Load mapping first to ensure it exists
#             logger.info("Loading document mapping...")
#             mapping = self._load_mapping(user_id)
#             logger.info(f"Found {len(mapping)} documents in mapping")
#             if not mapping:
#                 logger.error(f"No mapping found for user {user_id}.")
#                 return []

#             # Perform FAISS search with cosine similarity
#             try:
#                 # Get more candidates than needed to ensure we find the best matches after filtering
#                 k = min(limit * 4, len(mapping))  # Get 4x more candidates
#                 logger.info(f"Searching FAISS index with k={k}...")
#                 distances, indices = index.search(query_vector_reshaped, k)
#                 logger.info(f"FAISS search found {len(indices[0])} initial matches for user {user_id}")
                
#                 # Convert distances to cosine similarity scores (-1 to 1)
#                 # FAISS returns inner products which are already normalized for cosine similarity
#                 similarity_scores = distances[0]  # These are already cosine similarities
#                 logger.info(f"Raw similarity scores: {similarity_scores}")
                
#                 # Create list of (index, score) pairs and sort by score
#                 scored_indices = [(idx, score) for idx, score in zip(indices[0], similarity_scores)]
#                 scored_indices.sort(key=lambda x: x[1], reverse=True)  # Sort by similarity score
                
#                 logger.info(f"Top 3 matches:")
#                 for i, (idx, score) in enumerate(scored_indices[:3]):
#                     if idx < len(mapping):
#                         doc_id = mapping[idx]
#                         logger.info(f"Match {i+1}: Index {idx}, Score {score:.4f}, Doc ID {doc_id}")
#             except Exception as e:
#                 logger.error(f"FAISS search failed for user {user_id}: {e}")
#                 return []

#             # Get document IDs from valid indices, maintaining score order
#             logger.info("Processing search results...")
#             scored_doc_ids = []
#             for idx, score in scored_indices:
#                 if idx < len(mapping):
#                     doc_id = mapping[idx]
#                     scored_doc_ids.append((doc_id, score))
#                     logger.debug(f"Mapped index {idx} to document ID {doc_id} with score {score}")

#             if not scored_doc_ids:
#                 logger.info(f"No valid document IDs found in FAISS results for user {user_id}")
#                 return []

#             logger.info(f"Found {len(scored_doc_ids)} valid document IDs")

#             # Fetch documents from MongoDB with conversation filtering
#             logger.info("Fetching documents from MongoDB...")
#             mongo_doc_ids = [ObjectId(doc_id) for doc_id, _ in scored_doc_ids]
#             query = {
#                 "_id": {"$in": mongo_doc_ids},
#                 "conversation_id": str(conversation_id),  # Ensure conversation_id is string
#                 "user_id": str(user_id)  # Ensure user_id is string
#             }
#             logger.info(f"MongoDB query: {query}")
            
#             # First check if documents exist
#             count = await self.vector_collection.count_documents(query)
#             logger.info(f"Found {count} matching documents in MongoDB")
            
#             if count == 0:
#                 # Try querying without conversation_id to see if that's the issue
#                 base_query = {"_id": {"$in": mongo_doc_ids}}
#                 base_count = await self.vector_collection.count_documents(base_query)
#                 logger.info(f"Found {base_count} documents when searching only by IDs")
                
#                 # Check a sample document to debug
#                 if base_count > 0:
#                     sample_doc = await self.vector_collection.find_one({"_id": mongo_doc_ids[0]})
#                     if sample_doc:
#                         logger.info(f"Sample document fields: {list(sample_doc.keys())}")
#                         logger.info(f"Sample document conversation_id: {sample_doc.get('conversation_id')}")
#                         logger.info(f"Sample document user_id: {sample_doc.get('user_id')}")
            
#             cursor = self.vector_collection.find(query, {"text": 1, "_id": 1})

#             # Build results maintaining similarity score ordering
#             doc_id_to_text = {}
#             doc_count = 0
#             async for doc in cursor:
#                 doc_id_to_text[str(doc["_id"])] = doc["text"]
#                 doc_count += 1
#             logger.info(f"Retrieved {doc_count} documents from MongoDB")

#             # Collect results ordered by similarity score
#             logger.info("Processing final results...")
#             results = []
#             seen_texts = set()  # To avoid duplicate content
#             for doc_id, score in scored_doc_ids:
#                 if doc_id in doc_id_to_text:
#                     text = doc_id_to_text[doc_id]
#                     # Only add if we haven't seen this exact text before
#                     if text not in seen_texts:
#                         # Log a preview of the text
#                         preview = text[:100] + "..." if len(text) > 100 else text

#                         results.append(text)
#                         seen_texts.add(text)
#                         if len(results) >= limit:
#                             logger.info("Reached result limit")
#                             break

#             logger.info(f"Retrieved {len(results)} similar texts for user {user_id} in conversation {conversation_id}")
#             return results

#         except Exception as e:
#             logger.error(f"Error during semantic search: {e}")
#             return []

#     async def insert_document(self, content: bytes | str, user_id: str, conversation_id: str, chunk_size: int = 1000):
#         """Insert document into MongoDB and FAISS index with user and conversation isolation"""
#         try:
#             # Handle input content
#             if isinstance(content, bytes):
#                 try:
#                     # Try to extract text from PDF first
#                     pdf_stream = io.BytesIO(content)
#                     pdf_doc = fitz.open(stream=pdf_stream, filetype="pdf")
#                     text = ""
#                     for page in pdf_doc:
#                         text += page.get_text()
#                     pdf_doc.close()
#                 except Exception as e:
#                     logger.error(f"Failed to extract text from PDF: {e}")
#                     try:
#                         # Fallback to UTF-8
#                         text = content.decode('utf-8')
#                     except UnicodeDecodeError:
#                         # If UTF-8 fails, use a more lenient encoding
#                         text = content.decode('latin-1')
#             else:
#                 text = content

#             # Split text into chunks
#             chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

#             # Load existing mapping
#             mapping = self._load_mapping(user_id)

#             async def process_chunk(chunk: str) -> str:
#                 # Get embedding for chunk
#                 embedding = await self.get_embedding(chunk)
#                 embedding_np = np.array(embedding).astype('float32')
#                 logger.info(f"Embedding dimension: {len(embedding)}, Expected: {self.dimension}")
#                 if len(embedding) != self.dimension:
#                     raise ValueError(f"Embedding dimension mismatch. Got {len(embedding)}, expected {self.dimension}")
                
#                 faiss.normalize_L2(embedding_np.reshape(1, -1))  # Normalize for cosine similarity


#                 # Insert into MongoDB
#                 # Ensure IDs are stored as strings consistently
#                 result = await self.vector_collection.insert_one({
#                     "text": chunk,
#                     "embedding": embedding,
#                     "user_id": str(user_id),
#                     "conversation_id": str(conversation_id)
#                 })
#                 logger.info(f"Inserted document with user_id: {str(user_id)}, conversation_id: {str(conversation_id)}")
#                 doc_id = str(result.inserted_id)

#                 # Ensure lock exists and load index
#                 if user_id not in self.faiss_locks:
#                     logger.info(f"Initializing lock for user {user_id}")
#                     self.faiss_locks[user_id] = threading.Lock()
                
#                 # Add embedding to FAISS index with thread safety
#                 with self.faiss_locks[user_id]:
#                     index = self.faiss_indices.get(user_id)
#                     if not index:
#                         index = self._load_faiss_index(user_id)
#                     index.add(embedding_np.reshape(1, -1))
#                     logger.info(f"Inserted chunk into FAISS index for user {user_id}.")

#                 return doc_id

#             # Process chunks concurrently with a reasonable batch size
#             batch_size = 5  # Adjust based on your needs
#             for i in range(0, len(chunks), batch_size):
#                 batch = chunks[i:i + batch_size]
#                 doc_ids = await asyncio.gather(*[process_chunk(chunk) for chunk in batch])
#                 mapping.extend(doc_ids)

#             # Save FAISS index and mapping to disk after insertion
#             self._save_faiss_index(user_id)
#             self._save_mapping(user_id, mapping)
#         except Exception as e:
#             logger.error(f"Error inserting document: {e}")
#             raise


# async def get_semantic_search_service(
#     mongo_service: Annotated[MongoService, Depends(get_mongo_service)]
# ) -> SemanticSearchService:
#     service = SemanticSearchService(mongo_service)
#     await service.initialize()
#     return service
