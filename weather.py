from dotenv import load_dotenv
from pprint import pprint
import requests
import os

load_dotenv()
#lat =  37.696103, lon =  -121.8676914
def get_currrent_weather(city = "San Leandro"):

    request_url = f'http://api.openweathermap.org/data/2.5/weather?appid={os.getenv("API_KEY")}&q={city}&units=imperial'
    #request_url = f'https://api.openweathermap.org/data/2.5/weather?appid={os.getenv("API_KEY")}&q={lat}&q={lon}&units=imperial'

    # requests_url = f'https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={os.getenv("API_KEY")}&units=imperial'

    weather_data = requests.get(request_url).json()

    return weather_data

# a= get_currrent_weather(37.696119, -121.8676689) # <-- current latitude and longitude location
# print(a)


if __name__ == "__main__":
    print('\n*** Get Current Weather Conditions *** \n')

    city = input("\n Please entery a city name:")

    weather_data = get_currrent_weather(city)

    print("\n")

    pprint(weather_data)


#body onload is something that will automatically start everything.





