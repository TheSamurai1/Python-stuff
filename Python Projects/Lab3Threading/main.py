import urllib.request
from bs4 import BeautifulSoup
import sqlite3
import queue
import threading
import pandas as pd
import numpy as np
from matplotlib.figure import Figure
import matplotlib.pyplot as plot1



def createnasatable():
    try:
        global con
        con = sqlite3.connect('Nasa.db')
        global cur
        cur = con.cursor()
        cur.execute(
            '''CREATE TABLE Radioactive(Year INT, CO2 REAL, CH4 REAL, N2O REAL, CFC12 REAL, CFC11 REAL, MINOR15 REAL)''')
        con.close()
    except sqlite3.Error as sam:
        print('error from create db', sam)
def insertdata(elements):
    con = sqlite3.connect('Nasa.db')
    cur = con.cursor()
    sql_lite_insert = """INSERT INTO Radioactive values(?, ?, ?, ?, ?, ?, ?)"""
    con.execute(sql_lite_insert, elements)
    con.commit()
    con.close()
def nasascrape():
    url = "https://www.esrl.noaa.gov/gmd/aggi/aggi.html"
    page = urllib.request.urlopen(url)
    soup = BeautifulSoup(page, "html.parser")

    all_tables=soup.find_all("table")

    right_table= soup.find('table', {'class':"table table-bordered table-condensed table-striped table-header"})
    for row in right_table.find_all('tr'):
        elements = []
        cols = row.find_all('td')
        if len(cols) >= 7:
            for i in cols[0:7]:
                elements.append(i.text)
            insertdata(elements)
            # print(elements)
def processThread(queue):
    while True:
        qname = queue.get()
        con= sqlite3.connect('Nasa.db')
        cur = con.cursor()
        sqltxt = 'SELECT Year, ' + qname + ' FROM Radioactive WHERE Year = ? '
        data_list = []
        for i in range(1979, 2019):
            cur.execute(sqltxt, [i])
            data_list.append(cur.fetchone())
            a = linearRegression(data_list, qname)
            a.graph()
        con.close()

def mythreading():
    threadList = ["CO2-T1", "CH4-T2", "N2O-T3", "CFC12-T4", "CFC11-T5", "MINOR15-T6"]
    queueList = ["CO2", "CH4", "N2O", "CFC12", "CFC11", "MINOR15"]
    workQueue = queue.Queue(len(queueList))
    threads = []
    for threadName in threadList:
        thread = threading.Thread(target = processThread, args =(workQueue,))
        thread.setDaemon(True)
        thread.start()
        threads.append(thread)
    for rad_word in queueList:
        workQueue.put(rad_word)
    workQueue.join()

class linearRegression():
    def __init__(self, values, names):
        numbers = np.asarray(values, dtype=np.float)
        self.x = numbers[:,0]
        self.y = numbers[:,1]
        self.names = names
    def graph(self):
        line = np.polyfit(self.x, self.y, 1)
        axes = np.poly1d(line)
        fig = Figure(figsize=(5, 5), dpi = 100)
        plot1.plot(self.x, self.y, 'yo', self.x, axes(self.x), '--k')
        plot1.savefig('graph.png')
createnasatable()

nasascrape()

mythreading()

