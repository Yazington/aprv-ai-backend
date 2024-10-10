from fastapi import APIRouter, UploadFile
from services.mongo_service import MongoService, mongo_service

router = APIRouter(
    prefix="/upload",
    tags=["Upload"],
)


@router.post("/image")
async def upload_image(file: UploadFile, mongo_service: MongoService = mongo_service):
    try:
        file_id = await mongo_service.fs.put(await file.read(), filename=file.filename)
        return {"message": "Image uploaded successfully", "file_id": str(file_id)}

    except Exception as e:
        return {"error": str(e)}


@router.post("/pdf")
async def upload_pdf(file: UploadFile, mongo_service: MongoService = mongo_service):
    try:
        file_id = await mongo_service.fs.put(await file.read(), filename=file.filename)
        return {"message": "PDF uploaded successfully", "file_id": str(file_id)}

    except Exception as e:
        return {"error": str(e)}
