from dash import Dash, dcc, html, Input, Output, callback
from retry_requests import retry
import requests
import requests_cache
import openmeteo_requests
import pandas as pd
import dash_daq as daq

app = Dash(__name__)

app.layout = html.Div(
    [
        html.Div(
            className="container",
            children=[
                html.H1(id="title", children="News Channel 1"),
            ],
        ),
        html.Div(
            className="content",
            children=[
                dcc.Input(
                    id="location",
                    type="text",
                    placeholder="Type a location",
                    debounce=True,
                ),
                html.Button("Submit", id="submit-btn"),
                html.Div(id="output"),
            ],
        ),
        html.Div(id="humidity-gauge")  
    ]
)


@callback(
    Output("humidity-gauge", "children"),  
    Input("location", "value"),
    prevent_initial_call=True,
)
def update_output(location):
    if location != "":
        geocode_url = "https://geocoding-api.open-meteo.com/v1/search?name={}&count=1&language=en&format=json".format(
            location
        )
        req = requests.get(geocode_url).json()
        lat = req["results"][0]["latitude"]
        lon = req["results"][0]["longitude"]

        # Setup the Open-Meteo API client with cache and retry on error
        cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        openmeteo = openmeteo_requests.Client(session=retry_session)

        
        forecast_url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ["temperature_2m", "relative_humidity_2m", "precipitation_probability"],  
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "auto",
        }
        responses = openmeteo.weather_api(forecast_url, params=params)

        # Process first location. 
        response = responses[0]

        # Process hourly data. 
        hourly = response.Hourly()
        hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
        hourly_relative_humidity_2m = hourly.Variables(1).ValuesAsNumpy()  
        hourly_precipitation_probability = hourly.Variables(2).ValuesAsNumpy() 

        hourly_data = {
            "date": pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left",
            )
        }
        hourly_data["temperature_2m"] = hourly_temperature_2m
        hourly_data["relative_humidity_2m"] = hourly_relative_humidity_2m  
        hourly_data["precipitation_probability"] = hourly_precipitation_probability  

        hourly_dataframe = pd.DataFrame(data=hourly_data)
        print(hourly_dataframe)

        # Calculate average humidity and display it in a gauge
        avg_humidity = hourly_dataframe["relative_humidity_2m"].mean()
        humidity_gauge = daq.Gauge(
            color={"gradient":True,"ranges":{"green":[0,30],"yellow":[30,60],"red":[60,100]}},  # Adjusted color ranges
            value=avg_humidity,
            label='Humidity (%)',
            max=100,
            min=0,
        )
        
        return humidity_gauge

if __name__ == "__main__":
    app.run(debug=True)
