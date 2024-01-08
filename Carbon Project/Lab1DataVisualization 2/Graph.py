import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
import pandas as pd
import re
from tkinter import *
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from Database import Database
from Proccessor import Proccessor

#Database classes

import sqlite3

class createTempDatabase():
    def __init__(self):
        self.a = 1
    def createDB(self):
        try:
            con = sqlite3.connect('Temp.db')
            cur = con.cursor()
            cur.execute('''CREATE TABLE Temperature(year real, median real)''')
            con.close()
        except sqlite3.Error as sam:
            print('error from create db', sam)


class insertTemp():
    def __init__(self, year, median):
        self.dbName = 'Temp.db'
        self.year = year
        self.median = median

    def insertData(self):
        con = sqlite3.connect(self.dbName)
        cur = con.cursor()
        data_tuple = (self.year, self.median)

        sql_lite_insert = """INSERT INTO Temperature values(?, ?)"""
        con.execute(sql_lite_insert, data_tuple)
        con.commit()
        con.close()

class getRange():
    def __init__(self, range1, range2):
        self.range1 = range1
        self.range2 = range2
        self.temp_dict = {}
    def __iter__(self):
        con = sqlite3.connect('Temp.db')
        cur = con.cursor()
        for i in cur.execute('SELECT year, median from Temperature WHERE year BETWEEN ' + str(self.range1) + ' and ' + str(self.range2)):
            if i[0] not in self.temp_dict:
                self.temp_dict[i[0]] = i[1]
        yield self.temp_dict
        con.close()



class readTempTableData():
    def __init__(self):
        self.dbName = 'Temp.db'
        self.tble_name = 'Temperature'
        self.tempDict = {}

    def __iter__(self):
        con = sqlite3.connect(self.dbName)
        cur = con.cursor()
        for i in cur.execute('SELECT year, median from Temperature ORDER BY year'):
            if i[0] not in self.tempDict:
                self.tempDict[i[0]] = i[1]
        yield self.tempDict
            #yield i
        con.close()


class graph():
    def __init__(self):
        self.graphXList = []
        self.graphYList = []
        a = getRange(1960, 1990)
        for i in a:
            for k in i:
                self.graphXList.append(k)
                self.graphYList.append(i[k])
    def XYPlot(self):
        # define data values
        x = np.array(self.graphXList)  # X-axis points
        y = np.array(self.graphYList)  # Y-axis points
        plt.plot(x, y)  # Plot the chart
        plt.show()  # display
    def barChart(self):
        plt.bar(self.graphXList, self.graphYList)
        plt.title('Temperature Bar Chart')
        plt.xlabel('Years')
        plt.ylabel('Median Values')
        plt.show()
    def linearRegression(self):
        x = np.array(self.graphXList)
        y = np.array(self.graphYList)
        plt.plot(x, y, 'o')
        m, b = np.polyfit(x, y , 1)
        plt.plot(x, m*x + b)
        plt.show()


from tkinter import *
def Plot():
    graph_data = graph()
    window = Tk()
    window.title('Plotting in Tkinter')
    window.geometry("500x500")
    linear_button = Button(master=window,
                         command = graph_data.linearRegression,
                         height=2,
                         width=10,
                         text="Linear Regression")
    linear_button.pack()
    XY_button = Button(master=window,
                        command = graph_data.XYPlot,
                        height=2,
                        width=10,
                        text="XY Plot")
    XY_button.pack()

    barChart_button = Button(master=window,
                       command = graph_data.barChart,
                        height=2,
                        width=10,
                        text="Bar Chart")
    barChart_button.pack()
    window.mainloop()


#Lab 1- Main Calls
A = createTempDatabase()
A.createDB()


a = Proccessor()
d = Database()
for i in d.getGlobalData():
     b = insertTemp(i.Year, i.Median)
     b.insertData()

a.closeTempFile()
Plot()
