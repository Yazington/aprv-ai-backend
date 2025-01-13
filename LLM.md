This is the backend of a project. The project is an application of user (licensee/licensor) that can work with an LLM to help with guideline approval process. 
It can be in design approval (Going through each page of a guideline and checking if a design/image respects the guidelines).

Tech stack:
- FastAPI
- Odmantic
- Pydantic
- LightRAG -> for rag 
- OpenAI API for the LLM
- Google Auth for SSO (On the frontend, we use SSO and verify here on the backend)

When a user wants to send a prompt, we create a Message. If the body of the request sent contains a conversation id, we use existing conversation and only append the new message.
If no conversation id is provided, we create a new conversation with the new message provided. 

You can check all endpoints in `openapi.json` if you need a quick overview.

Application is currently running `uvicorn app.main:app --reload --port 9000` and hot reloading is enabled on VS Code