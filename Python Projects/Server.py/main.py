import socket
import matplotlib.pyplot as plt
import numpy as np
import json


data = ''
class Client:
    def __init__(self,nport, client_msg):
        self.host = socket.gethostname()  # as both code is running on same pc
        self.port = nport  # socket server port number
        self.client_socket = socket.socket()  # instantiate
        self.client_socket.connect((self.host, self.port))  # connect to the server
        self.client_msg = client_msg
    def Connect(self):
        # message = input(" -> ")  # take input
        message = self.client_msg
        # while message.lower().strip() != 'bye':
        self.client_socket.send(message.encode())  # send message
        global data
        data = self.client_socket.recv(1024).decode()  # receive response
        print('Received from server: ' + data)  # show in terminal
        self.client_socket.close()  # close the connection


# print(data)
class graph():
    def __init__(self,graphXlist, graphYList):
        self.graphXList = graphXlist
        self.graphYList = graphYList
    def XYPlot(self):
        # define data values
        x = np.array(self.graphXList)  # X-axis points
        y = np.array(self.graphYList)  # Y-axis points
        plt.plot(x, y)  # Plot the chart
        plt.show()  # display

print(data, 'data')
def ParseNPlot():
    if data != '':
        data_sample = (json.loads(data))
        print(data_sample, 'data sample')
        x_list = []
        y_list = []
        for key, value in data_sample.items():
            x_list.append(key)
            y_list.append(value)
        print(x_list)
        print(y_list)

        c = graph(x_list, y_list)
        c.XYPlot()

data_list = [
    "Australia",
    "Austria",
    "Belarus",
    "Belgium",
    "Bulgaria",
    "Canada",
    "Croatia",
    "Cyprus",
    "Czechia",
    "Denmark",
    "Estonia",
    "European Union",
    "Finland",
    "France",
    "Germany",
    "Greece",
    "Hungary",
    "Iceland",
    "Ireland",
    "Italy",
    "Japan",
    "Latvia",
    "Liechtenstein",
    "Lithuania",
    "Luxembourg",
    "Malta",
    "Monaco",
    "Netherlands",
    "New Zealand",
    "Norway",
    "Poland",
    "Portugal",
    "Romania",
    "Russian Federation",
    "Slovakia",
    "Slovenia",
    "Spain",
    "Sweden",
    "Switzerland",
    "Turkey",
    "Ukraine",
    "United Kingdom",
    "United States of America"
]

from tkinter import *


def CountryCall(s):
    client = Client(5000, 'Australia')
    client.Connect()
    ParseNPlot()

master = Tk()
variable = StringVar()
variable.set(data_list[0])  # default value
w = OptionMenu(master, variable, *data_list, command=CountryCall).pack()

mainloop()