from Database import Database
from Proccessor import Proccessor
d = Database()
a = Proccessor()

for i in d.getGlobalData():

    print(i['Year'])


a.closeCarbonFile()
a.closeTempFile()
