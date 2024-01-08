from Proccessor import Proccessor
import collections

b = Proccessor()
b.LoadCarbonData()
b.LoadTempData()
global_data = collections.namedtuple('Global', ['Year','Average', 'Median'])
class Database():
    def __init__(self):
        self.data = 0
        self.global_list = []
    def getGlobalData(self):
        for key, value in sorted(b.getCarbonData().items()):
            for key1, value1 in b.getTempData().items():
                if key == key1:
                    Global = global_data(key, value, value1)
                    self.global_list.append(Global)
                    
        return self.global_list
                    
                    




d = Database()
