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
            cur.execute('''CREATE TABLE Data(country text, year real, value real)''')
            con.close()
        except sqlite3.Error as sam:
            print('error from create db', sam)
a = createCountryDatabase()
a.createDB()


class insertCarbon():
    def __init__(self, country, year, value):
        self.dbName = 'CarbonDB.db'
        self.country = country
        self.year = year
        self.value = value

    def insertData(self):
        con = sqlite3.connect(self.dbName)
        cur = con.cursor()
        data_tuple = (self.country, self.year, self.value)
        sql_lite_insert = """INSERT INTO Carbon values(?, ?, ?)"""
        con.execute(sql_lite_insert, data_tuple)
        con.commit()
        con.close()
b = insertCarbon()
b.insertData('Zambia', 2, 3)

class graph():
    def __init__(self):
        self.graphXList = []
        self.graphYList = []
    def XYPlot(self):
        # define data values
        x = np.array(self.graphXList)  # X-axis points
        y = np.array(self.graphYList)  # Y-axis points
        plt.plot(x, y)  # Plot the chart
        plt.show()  # display