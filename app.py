from dash import Dash, dcc, html, Input, Output, callback
from dash.exceptions import PreventUpdate
from retry_requests import retry
import dash_leaflet as dl
import openmeteo_requests
import pandas as pd
import requests
import requests_cache

app = Dash(__name__)

app.layout = html.Div(
    [
        html.Div(
            className="container",
            children=[
                html.H1(id="title", children="⛈️ Weather Dashboard ⛈️"),
            ],
        ),
        html.Div(
            className="content",
            children=[
                dcc.Input(
                    id="location",
                    type="text",
                    placeholder="City or ZIP Code",
                    debounce=True,
                ),
                html.Button("Submit", id="submit-btn"),
                html.Div(
                    id="map-container",
                    children=[
                        dl.Map(
                            id="map",
                            children=[dl.TileLayer()],
                            center=[0, 0],
                            zoom=9,
                            style={"height": "50vh"},
                        )
                    ],
                    style={"visibility": "hidden"},
                ),
            ],
        ),
    ]
)


@callback(
    [
        Output("map", "center"),
        Output("map-container", "style"),
    ],
    Input("location", "value"),
    prevent_initial_call=True,
)
def update_output(location):
    if not location:
        raise PreventUpdate

    geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=en&format=json"
    res = requests.get(geocode_url).json()
    lat = res["results"][0]["latitude"]
    lon = res["results"][0]["longitude"]

    new_center = [lat, lon]
    new_style = {
        "visibility": "visible",
    }

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
    # hourly = response.Hourly()
    # hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
    # hourly_precipitation_probability = hourly.Variables(1).ValuesAsNumpy()

    # hourly_data = {
    #     "date": pd.date_range(
    #         start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
    #         end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
    #         freq=pd.Timedelta(seconds=hourly.Interval()),
    #         inclusive="left",
    #     )
    # }
    # hourly_data["temperature_2m"] = hourly_temperature_2m
    # hourly_data["precipitation_probability"] = hourly_precipitation_probability

    # hourly_dataframe = pd.DataFrame(data=hourly_data)
    # print(hourly_dataframe)

    return new_center, new_style


if __name__ == "__main__":
    app.run(debug=True)
