# import pandas as pd
# import re
# import tabula as tb
# print('bob')

# # file_path = '/Users/sureshwarasridhara/PycharmProjects/PDFScraper/Frey_Jacob_2014_Annual_report.pdf'
# file_web = 'https://www16.co.hennepin.mn.us/cfrs/getReport.pdf?seq=16&ids=742'
#file_pdf = 'Frey_Jacob_2014_Annual_report.pdf'
# # file_pdf = 'sample.pdf'
# # file_pdf = open('Frey_Jacob_2014_Annual_report.pdf', 'r')
# # print(file_pdf.read())
# #31 columns and 8 rows
# data = tb.read_pdf(file_web, pages = '4', multiple_tables= True)

#import PDF Scraper
import PyPDF2

#creating a pdf file obj
pdfFileObj = open('Frey_Jacob_2014_Annual_report.pdf', 'rb')

#creating a pdf reader obj
pdfReader = PyPDF2.PdfFileReader(pdfFileObj)

#printing # of pages in pdf file
print(pdfReader.numPages)

#creating a page obj
pageObj = pdfReader.getPage(4)

#extraciting text from page
print(pageObj.extractText())


#closing obj
pdfFileObj.close()

import camelot