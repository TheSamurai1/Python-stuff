import json
import xml.etree.ElementTree as ET

data_dict = {}

def parseXML(file_name):
    country = ''
    value = ''
    year = ''
    # Parse XML with ElementTree
    tree = ET.ElementTree(file=file_name)
    root = tree.getroot()

    # get the information via the children!
    elements = root.getchildren()
    for element in elements:
        elem_children = element.getchildren()
        for elem_child in elem_children:
            element_adult = elem_child.getchildren()
            for i in element_adult:
                if i.tag == 'Country':
                    if i.text not in data_dict:
                        country = i.text
                if i.tag == 'Year':
                    if country not in data_dict:
                        year = i.text
                if i.tag == 'Value':
                    if country not in data_dict:
                        value = i.text
                if country != '' and year != '' and value != '':
                    data_dict[country+'-' + year] = [value]
                    country = ''
                    year = ''
                    value = ''




import sqlite3
import numpy as np
import matplotlib.pyplot as plt

class createCountryDatabase():
    def __init__(self):
        self.a = 1
    def createDB(self):
        try:
            con = sqlite3.connect('Countries.db')
            cur = con.cursor()
            cur.execute('''CREATE TABLE Country_Table(country text, year INTEGER, value real)''')
            con.close()
        except sqlite3.Error as sam:
            print('error from create db', sam)



class insertCarbon():
    def __init__(self, country, year, value):
        self.dbName = 'Countries.db'
        self.country = country
        self.year = year
        self.value = value

    def insertData(self):
        con = sqlite3.connect(self.dbName)
        cur = con.cursor()
        data_tuple = (self.country, self.year, self.value)
        sql_lite_insert = """INSERT INTO Country_Table values(?, ?, ?)"""
        con.execute(sql_lite_insert, data_tuple)
        con.commit()
        con.close()




def getJsonData(country_name):
    dict_country = {}
    con = sqlite3.connect('Countries.db')
    cur = con.cursor()
    sql_txt = 'SELECT year, value from Country_Table WHERE Country=?'
    for i in cur.execute(sql_txt, [country_name]):
        dict_country[i[1]] = i[0]
    json_dict = json.dumps(dict_country)
    con.close()
    return (json_dict)




''' This is server.py code'''

import socket


class Server:
    def __init__(self,port):
        self.host = socket.gethostname()
        self.port = port  # initiate port no above 1024
        self.server_socket = socket.socket()  # get instance
        self.server_socket.bind((self.host, self.port))  # bind host address and port together
    def Connect(self,nports):
        # configure how many client the server can listen simultaneously
        self.server_socket.listen(nports)
        conn, address = self.server_socket.accept()  # accept new connection
        print("Connection from: " + str(address))
        while True:
            # receive data stream. it won't accept data packet greater than 1024 bytes
            data = conn.recv(1024).decode()
            json_dict = (getJsonData(str(data)))
            if not data:
                # if data is not received break
                break
            print("from connected user: " + str(data))
            # data = input(' -> ')
            data = json_dict
            conn.send(data.encode())  # send data to the client
        conn.close()  # close the connection




''' This is server.py code'''

#Parsing through the XML File
if __name__ == "__main__":
    parseXML("UNData.xml")

#Creating the Database
a = createCountryDatabase()
a.createDB()
#Inserting the Data Values from XML File
countries, values, years = '', '', ''
for key, value in data_dict.items():
    x = key.split('-')
    countries = x[0]
    years = x[1]
    for i in value:
        values = i
    b = insertCarbon(countries, values, years)
    b.insertData()


if __name__ == '__main__':
    server = Server(5000)
    server.Connect(2)








