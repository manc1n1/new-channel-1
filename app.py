from dash import Dash, dcc, html, Input, Output, callback
from retry_requests import retry
import requests
import requests_cache
import openmeteo_requests
import pandas as pd

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
    ]
)


@callback(
    Output("output", "children"),
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

        # Make sure all required weather variables are listed here
        # The order of variables in hourly or daily is important to assign them correctly below
        forecast_url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ["temperature_2m", "precipitation_probability"],
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "auto",
        }
        responses = openmeteo.weather_api(forecast_url, params=params)

        # Process first location. Add a for-loop for multiple locations or weather models
        response = responses[0]

        # Process hourly data. The order of variables needs to be the same as requested.
        hourly = response.Hourly()
        hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
        hourly_precipitation_probability = hourly.Variables(1).ValuesAsNumpy()

        hourly_data = {
            "date": pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left",
            )
        }
        hourly_data["temperature_2m"] = hourly_temperature_2m
        hourly_data["precipitation_probability"] = hourly_precipitation_probability

        hourly_dataframe = pd.DataFrame(data=hourly_data)
        print(hourly_dataframe)


if __name__ == "__main__":
    app.run(debug=True)
