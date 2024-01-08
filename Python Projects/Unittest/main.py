import unittest
import urllib.request
from bs4 import BeautifulSoup

class TestOutput(unittest.TestCase):
    def testType(self):
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
                self.assertEqual(type(elements), list)
if __name__=='__main__':
     unittest.main()
