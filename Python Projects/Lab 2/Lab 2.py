import urllib.request
url = "https://en.wikipedia.org/wiki/List_of_countries_by_carbon_dioxide_emissions"
page = urllib.request.urlopen(url)
from bs4 import BeautifulSoup
soup = BeautifulSoup(page, "lxml")


all_tables=soup.find_all("table")


right_table=soup.find_all('table', class_='wikitable sortable')



A=[]
B=[]
C=[]
D=[]
E=[]
import re
for row in right_table[0].findAll('tr'):
    cells=row.findAll('td')
    if len(cells)==8:
        for i in cells[0]:
            # print(i.find(text = True))
            alnk = i.find(text = True)
        A.append(alnk)
        B.append(cells[1].find(text=True))
        C.append(cells[2].find(text=True))
        D.append(cells[3].find(text=True))
        E.append(cells[4].find(text=True))


import pandas as pd
df=pd.DataFrame(A,columns=['Countries'])
# df['Manager']=B
# df['Captain']=C
# df['Kit_manufacturer']=D
df['2017 Carbon Emission Data']=E
# print(df)
import sqlite3


class createCarbDatabase():
    def __init__(self):
        self.a = 1
    def createDB(self):
        try:
            con = sqlite3.connect('CarbonDB.db')
            cur = con.cursor()
            cur.execute('''CREATE TABLE Carbon(country text, emission real)''')
            con.close()
        except sqlite3.Error as sam:
            print('error from create db', sam)
a = createCarbDatabase()
a.createDB()


class insertCarbon():
    def __init__(self, country, emission):
        self.dbName = 'CarbonDB.db'
        self.country = country
        self.emission = emission

    def insertData(self):
        con = sqlite3.connect(self.dbName)
        cur = con.cursor()
        data_tuple = (self.country, self.emission)
        sql_lite_insert = """INSERT INTO Carbon values(?, ?)"""
        con.execute(sql_lite_insert, data_tuple)
        con.commit()
        con.close()


for key in range(len(A)):
    b = insertCarbon(A[key], E[key])
    b.insertData()

class getTopTen():
    def __init__(self):
        self.carb_dict = {}
    def __iter__(self):
        con = sqlite3.connect('CarbonDB.db')
        cur = con.cursor()
        for i in cur.execute('SELECT country, emission from Carbon ORDER BY emission DESC LIMIT 10'):
            if i[0] not in self.carb_dict:
                self.carb_dict[i[0]] = i[1]
        yield self.carb_dict
        con.close()
d = getTopTen()
countries = []
emission_values = []
for i in d:
    for key, value in i.items():
        countries.append(key)
        emission_values.append(value)

char = '%'
for idx, ele in enumerate(emission_values):
        emission_values[idx] = ele.replace(char, '')

import matplotlib.pyplot as plt

my_data = emission_values
my_labels = countries
plt.pie(my_data,labels=my_labels,autopct='%1.1f%%')
plt.title('Co2 Top 10 Emission Countries')
plt.axis('equal')
plt.show()