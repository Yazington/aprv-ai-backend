# APRV AI Backend

A FastAPI project with integrated Ruff, Mypy, and Black for linting, type checking, and formatting.

## Setup

1. **Clone the repository**

2. **Create and activate the Conda environment**

   ```bash
   conda create -n aprv-ai-backend python=3.11
   conda activate aprv-ai-backend
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**

   ```bash
   uvicorn app.main:app --reload --port 9000
   ```

## Tools

- **FastAPI**: Web framework
- **Ruff**: Linter
- **Mypy**: Type checker
- **Black**: Formatter

# Commands

```
run app under docker: docker-compose up -d
get logs for app under docker: docker logs $(docker ps -a | grep aprv-ai | awk '{print $1}')
start app: uvicorn app.main:app --reload --port 9000
```

DOCKER:

```
docker build --build-arg OPENAI_API_KEY=api-key \
	     --build-arg APRV_AI_API_KEY=api-key \
	     --build-arg GOOGLE_CLIENT_ID=client-id \
	     --build-arg MONGO_URL=db-url \
	     -t my-fastapi-app .
docker run -p 9000:9000   --network=aprv-ai-local   --cpus="8"   --memory="8g"   -v /home/yaz/Workspace/aprv-ai/aprv-ai-backend/data:/app/data   my-fastapi-app
```

## Codebase Overview

The aprv-ai-backend is a brand guideline/licensing assistant application built with FastAPI. It provides the following key features:

### Core Functionality

- User authentication via Google OAuth
- Chat-based interaction with streaming responses
- File upload and management for designs and guidelines
- Design review capabilities against brand guidelines
- Semantic search using RAG (Retrieval Augmented Generation)
- Integration with OpenAI GPT-4 for natural language processing

### Technology Stack

- **Web Framework**: FastAPI
- **Database**: MongoDB (using ODMantic ORM)
- **AI Services**: OpenAI API, LightRAG
- **Authentication**: JWT tokens, Google OAuth
- **File Storage**: MongoDB GridFS
- **Streaming**: Server-sent events (SSE)

### Key Components

#### Authentication

- `app/api/auth.py`: Handles Google OAuth and JWT token generation
- `app/middlewares/token_validation_middleware.py`: Validates JWT tokens

#### Chat Functionality

- `app/api/chat.py`: Implements chat endpoints with streaming responses
- `app/services/openai_service.py`: Manages OpenAI API integration
- `app/utils/llm_tools.py`: Provides tools for semantic search and file management

#### File Management

- `app/api/upload.py`: Handles file uploads
- `app/services/mongo_service.py`: Manages MongoDB operations
- `app/models/files.py`: Defines file-related models

#### Design Review

- `app/services/rag_service.py`: Implements RAG-based semantic search
- `app/models/review.py`: Defines review models
- `app/services/approval_service.py`: Manages approval workflows

### Architecture

The application follows a clean architecture with clear separation of concerns:

1. **API Layer**: FastAPI routes in `app/api/`
2. **Service Layer**: Business logic in `app/services/`
3. **Data Layer**: Models in `app/models/` and MongoDB integration
4. **Utility Layer**: Helper functions and tools in `app/utils/`

# ALL SOURCE CODE DEFINITIONS

### app/**init**.py

### app/main.py

### app/api/**init**.py

### app/api/auth.py

- async def auth_google

### app/api/chat.py

- async def create_prompt
- async def get_prompt_model_response
- async def event_generator

### app/api/conversation.py

- async def get_conversations_by_user_id
- async def get_conversation_by_conversation_id
- async def get_conversations_messages
- async def process_design
- async def process_status
- async def get_process_result
- async def get_conversation_reviews

### app/api/upload.py

- async def upload_image
- async def upload_pdf
- async def get_all_conversation_files

### app/config/**init**.py

### app/config/logging_config.py

### app/config/profiling.py

### app/config/settings.py

- class Settings

### app/exceptions/bad_conversation_files.py

- class DesignOrGuidelineNotFoundError
- class FileNotFoundError

### app/middlewares/**init**.py

### app/middlewares/token_validation_middleware.py

- class TokenValidationMiddleware
- async def dispatch
- def \_unauthorized_response

### app/models/**init**.py

### app/models/auth_request.py

- class AuthRequest

### app/models/chat_models.py

- class ChatRequest
- class ChatResponse

### app/models/conversation.py

- class Conversation

### app/models/create_prompt_request.py

- class CreatePromptRequest

### app/models/files.py

- class File
- class FileResponse

### app/models/llm_ready_page.py

- class BrandGuidelineReviewResource
- class LLMPageInferenceResource

### app/models/message.py

- class Message

### app/models/review.py

- class Review

### app/models/task.py

- class TaskStatus
- class Task

### app/models/users.py

- class GoogleAuthInfo
- class User

### app/services/**init**.py

### app/services/approval_service.py

- class ApprovalService
- async def validate_design_against_all_documents
- async def process_page_content
- async def background_process_design
- def get_existing_files_as_bytes
- async def create_task
- def get_page_images_as_bytes
- async def compare_design_against_page
- def init_subprocess_models
- def extract_and_store_tables_as_string
- def get_approval_service

### app/services/auth_service.py

- class AuthService
- async def generate_access_token
- async def verify_google_token
- def get_auth_service

### app/services/conversation_service.py

- class ConversationService
- async def create_conversation
- async def update_conversation
- async def get_conversations_by_user_id
- async def get_conversation_by_conversation_id
- def get_conversation_service

### app/services/message_service.py

- class MessageService
- async def create_message
- async def retrieve_message_by_id
- async def retrieve_message_history
- async def get_conversations_messages
- def get_tokenized_message_count
- def get_message_service

### app/services/mongo_service.py

- class MongoService
- def get_mongo_service

### app/services/openai_service.py

- class OpenAIClient
- async def stream_openai_llm_response
- async def get_openai_multi_images_response
- def get_openai_client

### app/services/pdf_extraction_service.py

- class PDFExtractionService
- async def extract_tables_and_text_from_file
- async def get_tables_for_each_page_formatted_as_text
- async def extract_tables_and_check_time
- def get_pdf_extraction_service

### app/services/queue_system.py

- def execute_api_call
- def queue_openai_task

### app/services/rag_service.py

- class RagService
- async def search_similar_text
- async def insert_to_rag
- async def insert_to_rag_with_message
- def split_document_into_chunks
- async def embedding_func
- def get_rag_service

### app/services/upload_service.py

- class UploadService
- async def upload_guideline_and_concat
- def get_upload_service

### app/services/user_service.py

- class UserService
- async def get_user_by_email
- async def create_user
- async def update_user
- async def get_or_create_user
- def get_user_service

### app/utils/llm_tools.py

- class LLMToolsService
- async def search_similar_text
- async def check_for_conversation_uploaded_design_file
- async def check_for_conversation_uploaded_guidelines_file
- async def check_for_conversation_review_or_approval_process_file
- async def get_guidelines_page_review
- def get_llm_tools_service

### app/utils/tiktoken.py

- def num_tokens_from_messages
- def truncate_all
- def count_tokens
- def truncate_text
