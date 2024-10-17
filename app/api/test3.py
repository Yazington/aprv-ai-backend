# # new in v0.3: gmft.auto
# from gmft.auto import AutoTableDetector, AutoTableFormatter
# from gmft.pdf_bindings import PyPDFium2Document
# import pandas as pd

# detector = AutoTableDetector()
# formatter = AutoTableFormatter()

# def ingest_pdf(pdf_path):  # produces list[CroppedTable]
#     doc = PyPDFium2Document(pdf_path)
#     tables = []
#     for page in doc:
#         tables += detector.extract(page)
#     return tables, doc

# def extract_and_store_tables(tables):
#     extracted_data = []
#     for idx, table in enumerate(tables):
#         # Format the table using the formatter
#         formatted_table = formatter.format(table)
        
#         # Convert to a DataFrame
#         df = formatted_table.df()  # Replace with the appropriate method to get DataFrame

#         # Store the DataFrame in the list
#         extracted_data.append(df)

#     return extracted_data

# # Replace with your PDF path
# tables, doc = ingest_pdf("./doc.pdf")
# extracted_tables = extract_and_store_tables(tables)
# doc.close()  # Close the document once you're done with it

# # Now you can access the extracted tables later using `extracted_tables`
# # Example: Access the first table DataFrame
# print("First table DataFrame:")
# print(extracted_tables[0])






# # new in v0.3: gmft.auto
# from gmft.auto import AutoTableDetector, AutoTableFormatter
# from gmft.pdf_bindings import PyPDFium2Document
# import pandas as pd

# detector = AutoTableDetector()
# formatter = AutoTableFormatter()

# def ingest_pdf(pdf_path):  # produces list[CroppedTable]
#     doc = PyPDFium2Document(pdf_path)
#     tables = []
#     text_content = {}
    
#     for page_number, page in enumerate(doc, start=1):
#         # Extract tables
#         tables += detector.extract(page)

#         # Extract text using `get_positions_and_text`
#         page_text = ""
#         text_positions = page.get_positions_and_text()
        
#         # Iterate through the text and positions
#         for x1, y1, x2, y2, text in text_positions:
#             page_text += text + " "

#         text_content[page_number] = page_text.strip()
    
#     return tables, text_content, doc

# def extract_and_store_tables(tables):
#     extracted_data = []
#     for idx, table in enumerate(tables):
#         # Format the table using the formatter
#         formatted_table = formatter.format(table)
        
#         # Convert to a DataFrame
#         df = formatted_table.df()  # Replace with the appropriate method to get DataFrame

#         # Store the DataFrame in the list
#         extracted_data.append(df)

#     return extracted_data

# # Replace with your PDF path
# tables, text_content, doc = ingest_pdf("./app/api/doc.pdf")
# extracted_tables = extract_and_store_tables(tables)
# doc.close()  # Close the document once you're done with it

# # Now you can access the extracted tables and text content
# # Example: Access the first table DataFrame
# print("First table DataFrame:")
# print(extracted_tables[2])

# # Example: Access text content from the first page
# print("\nText content from the first page:")
# print(text_content[20])


from gmft.auto import AutoTableDetector, AutoTableFormatter
from gmft.pdf_bindings import PyPDFium2Document
import pandas as pd
from io import BytesIO

detector = AutoTableDetector()
formatter = AutoTableFormatter()

def ingest_pdf(pdf_bytes):  # Accepts a file-like object or bytes
    doc = PyPDFium2Document(pdf_bytes)
    tables = []
    text_content = {}
    
    for page_number, page in enumerate(doc, start=1):
        # Extract tables
        tables += detector.extract(page)

        # Extract text using `get_positions_and_text`
        page_text = ""
        text_positions = page.get_positions_and_text()
        
        # Iterate through the text and positions
        for x1, y1, x2, y2, text in text_positions:
            page_text += text + " "

        text_content[page_number] = page_text.strip()
    
    return tables, text_content, doc

def extract_and_store_tables(tables):
    extracted_data = []
    for idx, table in enumerate(tables):
        # Format the table using the formatter
        formatted_table = formatter.format(table)
        
        # Convert to a DataFrame
        df = formatted_table.df()  # Replace with the appropriate method to get DataFrame

        # Store the DataFrame in the list
        extracted_data.append(df)

    return extracted_data

# Example: Load a PDF file into memory
with open("./app/api/doc.pdf", "rb") as f:
    pdf_bytes = BytesIO(f.read())

# Use the bytes instead of a file path
tables, text_content, doc = ingest_pdf(pdf_bytes)
extracted_tables = extract_and_store_tables(tables)
doc.close()  # Close the document once you're done with it

# Now you can access the extracted tables and text content
# Example: Access the first table DataFrame
print("First table DataFrame:")
print(extracted_tables[9])

# Example: Access text content from the first page
print("\nText content from the first page:")
print(text_content[25])
