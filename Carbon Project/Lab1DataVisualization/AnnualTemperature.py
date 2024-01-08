class AnnualTemperature():
    def __init__(self):
        self.temp_dict = {}
    def __add__(self, year, median):
        if year not in self.temp_dict:
            self.temp_dict[year] = median
        # else:
        #     self.temp_dict[year] = median
    def getTempDict(self):
        return self.temp_dict
    def getMedianAvg(self, year):
        for key, value in self.temp_dict.items():
            if str(key) == str(year):
                return value
            




 
