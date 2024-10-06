from fastapi import APIRouter, UploadFile
from models.document import Document
from services.mongo_service import MongoService, mongo_service

router = APIRouter(
    prefix="/upload",
    tags=["Upload"],
)


@router.post("/image")
async def upload_image(file: UploadFile, mongo_service: MongoService = mongo_service):
    try:
        file_id = await mongo_service.fs.put(await file.read(), filename=file.filename)
        saved_document = await mongo_service.engine.save(Document(fs_id=file_id))
        return {"message": "Image uploaded successfully", "file_id": str(file_id), "document_id": saved_document.id}

    except Exception as e:
        return {"error": str(e)}


@router.post("/pdf")
async def upload_pdf(file: UploadFile, mongo_service: MongoService = mongo_service):
    try:
        file_id = await mongo_service.fs.put(await file.read(), filename=file.filename)
        saved_document = await mongo_service.engine.save(Document(fs_id=file_id))
        return {"message": "PDF uploaded successfully", "file_id": str(file_id), "document_id": saved_document.id}

    except Exception as e:
        return {"error": str(e)}
