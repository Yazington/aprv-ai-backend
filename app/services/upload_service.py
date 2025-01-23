from io import BytesIO
from typing import Annotated

from fastapi import Depends
from gridfs import GridOut
from odmantic import ObjectId

from app.config.logging_config import logger
from app.services.mongo_service import MongoService, get_mongo_service
from app.services.pdf_service import PDFService, get_pdf_service


class UploadService:
    def __init__(self, mongo_service: MongoService, pdf_extraction_service: PDFService):
        self.mongo_service = mongo_service
        self.pdf_extraction_service = pdf_extraction_service



def get_upload_service(
    mongo_service: Annotated[MongoService, Depends(get_mongo_service)],
    pdf_extraction_service: Annotated[PDFService, Depends(get_pdf_service)],
):
    return UploadService(mongo_service, pdf_extraction_service)
