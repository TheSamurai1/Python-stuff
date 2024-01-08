class CarbonEmissionClass():
    def __init__(self):
        self.carbon_dict = {}
    def __add__(self, year, month, average):
        if year in self.carbon_dict:
            self.carbon_dict[year, month] += average
        else:
            self.carbon_dict[year, month] = average
    def getCarbonDict(self):
        return self.carbon_dict
    def getYearAvg(self, year):
        months = 0
        total_emmision = 0.0
        for (key1, key2), value in self.carbon_dict.items():
            if str(key1) == str(year):
                months += 1
                #print(value)
                total_emmision += float(value)
        return total_emmision / months


